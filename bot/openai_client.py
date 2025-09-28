"""OpenAI helper utilities for speech transcription and responses."""
from __future__ import annotations

import asyncio
import io
import logging
from dataclasses import dataclass, field
from typing import List

from openai import OpenAI

LOGGER = logging.getLogger(__name__)


@dataclass
class ConversationHistory:
    """Chat history wrapper for maintaining conversational context."""

    system_prompt: str
    messages: List[dict] = field(default_factory=list)

    def reset(self) -> None:
        self.messages = [{"role": "system", "content": self.system_prompt}]

    def append_user(self, content: str) -> None:
        self.messages.append({"role": "user", "content": content})

    def append_assistant(self, content: str) -> None:
        self.messages.append({"role": "assistant", "content": content})


class OpenAIResponder:
    """Wrapper around the OpenAI SDK that exposes async helpers."""

    def __init__(
        self,
        api_key: str,
        *,
        chat_model: str = "gpt-4o-mini",
        transcription_model: str = "gpt-4o-mini-transcribe",
        tts_model: str = "gpt-4o-mini-tts",
        tts_voice: str = "alloy",
    ) -> None:
        self._client = OpenAI(api_key=api_key)
        self._chat_model = chat_model
        self._transcription_model = transcription_model
        self._tts_model = tts_model
        self._tts_voice = tts_voice
        self._history = ConversationHistory(
            system_prompt=(
                "You are a friendly and concise AI assistant speaking with a user "
                "over a Discord voice chat. Respond conversationally and keep "
                "answers under 80 words unless more detail is explicitly requested."
            )
        )
        self._history.reset()

    async def transcribe(self, wav_bytes: bytes) -> str:
        """Transcribe speech audio into text using the transcription model."""

        LOGGER.debug("Submitting audio to OpenAI for transcription (%s bytes)", len(wav_bytes))

        audio_file = io.BytesIO(wav_bytes)
        audio_file.name = "audio.wav"

        def _transcribe() -> str:
            response = self._client.audio.transcriptions.create(
                model=self._transcription_model,
                file=audio_file,
                response_format="text",
            )
            text = response.text.strip() if hasattr(response, "text") else str(response).strip()
            LOGGER.debug("Transcription response: %s", text)
            return text

        return await asyncio.to_thread(_transcribe)

    async def chat(self, user_message: str) -> str:
        """Generate a conversational reply for the provided user message."""

        self._history.append_user(user_message)

        def _complete() -> str:
            completion = self._client.chat.completions.create(
                model=self._chat_model,
                messages=self._history.messages,
                temperature=0.6,
            )
            reply = completion.choices[0].message.content.strip()
            LOGGER.debug("Chat completion response: %s", reply)
            return reply

        assistant_reply = await asyncio.to_thread(_complete)
        self._history.append_assistant(assistant_reply)
        return assistant_reply

    async def synthesize(self, text: str) -> bytes:
        """Convert assistant text into spoken audio via TTS."""

        LOGGER.debug("Synthesizing speech (%s characters)", len(text))

        def _speak() -> bytes:
            response = self._client.audio.speech.create(
                model=self._tts_model,
                voice=self._tts_voice,
                input=text,
                format="mp3",
            )
            # The SDK returns a binary stream-like object.
            audio_data = response.read()
            LOGGER.debug("Received %s bytes of speech audio", len(audio_data))
            return audio_data

        return await asyncio.to_thread(_speak)

    def reset(self) -> None:
        """Clear the current conversation history."""

        self._history.reset()
