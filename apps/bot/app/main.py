import asyncio
from contextlib import suppress

import structlog
from aiogram import Bot, Dispatcher

from app.bot.routers import router as bot_router
from app.bot.services import GameTickService, TelegramGameNotifier
from app.core.config import get_settings
from app.core.logging import setup_logging
from app.infrastructure.container import Container
from app.workers.phase_worker import PhaseWorker


async def main() -> None:
    # Setup logging
    setup_logging()
    log = structlog.get_logger()
    settings = get_settings()

    # Initialize container with settings
    container = Container(settings)

    # Check infrastructure
    await container.db.check_connection()
    await container.redis.check_connection()

    bot = Bot(token=settings.BOT_TOKEN.get_secret_value())
    dp = Dispatcher()
    dp.include_router(bot_router)

    # Provide container to handlers
    dp["container"] = container

    # Initialize notifier and worker
    notifier = TelegramGameNotifier(
        bot=bot,
        player_game_repository=container.player_game_repository,
        phase_notification_repository=container.phase_notification_repository,
        game_repository=container.game_repository,
    )
    game_tick_service = GameTickService(
        game_engine=container.game_engine,
        state_repository=container.game_repository,
        notifier=notifier,
    )
    dp["game_tick_service"] = game_tick_service

    phase_worker = PhaseWorker(
        game_engine=container.game_engine,
        state_repository=container.game_repository,
        active_game_registry=container.active_game_registry,
        notifier=notifier,
        tick_service=game_tick_service,
    )

    log.info("Starting bot...", environment=settings.ENVIRONMENT)

    worker_task = asyncio.create_task(phase_worker.start())
    log.info("Starting phase worker...")

    try:
        await dp.start_polling(bot)
    finally:
        log.info("Stopping phase worker...")
        phase_worker.stop()
        worker_task.cancel()
        with suppress(asyncio.CancelledError):
            await worker_task

        await container.redis.close()
        await container.db.close()
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
