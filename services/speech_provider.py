"""Optional Azure AI Speech integration (speech-to-text and text-to-speech).

This feature is entirely optional, as required by the project brief: the core
text-based interview flow (services/interview_agent.py) never imports or
depends on anything in this file. The Streamlit app only offers voice
controls when SpeechService.is_available is True, i.e. when both
AZURE_SPEECH_KEY and AZURE_SPEECH_REGION are set in the environment.

Voice round trip demonstrated end-to-end:

    Microphone audio (recorded in the browser via st.audio_input)
        -> SpeechService.speech_to_text()        [Azure AI Speech, STT]
        -> InterviewAgent.submit_answer()         [agent + AI evaluation,
                                                     adaptive next question]
        -> SpeechService.text_to_speech()          [Azure AI Speech, TTS]
        -> audio played back to the user in the browser

The Azure Speech SDK (azure-cognitiveservices-speech) is only imported inside
this class, so a machine without that package installed can still run the
whole text-based app in Demo Mode.
"""

import os
import tempfile
from typing import Optional


class SpeechError(Exception):
    """Raised when speech-to-text or text-to-speech fails or is unavailable."""


class SpeechService:
    """Thin wrapper around Azure AI Speech for STT and TTS.

    Only ever raises SpeechError -- callers (the Streamlit UI) do not need to
    know anything about the underlying Azure Speech SDK.
    """

    #: Voice used for reading interview questions aloud.
    DEFAULT_VOICE = "en-US-JennyNeural"
    #: Language used for transcribing the candidate's spoken answers.
    DEFAULT_LANGUAGE = "en-US"

    def __init__(self, speech_key: Optional[str] = None, speech_region: Optional[str] = None):
        self.speech_key = speech_key or os.environ.get("AZURE_SPEECH_KEY", "").strip()
        self.speech_region = speech_region or os.environ.get("AZURE_SPEECH_REGION", "").strip()

    @property
    def is_available(self) -> bool:
        """True if both Speech credentials are configured."""
        return bool(self.speech_key and self.speech_region)

    def _speech_config(self):
        """Build a fresh SpeechConfig for one request. Raises SpeechError if unavailable."""
        if not self.is_available:
            raise SpeechError(
                "Azure AI Speech is not configured. Set AZURE_SPEECH_KEY and "
                "AZURE_SPEECH_REGION in .env to enable voice mode."
            )
        try:
            import azure.cognitiveservices.speech as speechsdk
        except ImportError as exc:
            raise SpeechError(
                "The azure-cognitiveservices-speech package is not installed. "
                "Run: pip install azure-cognitiveservices-speech"
            ) from exc

        config = speechsdk.SpeechConfig(subscription=self.speech_key, region=self.speech_region)
        config.speech_recognition_language = self.DEFAULT_LANGUAGE
        config.speech_synthesis_voice_name = self.DEFAULT_VOICE
        return speechsdk, config

    def speech_to_text(self, audio_bytes: bytes) -> str:
        """Transcribe recorded microphone audio (WAV bytes) into text.

        `audio_bytes` is the raw WAV data returned by Streamlit's
        st.audio_input widget. Returns the transcribed text, or raises
        SpeechError if nothing could be recognized.
        """
        speechsdk, config = self._speech_config()

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
            tmp_file.write(audio_bytes)
            tmp_path = tmp_file.name

        try:
            audio_config = speechsdk.audio.AudioConfig(filename=tmp_path)
            recognizer = speechsdk.SpeechRecognizer(speech_config=config, audio_config=audio_config)
            result = recognizer.recognize_once()

            if result.reason == speechsdk.ResultReason.RecognizedSpeech:
                text = result.text.strip()
                if not text:
                    raise SpeechError("No speech was recognized in the recording.")
                return text
            if result.reason == speechsdk.ResultReason.NoMatch:
                raise SpeechError("Could not understand the recording. Please try speaking again.")
            if result.reason == speechsdk.ResultReason.Canceled:
                details = result.cancellation_details
                raise SpeechError(f"Speech recognition was canceled: {details.reason} "
                                   f"({details.error_details or 'no further details'})")
            raise SpeechError(f"Speech recognition failed: {result.reason}")
        except SpeechError:
            raise
        except Exception as exc:  # network error, SDK error, etc.
            raise SpeechError(f"Speech-to-text request failed: {exc}") from exc
        finally:
            try:
                os.remove(tmp_path)
            except OSError:
                pass

    def text_to_speech(self, text: str) -> bytes:
        """Convert text (e.g. an interview question) into spoken audio (WAV bytes)."""
        if not text or not text.strip():
            raise SpeechError("No text was provided to speak.")

        speechsdk, config = self._speech_config()
        # audio_config=None makes the synthesizer return audio bytes in memory
        # instead of playing through a local speaker (needed in a web app).
        synthesizer = speechsdk.SpeechSynthesizer(speech_config=config, audio_config=None)

        try:
            result = synthesizer.speak_text_async(text).get()
        except Exception as exc:
            raise SpeechError(f"Text-to-speech request failed: {exc}") from exc

        if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
            return result.audio_data
        if result.reason == speechsdk.ResultReason.Canceled:
            details = result.cancellation_details
            raise SpeechError(f"Text-to-speech was canceled: {details.reason} "
                               f"({details.error_details or 'no further details'})")
        raise SpeechError(f"Text-to-speech failed: {result.reason}")


def get_speech_service() -> SpeechService:
    """Return a SpeechService built from environment variables.

    Always returns a SpeechService instance (never raises); check
    `.is_available` before offering voice controls in the UI.
    """
    return SpeechService()
