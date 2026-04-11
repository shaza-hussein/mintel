import os
import sys
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../../../..")))

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[6]


class Config(BaseSettings):
    BASE_URL: str = "https://openrouter.ai/api/v1/chat/completions"
    MODEL: str = "openai/gpt-4o-mini"
    OPENROUTER_API_KEY: str 

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Config:
    return Config()
