# Settings for the brain part
# This file reads your .env file

from pathlib import Path
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    debug: bool = True
    database_url: str = f"sqlite:///{BASE_DIR / 'football.db'}"
    cache_dir: str = str(BASE_DIR / ".cache")
    cache_ttl_seconds: int = 3600
    football_data_api_key: str = ""
    api_football_key: str = ""
    odds_api_key: str = ""
    frontend_url: str = "http://localhost:3000"

    class Config:
        env_file = BASE_DIR.parent / ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

settings = Settings()
