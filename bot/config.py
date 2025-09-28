"""Configuration helpers for the Discord voice bot."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv


@dataclass
class Settings:
    """Runtime configuration for the bot."""

    discord_token: str
    openai_api_key: str
    silence_duration: float = 2.5
    silence_threshold: int = 2
    target_user_id: Optional[int] = None


def load_settings() -> Settings:
    """Load configuration from environment variables.

    Returns
    -------
    Settings
        The populated settings dataclass.

    Raises
    ------
    RuntimeError
        If the required environment variables are missing.
    """

    load_dotenv()

    discord_token = os.getenv("DISCORD_TOKEN")
    openai_api_key = os.getenv("OPENAI_API_KEY")

    if not discord_token:
        raise RuntimeError("DISCORD_TOKEN environment variable is required.")

    if not openai_api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable is required.")

    silence_duration = float(os.getenv("SILENCE_DURATION", "2.5"))
    vad_level = int(os.getenv("SILENCE_VAD_LEVEL", "2"))
    target_user = os.getenv("TARGET_USER_ID")

    return Settings(
        discord_token=discord_token,
        openai_api_key=openai_api_key,
        silence_duration=silence_duration,
        silence_threshold=vad_level,
        target_user_id=int(target_user) if target_user else None,
    )
