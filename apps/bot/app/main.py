import asyncio
import structlog
from aiogram import Bot, Dispatcher
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.bot.handlers import router
from app.infrastructure.container import container

async def main() -> None:
    # Setup logging
    setup_logging()
    log = structlog.get_logger()
    settings = get_settings()

    # Check infrastructure
    await container.db.check_connection()
    await container.redis.check_connection()

    bot = Bot(token=settings.BOT_TOKEN.get_secret_value())
    dp = Dispatcher()
    dp.include_router(router)

    log.info("Starting bot...", environment=settings.ENVIRONMENT)
    try:
        await dp.start_polling(bot)
    finally:
        await container.redis.close()
        await container.db.close()
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
