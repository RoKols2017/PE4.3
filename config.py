from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Literal
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError
from pydantic_settings import BaseSettings


# Загружаем .env из корня проекта (явный путь)
_PROJECT_ROOT = Path(__file__).resolve().parent
_ENV_PATH = _PROJECT_ROOT / ".env"
_found = load_dotenv(dotenv_path=_ENV_PATH)
if not _found:
	logging.getLogger(__name__).warning("Файл .env не найден по пути: %s", _ENV_PATH)


class _LoggingConfig(BaseModel):
	level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
		default="INFO"
	)


class Settings(BaseSettings):
	elevenlabs_api_key: str = Field(alias="ELEVENLABS_API_KEY")
	telegram_bot_token: str = Field(alias="TELEGRAM_BOT_TOKEN")
	default_voice_id: str = Field(alias="DEFAULT_VOICE_ID", default="EXAVITQu4vr4xnSDxMaL")
	audio_format: Literal["mp3"] = Field(alias="AUDIO_FORMAT", default="mp3")
	tmp_dir: str = Field(alias="TMP_DIR", default="./tmp")
	send_as: Literal["voice", "audio"] = Field(alias="SEND_AS", default="voice")
	log: _LoggingConfig = Field(default_factory=_LoggingConfig)

	class Config:
		populate_by_name = True
		extra = "ignore"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
	try:
		settings = Settings()
	except ValidationError as exc:
		# Делаем сообщение дружелюбным (без утечки секретов)
		missing = {e["loc"][0] for e in exc.errors()}
		raise RuntimeError(
			f"Отсутствуют или некорректны переменные окружения: {sorted(missing)}"
		) from None

	os.makedirs(settings.tmp_dir, exist_ok=True)

	# Настройка логов один раз
	logging.basicConfig(
		level=getattr(logging, settings.log.level.upper(), logging.INFO),
		format="%(asctime)s %(levelname)s %(name)s - %(message)s",
	)
	return settings
