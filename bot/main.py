"""Entrypoint for running the Discord voice assistant bot."""
from __future__ import annotations

import logging
from typing import Dict, Optional

import discord
from discord.ext import commands

from .config import Settings, load_settings
from .openai_client import OpenAIResponder
from .voice_session import VoiceSession

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
LOGGER = logging.getLogger(__name__)


def create_bot(settings: Settings) -> commands.Bot:
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True
    intents.voice_states = True

    bot = commands.Bot(command_prefix="!", intents=intents)

    sessions: Dict[int, VoiceSession] = {}

    @bot.event
    async def on_ready() -> None:
        LOGGER.info("Bot logged in as %s (ID: %s)", bot.user, bot.user.id if bot.user else "?")

    def get_session(guild_id: int) -> Optional[VoiceSession]:
        return sessions.get(guild_id)

    async def ensure_session(ctx: commands.Context) -> VoiceSession:
        session = get_session(ctx.guild.id)
        if session:
            session.ctx = ctx
            return session
        if not ctx.author.voice or not ctx.author.voice.channel:
            raise commands.CommandError("Вы должны находиться в голосовом канале, чтобы призвать бота.")
        channel = ctx.author.voice.channel
        voice_client: discord.VoiceClient = await channel.connect()
        responder = OpenAIResponder(api_key=settings.openai_api_key)
        session = VoiceSession(
            ctx=ctx,
            voice_client=voice_client,
            responder=responder,
            silence_duration=settings.silence_duration,
            vad_level=settings.silence_threshold,
            target_user_id=settings.target_user_id,
        )
        sessions[ctx.guild.id] = session
        await session.start()
        return session

    @bot.command(name="join")
    async def join(ctx: commands.Context) -> None:
        """Summon the assistant into your voice channel."""

        if ctx.guild is None:
            raise commands.CommandError("Эта команда доступна только на сервере.")
        if get_session(ctx.guild.id):
            await ctx.send("Я уже слушаю этот канал.")
            return
        session = await ensure_session(ctx)
        session.ctx = ctx
        await ctx.send(
            "Привет! Я подключился к голосовому каналу. Просто поговорите, и я отвечу после небольшой паузы."
        )
        LOGGER.info("Session started for guild %s", ctx.guild)

    @bot.command(name="leave")
    async def leave(ctx: commands.Context) -> None:
        """Disconnect the bot from the voice channel."""

        if ctx.guild is None:
            return
        session = get_session(ctx.guild.id)
        if not session:
            await ctx.send("Я ещё не подключался к этому каналу.")
            return
        session.ctx = ctx
        await session.stop()
        await session.voice_client.disconnect(force=True)
        del sessions[ctx.guild.id]
        await ctx.send("До встречи! Я отключился от голосового канала.")

    @bot.command(name="reset")
    async def reset(ctx: commands.Context) -> None:
        """Reset the conversation history without leaving the channel."""

        if ctx.guild is None:
            return
        session = get_session(ctx.guild.id)
        if not session:
            await ctx.send("Я пока не подключен. Используйте !join для начала.")
            return
        session.ctx = ctx
        session.responder.reset()
        await ctx.send("Контекст диалога очищен. Можем начинать заново!")

    @bot.event
    async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState) -> None:
        if not bot.user or member.id != bot.user.id:
            return
        if before.channel and not after.channel and before.channel.guild:
            session = sessions.pop(before.channel.guild.id, None)
            if session:
                await session.stop()

    return bot


def main() -> None:
    settings = load_settings()
    bot = create_bot(settings)
    bot.run(settings.discord_token)


if __name__ == "__main__":
    main()
