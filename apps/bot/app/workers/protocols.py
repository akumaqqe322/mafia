from typing import Protocol

from app.core.game.schemas import GameState


class GameNotifier(Protocol):
    """
    Protocol for game state change notifications.
    Keeps workers transport-agnostic.
    """

    async def notify_phase_change(
        self,
        old_state: GameState | None,
        new_state: GameState,
    ) -> None:
        """
        Notify about a game phase change.
        """
        ...
