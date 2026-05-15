import asyncio
import logging
from datetime import datetime, timezone

from app.bot.services.game_tick import GameTickService, should_notify_phase_change
from app.core.game.engine import GameEngine, GameEngineException
from app.core.game.schemas import GameState
from app.infrastructure.repositories.active_game_registry import ActiveGameRegistry
from app.infrastructure.repositories.redis_game_repository import RedisGameStateRepository
from app.workers.protocols import GameNotifier

logger = logging.getLogger(__name__)


class PhaseWorker:
    def __init__(
        self,
        game_engine: GameEngine,
        state_repository: RedisGameStateRepository,
        active_game_registry: ActiveGameRegistry,
        poll_interval_sec: float = 1.0,
        notifier: GameNotifier | None = None,
    ) -> None:
        self.game_engine = game_engine
        self.state_repository = state_repository
        self.active_game_registry = active_game_registry
        self.poll_interval_sec = poll_interval_sec
        self.notifier = notifier
        self.tick_service = GameTickService(
            game_engine=game_engine,
            state_repository=state_repository,
            notifier=notifier,
        )
        self._is_running = False

    @property
    def is_running(self) -> bool:
        """Returns whether the worker loop is running."""
        return self._is_running

    async def tick(self, now: datetime | None = None) -> int:
        """
        Processes one iteration of active games.
        Returns the number of games advanced to next phase.
        """
        current_time = now or datetime.now(timezone.utc)
        game_ids = await self.active_game_registry.list_active_games()
        advanced_count = 0

        for game_id in game_ids:
            try:
                state = await self.state_repository.get(game_id)
                if not state:
                    continue

                if state.phase_end_at is None:
                    continue

                if state.phase_end_at <= current_time:
                    logger.info(
                        "Ticking game %s (expired at %s)",
                        game_id,
                        state.phase_end_at,
                    )
                    new_state = await self.tick_service.advance_game(game_id)
                    if new_state is not None:
                        advanced_count += 1
            except GameEngineException as e:
                logger.error("Error advancing game %s: %s", game_id, e)
            except Exception as e:
                logger.exception(
                    "Unexpected error in PhaseWorker for game %s: %s",
                    game_id,
                    e,
                )

        return advanced_count

    async def start(self) -> None:
        """Starts the main worker loop."""
        if self._is_running:
            return

        self._is_running = True
        logger.info("PhaseWorker started")
        while self._is_running:
            await self.tick()
            await asyncio.sleep(self.poll_interval_sec)

    def stop(self) -> None:
        """Stops the main worker loop."""
        self._is_running = False
        logger.info("PhaseWorker stopped")


def _should_notify_phase_change(
    old_state: GameState | None,
    new_state: GameState,
) -> bool:
    """
    Returns True if we should notify about a phase change or significant event.
    """
    return should_notify_phase_change(old_state, new_state)
