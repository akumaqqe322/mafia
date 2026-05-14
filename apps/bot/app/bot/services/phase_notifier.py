from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError
from aiogram.types import InlineKeyboardMarkup

from app.bot.keyboards.day_vote import build_day_vote_keyboard
from app.bot.renderers.day_vote import render_day_vote_started
from app.bot.renderers.phase import (
    render_day_started,
    render_game_finished,
    render_night_started,
)
from app.bot.services.night_actions import send_night_action_menus
from app.core.game.schemas import GamePhase, GameState
from app.infrastructure.repositories.phase_notification_repository import PhaseNotificationRepository
from app.infrastructure.repositories.player_game_repository import PlayerGameRepository


class TelegramGameNotifier:
    """
    Handles Telegram notifications for game phase changes.
    """

    def __init__(
        self,
        bot: Bot,
        player_game_repository: PlayerGameRepository,
        phase_notification_repository: PhaseNotificationRepository,
    ) -> None:
        self.bot = bot
        self.player_game_repository = player_game_repository
        self.phase_notification_repository = phase_notification_repository

    async def notify_phase_change(
        self,
        old_state: GameState | None,
        new_state: GameState,
    ) -> None:
        """
        Sends notifications to group chat (and players if needed) based on phase transition.
        Does not raise Telegram exceptions to prevent worker crashes.
        Uses PhaseNotificationRepository to avoid duplicate notifications for same version.
        """
        # Dedupe by (game_id, version)
        was_marked = await self.phase_notification_repository.try_mark_notified(
            new_state.game_id,
            new_state.version,
        )

        if not was_marked:
            # If already notified, we still want to ensure cleanup if it's FINISHED
            # (cleanup is idempotent and safe to repeat)
            if new_state.phase == GamePhase.FINISHED:
                await self._clear_player_game_mappings(new_state)
            return

        phase = new_state.phase

        if phase == GamePhase.NIGHT:
            # 1. Send action menus to active players
            failed_ids = await send_night_action_menus(self.bot, new_state)
            dm_failed = bool(failed_ids)

            # 2. Notify group
            text = render_night_started(new_state, dm_failed=dm_failed)
            await self._send_group_message(new_state, text)

        elif phase == GamePhase.DAY:
            text = render_day_started(old_state, new_state)
            await self._send_group_message(new_state, text)

        elif phase == GamePhase.VOTING:
            text = render_day_vote_started(new_state)
            keyboard = build_day_vote_keyboard(new_state)
            await self._send_group_message(
                new_state,
                text,
                reply_markup=keyboard,
            )

        elif phase == GamePhase.FINISHED:
            # 1. Notify group
            text = render_game_finished(new_state)
            await self._send_group_message(new_state, text)

            # 2. Cleanup player mappings
            await self._clear_player_game_mappings(new_state)

    async def _clear_player_game_mappings(self, state: GameState) -> None:
        """Removes active game association for all players in this game."""
        for player in state.players:
            # We don't catch exceptions here because clear_active_game (Redis)
            # is expected to be stable. Error in one player won't block others.
            await self.player_game_repository.clear_active_game(player.telegram_id)

    async def _send_group_message(
        self,
        state: GameState,
        text: str,
        reply_markup: InlineKeyboardMarkup | None = None,
    ) -> None:
        """
        Sends a message to the game's Telegram group chat.
        Handles possible Telegram errors silently.
        """
        try:
            await self.bot.send_message(
                chat_id=state.telegram_chat_id,
                text=text,
                parse_mode="HTML",
                reply_markup=reply_markup,
            )
        except (TelegramForbiddenError, TelegramAPIError):
            # Log could be added later if needed
            return
