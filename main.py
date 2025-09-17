from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Tuple

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
	Application,
	ApplicationBuilder,
	CallbackQueryHandler,
	CommandHandler,
	ContextTypes,
	MessageHandler,
	filters,
)

from config import get_settings
from voice import get_voices, synthesize_speech, InvalidInputError, VoiceServiceError

logger = logging.getLogger(__name__)

# Простое in-memory состояние: user_id -> {voice_id}
_user_state: Dict[int, Dict[str, Any]] = {}


def _paginate_buttons(voices: List[Dict[str, Any]], page: int, page_size: int = 8) -> Tuple[List[List[InlineKeyboardButton]], int]:
	start = page * page_size
	end = start + page_size
	page_voices = voices[start:end]
	buttons: List[List[InlineKeyboardButton]] = []
	for v in page_voices:
		label = v.get("name") or v.get("id")
		buttons.append([InlineKeyboardButton(label, callback_data=f"pick:{v['id']}")])

	total_pages = max(1, (len(voices) + page_size - 1) // page_size)
	nav: List[InlineKeyboardButton] = []
	if page > 0:
		nav.append(InlineKeyboardButton("⟵ Назад", callback_data=f"page:{page-1}"))
	if page + 1 < total_pages:
		nav.append(InlineKeyboardButton("Далее ⟶", callback_data=f"page:{page+1}"))
	nav.append(InlineKeyboardButton("Обновить", callback_data="refresh"))
	buttons.append(nav)
	return buttons, total_pages


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
	voices = get_voices()
	buttons, _ = _paginate_buttons(voices, page=0)
	if update.message:
		await update.message.reply_text(
			"Выберите голос:",
			reply_markup=InlineKeyboardMarkup(buttons),
		)


async def cmd_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
	return await cmd_start(update, context)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
	if update.message:
		await update.message.reply_text(
			"Отправьте текст для озвучки или используйте /voice для выбора голоса.",
		)


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
	query = update.callback_query
	assert query is not None
	await query.answer()

	data = query.data or ""
	if data.startswith("page:"):
		page = int(data.split(":", 1)[1])
		voices = get_voices()
		buttons, _ = _paginate_buttons(voices, page=page)
		await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))
		return

	if data == "refresh":
		voices = get_voices()
		buttons, _ = _paginate_buttons(voices, page=0)
		try:
			await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(buttons))
		except Exception:
			# Игнорируем ошибку "Message is not modified"
			pass
		return

	if data.startswith("pick:"):
		voice_id = data.split(":", 1)[1]
		user_id = query.from_user.id
		_user_state[user_id] = {"voice_id": voice_id}
		await query.edit_message_text("Голос выбран. Теперь отправьте текст для озвучки.")
		return


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
	user_id = update.effective_user.id if update.effective_user else 0
	text = update.message.text if update.message else ""

	settings = get_settings()
	voice_id = _user_state.get(user_id, {}).get("voice_id") or settings.default_voice_id

	try:
		audio_bytes = synthesize_speech(text, voice_id, fmt=settings.audio_format)
	except InvalidInputError as e:
		if update.message:
			await update.message.reply_text(str(e))
		return
	except VoiceServiceError:
		if update.message:
			await update.message.reply_text("Сервис перегружен, попробуйте позже.")
		return

	if update.message:
		try:
			# Отправляем голосовое сообщение
			if settings.send_as == "voice":
				await update.message.reply_voice(voice=audio_bytes)
			else:
				await update.message.reply_audio(audio=audio_bytes, title="TTS", filename="tts.mp3")
			
			# Отправляем файл mp3 для сохранения
			await update.message.reply_document(
				document=audio_bytes,
				filename=f"tts_{voice_id}_{len(text)}.mp3",
				caption=f"Файл: {voice_id}"
			)
		except Exception as e:
			# Fallback к audio
			try:
				await update.message.reply_audio(audio=audio_bytes, title="TTS", filename="tts.mp3")
				await update.message.reply_document(
					document=audio_bytes,
					filename=f"tts_{voice_id}_{len(text)}.mp3",
					caption=f"Файл: {voice_id}"
				)
			except Exception:
				await update.message.reply_text("Не удалось отправить аудио. Попробуйте позже.")

	await asyncio.sleep(0.05)


async def main_async() -> None:
	settings = get_settings()

	application: Application = (
		ApplicationBuilder()
		.token(settings.telegram_bot_token)
		.build()
	)

	application.add_handler(CommandHandler("start", cmd_start))
	application.add_handler(CommandHandler("voice", cmd_voice))
	application.add_handler(CommandHandler("help", cmd_help))
	application.add_handler(CallbackQueryHandler(on_callback))
	application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))

	logger.info("Бот запускается…")
	voices = get_voices()
	logger.info("Доступных голосов: %d", len(voices))

	await application.initialize()
	await application.start()
	try:
		await application.updater.start_polling(drop_pending_updates=True)
		# Ждём бесконечно, пока не прервём Ctrl+C
		await asyncio.Event().wait()
	finally:
		await application.stop()
		await application.shutdown()


if __name__ == "__main__":
	try:
		asyncio.run(main_async())
	except KeyboardInterrupt:
		pass
