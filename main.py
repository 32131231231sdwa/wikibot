import asyncio
import logging
import os
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

import database as db
from handlers import common, folders, groups, articles, editors, public, settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("TELEGRAM_TOKEN")
if not TOKEN:
    logger.error("TELEGRAM_TOKEN не задан!")
    sys.exit(1)


async def set_commands(bot: Bot):
    await bot.set_my_commands([
        BotCommand(command="start", description="Главное меню"),
    ])


async def main():
    db.init_db()
    logger.info("База данных инициализирована.")

    bot = Bot(
        token=TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    dp.include_router(common.router)
    dp.include_router(settings.router)
    dp.include_router(folders.router)
    dp.include_router(groups.router)
    dp.include_router(articles.router)
    dp.include_router(editors.router)
    dp.include_router(public.router)

    await set_commands(bot)
    logger.info("WikiBot запущен. Ожидаю сообщения...")

    # Keep-alive web server for Replit
    web_task = None
    if os.environ.get("REPLIT_DB_URL") or os.environ.get("KEEP_ALIVE"):
        web_task = asyncio.create_task(start_keepalive())

    try:
        await dp.start_polling(bot, allowed_updates=["message", "callback_query"])
    finally:
        if web_task:
            web_task.cancel()
        await bot.session.close()


async def start_keepalive():
    """Simple aiohttp keep-alive server for Replit."""
    try:
        from aiohttp import web

        async def health(request):
            return web.Response(text="WikiBot is running!")

        app = web.Application()
        app.router.add_get("/", health)
        app.router.add_get("/health", health)
        runner = web.AppRunner(app)
        await runner.setup()
        port = int(os.environ.get("PORT", 8080))
        site = web.TCPSite(runner, "0.0.0.0", port)
        await site.start()
        logger.info(f"Keep-alive сервер запущен на порту {port}")
        while True:
            await asyncio.sleep(3600)
    except ImportError:
        logger.warning("aiohttp не установлен, keep-alive недоступен.")
    except Exception as e:
        logger.error(f"Keep-alive ошибка: {e}")


if __name__ == "__main__":
    asyncio.run(main())
