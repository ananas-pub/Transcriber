import asyncio
import logging
import os
import shutil
import tempfile
from pathlib import Path
from typing import List

from dotenv import load_dotenv
from openai import AsyncOpenAI
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN") or exit("TELEGRAM_TOKEN не задан — см. .env.example")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY") or exit("OPENAI_API_KEY не задан — см. .env.example")

if shutil.which("ffmpeg") is None:
    logger.warning("ffmpeg не найден в PATH — обработка видео может не работать")

client = AsyncOpenAI(api_key=OPENAI_API_KEY)

MAX_VIDEO_BYTES = 20 * 1024 * 1024  # ограничение Telegram Bot API на скачивание

def _split_text(text: str, limit: int = 4000) -> List[str]:
    """Разбивает длинный текст на части, безопасные для Telegram (<=4096)."""
    chunks: List[str] = []
    start = 0
    while start < len(text):
        end = min(start + limit, len(text))
        # стараться резать по пробелам/строкам
        if end < len(text):
            cut = text.rfind("\n", start, end)
            if cut == -1:
                cut = text.rfind(" ", start, end)
            if cut != -1 and cut > start:
                end = cut
        chunks.append(text[start:end])
        start = end
    return chunks or [text]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start"""
    await update.message.reply_text(
        "Transcriber - бот разработан @denisvatlin\n\nПерешлите сюда любые кружки/аудио/видео/голосовые и получите извлеченный текст."
    )


async def transcribe_audio(file_path: Path) -> str:
    """Транскрибация аудио с помощью Whisper API"""
    with open(file_path, "rb") as audio_file:
        transcript = await client.audio.transcriptions.create(
            model="whisper-1", file=audio_file, language="ru"
        )
    return transcript.text


async def extract_audio(video_path: Path, audio_path: Path) -> None:
    """Извлечение аудио из видео через ffmpeg: mp3 16kHz моно для Whisper"""
    process = await asyncio.create_subprocess_exec(
        "ffmpeg", "-i", str(video_path), "-vn", "-acodec", "libmp3lame",
        "-ar", "16000", "-ac", "1", "-b:a", "64k", "-y", str(audio_path),
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await process.communicate()
    if process.returncode != 0:
        raise RuntimeError(f"ffmpeg завершился с кодом {process.returncode}: {stderr.decode(errors='ignore')[-500:]}")


# атрибут сообщения → (подпись, нужно ли извлекать аудио)
MEDIA = {
    "voice": ("", False),
    "audio": (" аудио", False),
    "video_note": (" кружка", True),
    "video": (" видео", True),
}


async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Единый обработчик: скачать → (ffmpeg) → Whisper → ответить"""
    kind = next(k for k in MEDIA if getattr(update.message, k))
    label, is_video = MEDIA[kind]
    media = getattr(update.message, kind)

    if is_video and (media.file_size or 0) > MAX_VIDEO_BYTES:
        await update.message.reply_text("❌ Видео слишком большое. Максимальный размер: 20MB.")
        return

    message = await update.message.reply_text(f"⏳ Обрабатываю{label}...")
    context.chat_data["pending"] = message

    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "input"
        file = await media.get_file()
        await file.download_to_drive(src)
        if is_video:
            audio = Path(tmp) / "audio.mp3"
            await extract_audio(src, audio)
            src = audio
        text = await transcribe_audio(src)

    if not text:
        await message.edit_text(f"❌ Не удалось расшифровать{label or ' сообщение'}.")
        return
    chunks = _split_text(text)
    await message.edit_text(f"📝 Расшифровка{label}:\n\n{chunks[0]}")
    for part in chunks[1:]:
        await update.message.reply_text(part)


async def handle_unknown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "ℹ️ Пожалуйста, отправьте голосовое сообщение, видео-кружок или видео файл для расшифровки."
    )


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Ошибка обработки", exc_info=context.error)
    if not isinstance(update, Update) or not update.effective_message:
        return
    pending = context.chat_data.pop("pending", None)
    text = "❌ Произошла ошибка при обработке."
    if pending:
        await pending.edit_text(text)
    else:
        await update.effective_message.reply_text(text)


def main() -> None:
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO | filters.VIDEO_NOTE | filters.VIDEO, handle_media))
    app.add_handler(MessageHandler(~filters.COMMAND, handle_unknown))
    app.add_error_handler(on_error)
    logger.info("Бот запущен...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
