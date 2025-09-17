from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx

from config import get_settings

logger = logging.getLogger(__name__)


# Исключения по ТЗ
class VoiceServiceError(Exception):
	pass


class RateLimitError(VoiceServiceError):
	pass


class InvalidInputError(VoiceServiceError):
	pass


@dataclass
class _VoicesCache:
	value: Optional[List[Dict[str, Any]]] = None
	ts: float = 0.0
	ttl: float = 600.0  # 10 минут

	def get(self) -> Optional[List[Dict[str, Any]]]:
		if self.value is None:
			return None
		if time.time() - self.ts > self.ttl:
			return None
		return self.value

	def set(self, value: List[Dict[str, Any]]) -> None:
		self.value = value
		self.ts = time.time()


_voices_cache = _VoicesCache()


def _client() -> httpx.Client:
	settings = get_settings()
	return httpx.Client(
		base_url="https://api.elevenlabs.io/v1",
		headers={
			"xi-api-key": settings.elevenlabs_api_key,
			"Accept": "application/json",
		},
		timeout=15.0,
	)


def get_voices() -> List[Dict[str, Any]]:
	"""
	Возвращает список доступных голосов [{id, name, labels}], кеш 10 минут.
	"""
	cached = _voices_cache.get()
	if cached is not None:
		return cached

	settings = get_settings()

	backoffs = [0.5, 1.0, 2.0]
	last_err: Optional[Exception] = None
	for attempt, backoff in enumerate([0.0] + backoffs):
		if backoff:
			time.sleep(backoff)
		try:
			with _client() as client:
				resp = client.get("/voices")
				if resp.status_code == 429:
					raise RateLimitError("Rate limited")
					
				resp.raise_for_status()
				data = resp.json()
				items = data.get("voices") or data.get("data") or []
				voices: List[Dict[str, Any]] = []
				for v in items:
					voices.append({
						"id": v.get("voice_id") or v.get("id"),
						"name": v.get("name") or "Unnamed",
						"labels": v.get("labels") or None,
					})
				if not voices:
					# fallback к дефолту, чтобы бот не падал
					voices = [{"id": settings.default_voice_id, "name": "Default", "labels": {}}]
				_voices_cache.set(voices)
				logger.info("Загружено голосов: %d", len(voices))
				return voices
		except RateLimitError as e:
			last_err = e
			logger.warning("Rate limited на получении голосов, попытка=%d", attempt)
		except httpx.HTTPStatusError as e:
			last_err = e
			status = e.response.status_code if e.response else 0
			if 500 <= status < 600:
				logger.warning("5xx при получении голосов, попытка=%d", attempt)
				continue
			else:
				break
		except httpx.HTTPError as e:
			last_err = e
			logger.warning("HTTP ошибка при получении голосов, попытка=%d", attempt)
			continue

	# Если не удалось — вернём дефолт с логом
	logger.error("Не удалось получить голоса: %s", last_err)
	return [{"id": settings.default_voice_id, "name": "Default", "labels": {}}]


def synthesize_speech(text: str, voice_id: str, fmt: str = "mp3") -> bytes:
	"""
	Генерация аудио байтов через ElevenLabs. Валидация длины, ретраи на 429/5xx.
	"""
	if not text:
		raise InvalidInputError("Пустой текст")
	if len(text) > 5000:
		raise InvalidInputError("Слишком длинный текст (>5000)")

	settings = get_settings()
	backoffs = [0.5, 1.0, 2.0]
	last_err: Optional[Exception] = None

	payload = {
		"text": text,
		"model_id": "eleven_multilingual_v2",
		"voice_settings": {
			"stability": 0.5,
			"similarity_boost": 0.75,
		},
	}
	headers = {
		"xi-api-key": settings.elevenlabs_api_key,
		"Accept": "audio/mpeg" if fmt == "mp3" else "application/json",
		"Content-Type": "application/json",
	}

	for attempt, backoff in enumerate([0.0] + backoffs):
		if backoff:
			time.sleep(backoff)
		try:
			with httpx.Client(timeout=15.0) as client:
				url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
				resp = client.post(url, json=payload, headers=headers)
				if resp.status_code == 429:
					raise RateLimitError("Rate limited")
				resp.raise_for_status()
				content = resp.content
				logger.info("Синтез успешен, bytes=%d", len(content))
				return content
		except RateLimitError as e:
			last_err = e
			logger.warning("Rate limited на синтезе, попытка=%d", attempt)
			continue
		except httpx.HTTPStatusError as e:
			last_err = e
			status = e.response.status_code if e.response else 0
			if 500 <= status < 600:
				logger.warning("5xx на синтезе, попытка=%d", attempt)
				continue
			else:
				break
		except httpx.HTTPError as e:
			last_err = e
			logger.warning("HTTP ошибка на синтезе, попытка=%d", attempt)
			continue

	logger.error("Синтез не удался: %s", last_err)
	raise VoiceServiceError("Не удалось сгенерировать аудио. Попробуйте позже.")


"""
Пример использования ElevenLabs SDK (из ТЗ):

from elevenlabs import ElevenLabs

client = ElevenLabs(
	api_key="YOUR_API_KEY",
)
client.service_accounts.api_keys.create(
	service_account_user_id="service_account_user_id",
	name="name",
	permissions=["text_to_speech"],
)
"""
