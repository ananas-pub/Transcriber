# Telegram‑бот для транскрибации аудио и видео

Бот принимает голосовые сообщения, видео‑кружки, видео и аудиофайлы и возвращает их расшифровку на русском языке.

## Попробовать

Демо‑бот работает здесь:

[![Transcriber](https://img.shields.io/badge/Transcriber-blue?logo=telegram)](https://t.me/ultrageniustranscriberbot)

## Что умеет

- Расшифровывает голосовые сообщения (OGG/Opus), кружки, обычные видео и аудиофайлы (mp3/m4a/ogg/wav).
- Из видео вытаскивает звук через `ffmpeg`, обработка асинхронная.
- Временные файлы удаляет сам, в том числе при ошибке.

## Стек

- `Python`, асинхронные хэндлеры
- `python-telegram-bot` для Telegram Bot API
- `openai`, клиент к OpenAI API (модель `whisper-1`)
- `ffmpeg` для извлечения аудио из видео (16 kHz, mono, 64 kbps)
- `Docker`, есть Dockerfile и compose.yaml

## Как это работает

1. Пользователь отправляет боту голосовое, кружок, видео или аудиофайл.
2. Бот скачивает медиа во временную директорию под случайным именем (UUID), чтобы файлы разных пользователей не пересекались.
3. Если это видео или кружок, извлекает аудио через `ffmpeg` в `.mp3` (16 kHz, mono).
4. Отправляет аудио в OpenAI Whisper (`whisper-1`) с указанием языка `ru`.
5. Возвращает текст пользователю. Ответы длиннее 4096 символов режутся на несколько сообщений. Временные файлы удаляются.

Ограничение: файлы до ~20 МБ (лимит Telegram Bot API). Ключевые этапы и ошибки пишутся в лог; при ошибке пользователь получает сообщение, а временные файлы удаляются.

## Быстрый старт

### Вариант A: Docker

```bash
# Сборка образа
docker build -t transcriber-bot .

# Запуск с .env файлом
docker run -d --env-file .env --name transcriber transcriber-bot

# Либо напрямую
docker run -d \
  -e TELEGRAM_TOKEN="<your_bot_token>" \
  -e OPENAI_API_KEY="<your_openai_key>" \
  --name transcriber \
  transcriber-bot
```

### Вариант B: локально

```bash
# Зависимости Python
pip install -r requirements.txt

# Установите ffmpeg, если не установлен
# Ubuntu/Debian
sudo apt-get update && sudo apt-get install -y ffmpeg
# macOS (Homebrew)
brew install ffmpeg

cp .env.example .env  # отредактируйте значения

# Запуск бота
python bot.py
```

## Переменные окружения

- `TELEGRAM_TOKEN`: токен бота от @BotFather
- `OPENAI_API_KEY`: ключ OpenAI API

Удобнее хранить их в `.env`:

```env
TELEGRAM_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

## Лицензия

MIT — см. [LICENSE](LICENSE).
