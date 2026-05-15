import logging
from uuid import UUID

from app.core.game.engine import GameEngine
from app.core.game.schemas import GameState
from app.infrastructure.repositories.redis_game_repository import RedisGameStateRepository
from app.workers.protocols import GameNotifier

logger = logging.getLogger(__name__)


def should_notify_phase_change(
    old_state: GameState | None,
    new_state: GameState,
) -> bool:
    """
    Returns True if we should notify about a phase change or significant event.
    """
    if old_state is None:
        return True

    return old_state.phase != new_state.phase


class GameTickService:
    def __init__(
        self,
        game_engine: GameEngine,
        state_repository: RedisGameStateRepository,
        notifier: GameNotifier | None = None,
    ) -> None:
        self.game_engine = game_engine
        self.state_repository = state_repository
        self.notifier = notifier

    async def advance_game(self, game_id: UUID) -> GameState | None:
        """
        Advances game to next phase, notifies if changed.
        Returns the new state or None if old state missing.
        """
        old_state = await self.state_repository.get(game_id)
        if old_state is None:
            return None

        new_state = await self.game_engine.tick_game(game_id)

        if self.notifier and should_notify_phase_change(old_state, new_state):
            try:
                await self.notifier.notify_phase_change(old_state, new_state)
            except Exception:
                logger.exception("Error notifying phase change for game %s", game_id)

        return new_state
