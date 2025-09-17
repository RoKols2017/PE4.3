# TTS Telegram Bot (ElevenLabs)

Минимальный сервис: выбор голоса и генерация аудио из текста через ElevenLabs, бот в Telegram.

Требования: Python 3.13.

## Запуск (Windows PowerShell)

```powershell
cd C:\py_project\PE4.3
# Если Python 3.13 не установлен:
# winget install Python.Python.3.13 --source winget --silent --accept-package-agreements --accept-source-agreements

py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env_example .env
# заполните .env ключами
python main.py
```

Если команда `py -3.13` недоступна, попробуйте:
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

## Переменные окружения
См. `.env_example` и `docs/TZ.md`.

## Тесты
```powershell
pytest -q
```

## Примечания
- Секреты в `.env`, не коммитить.
- При старте бот логирует количество доступных голосов.
