"""Voice channel utilities for receiving audio and producing replies."""
from __future__ import annotations

import asyncio
import audioop
import io
import logging
import time
import wave
from dataclasses import dataclass
from typing import Awaitable, Callable, Optional

import discord
from discord import abc as discord_abc
import webrtcvad

from .openai_client import OpenAIResponder

LOGGER = logging.getLogger(__name__)

SAMPLE_WIDTH = 2
CHANNELS = 2
SAMPLE_RATE = 48000
TARGET_SAMPLE_RATE = 16000


class SpeechSegmenter(discord.sinks.RawDataSink):
    """Collect PCM data and emit segments once silence is detected."""

    def __init__(
        self,
        *,
        loop: asyncio.AbstractEventLoop,
        on_segment: Callable[[discord_abc.Snowflake, bytes], Awaitable[None]],
        silence_duration: float = 2.5,
        vad_level: int = 2,
        target_user_id: Optional[int] = None,
    ) -> None:
        super().__init__(encoding="pcm")
        self._loop = loop
        self._on_segment = on_segment
        self._silence_duration = silence_duration
        self._target_user_id = target_user_id
        self._buffers: dict[int, bytearray] = {}
        self._last_speech: dict[int, float] = {}
        self._vad = webrtcvad.Vad(vad_level)
        self._running = True

    def _is_speech(self, pcm: bytes) -> bool:
        if not pcm:
            return False
        # Convert stereo 48k audio to mono 16k for the VAD check.
        mono = audioop.tomono(pcm, SAMPLE_WIDTH * CHANNELS, 1, 1)
        resampled, _ = audioop.ratecv(mono, SAMPLE_WIDTH, 1, SAMPLE_RATE, TARGET_SAMPLE_RATE, None)
        frame_duration_ms = int(len(resampled) / (TARGET_SAMPLE_RATE * SAMPLE_WIDTH) * 1000)
        # The VAD requires frames of 10, 20 or 30 ms. If we fall out of range, pad zeros.
        if frame_duration_ms not in (10, 20, 30):
            target_length = int(TARGET_SAMPLE_RATE * (20 / 1000) * SAMPLE_WIDTH)
            resampled = resampled.ljust(target_length, b"\0")
        try:
            return self._vad.is_speech(resampled, TARGET_SAMPLE_RATE)
        except Exception:  # pragma: no cover - fallback if VAD fails
            rms = audioop.rms(pcm, SAMPLE_WIDTH)
            return rms > 300

    def _queue_segment(self, user: discord_abc.Snowflake, payload: bytes) -> None:
        LOGGER.debug("Detected end of speech for %s (%s bytes)", user, len(payload))
        if not payload:
            return

        async def runner() -> None:
            await self._on_segment(user, payload)

        asyncio.run_coroutine_threadsafe(runner(), self._loop)

    def _maybe_flush(self, user: discord.User) -> None:
        now = time.monotonic()
        last = self._last_speech.get(user.id)
        if last is None:
            return
        if now - last >= self._silence_duration:
            payload = bytes(self._buffers.get(user.id, b""))
            self._buffers[user.id] = bytearray()
            self._last_speech[user.id] = None  # type: ignore[assignment]
            if payload:
                self._queue_segment(user, payload)

    def write(self, data: bytes, user: discord.User) -> None:  # type: ignore[override]
        if not self._running or user is None:
            return
        if self._target_user_id and user.id != self._target_user_id:
            return

        buffer = self._buffers.setdefault(user.id, bytearray())
        if self._is_speech(data):
            buffer.extend(data)
            self._last_speech[user.id] = time.monotonic()
        else:
            self._maybe_flush(user)

    def cleanup(self) -> None:  # type: ignore[override]
        self._running = False
        for user_id, buffer in list(self._buffers.items()):
            if buffer:
                fake_user = discord.Object(id=user_id)
                self._queue_segment(fake_user, bytes(buffer))
        self._buffers.clear()


@dataclass
class VoiceSession:
    """Manage a single voice interaction session for a guild."""

    ctx: commands.Context
    voice_client: discord.VoiceClient
    responder: OpenAIResponder
    silence_duration: float
    vad_level: int
    target_user_id: Optional[int]

    def __post_init__(self) -> None:
        self._loop = asyncio.get_event_loop()
        self._segment_queue: asyncio.Queue[tuple[int, bytes]] = asyncio.Queue()
        self._processor_task: Optional[asyncio.Task[None]] = None
        self._sink: Optional[SpeechSegmenter] = None
        self._play_lock = asyncio.Lock()

    async def start(self) -> None:
        """Begin listening for audio and processing responses."""

        LOGGER.info("Starting voice session in guild %s", self.ctx.guild)
        self._sink = SpeechSegmenter(
            loop=self._loop,
            on_segment=self._handle_segment,
            silence_duration=self.silence_duration,
            vad_level=self.vad_level,
            target_user_id=self.target_user_id or self.ctx.author.id,
        )
        self.voice_client.listen(self._sink)
        self._processor_task = asyncio.create_task(self._process_segments())

    async def stop(self) -> None:
        """Tear down the session and release resources."""

        LOGGER.info("Stopping voice session in guild %s", self.ctx.guild)
        if self._sink:
            self.voice_client.stop_listening()
            self._sink = None
        if self._processor_task:
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:  # pragma: no cover - expected during shutdown
                pass
            self._processor_task = None
        self.responder.reset()

    async def _handle_segment(self, user: discord_abc.Snowflake, pcm: bytes) -> None:
        LOGGER.debug("Queued segment from %s (%s bytes)", user, len(pcm))
        await self._segment_queue.put((user.id, pcm))

    async def _process_segments(self) -> None:
        while True:
            user_id, pcm = await self._segment_queue.get()
            try:
                wav_data = pcm_to_wav(pcm)
                transcription = await self.responder.transcribe(wav_data)
                if not transcription:
                    continue
                await self.ctx.send(f"**<@{user_id}>:** {transcription}")
                reply = await self.responder.chat(transcription)
                await self.ctx.send(f"**Assistant:** {reply}")
                audio_bytes = await self.responder.synthesize(reply)
                await self._play_audio(audio_bytes)
            except Exception as exc:  # pragma: no cover - runtime safeguard
                LOGGER.exception("Error while processing audio segment: %s", exc)

    async def _play_audio(self, audio_bytes: bytes) -> None:
        if not audio_bytes:
            return
        async with self._play_lock:
            source = discord.FFmpegPCMAudio(
                io.BytesIO(audio_bytes),
                pipe=True,
            )
            playback_complete = asyncio.Event()

            def after_play(error: Optional[Exception]) -> None:
                if error:
                    LOGGER.error("Playback error: %s", error)
                self._loop.call_soon_threadsafe(playback_complete.set)

            self.voice_client.play(discord.PCMVolumeTransformer(source), after=after_play)
            await playback_complete.wait()


def pcm_to_wav(pcm: bytes, sample_rate: int = SAMPLE_RATE, channels: int = CHANNELS) -> bytes:
    """Convert 16-bit PCM bytes into a WAV container."""

    if not pcm:
        return b""

    with io.BytesIO() as buffer:
        with wave.open(buffer, "wb") as wav_file:
            wav_file.setnchannels(channels)
            wav_file.setsampwidth(SAMPLE_WIDTH)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(pcm)
        return buffer.getvalue()


# Import deferred to avoid circular dependency with discord.ext.commands.
from discord.ext import commands  # noqa: E402  # isort:skip
