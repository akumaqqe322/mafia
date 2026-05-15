from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError
from aiogram.types import InlineKeyboardMarkup

from app.bot.keyboards.day_vote import build_day_vote_keyboard
from app.bot.renderers.check_result import render_check_result
from app.bot.renderers.day_vote import render_day_vote_started
from app.bot.renderers.day_vote_result import render_day_vote_result
from app.bot.renderers.phase import (
    render_day_started,
    render_game_finished,
    render_night_started,
)
from app.bot.services.night_actions import send_night_action_menus
from app.core.game.events import EventVisibility, GameEventType
from app.core.game.schemas import GamePhase, GameState
from app.infrastructure.repositories.phase_notification_repository import PhaseNotificationRepository
from app.infrastructure.repositories.player_game_repository import PlayerGameRepository
from app.infrastructure.repositories.redis_game_repository import RedisGameStateRepository


class TelegramGameNotifier:
    """
    Handles Telegram notifications for game phase changes.
    """

    def __init__(
        self,
        bot: Bot,
        player_game_repository: PlayerGameRepository,
        phase_notification_repository: PhaseNotificationRepository,
        game_repository: RedisGameStateRepository,
    ) -> None:
        self.bot = bot
        self.player_game_repository = player_game_repository
        self.phase_notification_repository = phase_notification_repository
        self.game_repository = game_repository

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

        # Send day vote result summary if we just left VOTING phase
        await self._cleanup_voting_panel_if_needed(old_state, new_state)
        await self._send_day_vote_result_if_needed(old_state, new_state)

        # Send private check results (e.g. for Sheriff/Don) if any in last_events
        await self._send_private_check_results(new_state)

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
            await self._send_voting_panel(new_state)

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

    async def _send_private_check_results(
        self,
        state: GameState,
    ) -> None:
        """
        Sends private check results (Sheriff/Don) to the corresponding players.
        """
        for event in state.last_events:
            if event.type != GameEventType.CHECK_RESULT:
                continue
            if event.visibility != EventVisibility.PRIVATE:
                continue
            if event.recipient_user_id is None:
                continue

            recipient = next(
                (p for p in state.players if p.user_id == event.recipient_user_id),
                None,
            )
            if recipient is None:
                continue

            text = render_check_result(state, event)
            if text is None:
                continue

            try:
                await self.bot.send_message(
                    chat_id=recipient.telegram_id,
                    text=text,
                    parse_mode="HTML",
                )
            except (TelegramForbiddenError, TelegramAPIError):
                # We skip players who blocked the bot or other API errors
                continue

    async def _send_day_vote_result_if_needed(
        self,
        old_state: GameState | None,
        new_state: GameState,
    ) -> None:
        """
        Sends day vote result summary if the phase just transitioned from VOTING.
        """
        if old_state is None:
            return
        if old_state.phase != GamePhase.VOTING:
            return
        if new_state.phase == GamePhase.VOTING:
            return

        text = render_day_vote_result(new_state)
        if text:
            await self._send_group_message(new_state, text)

    async def _cleanup_voting_panel_if_needed(
        self,
        old_state: GameState | None,
        new_state: GameState,
    ) -> None:
        """
        Removes buttons from the old voting panel and updates its text.
        Called when transitioning out of VOTING phase.
        """
        if old_state is None:
            return
        if old_state.phase != GamePhase.VOTING:
            return
        if new_state.phase == GamePhase.VOTING:
            return

        # Prefer message_id from new_state (it should be persisted across phases in GameState)
        message_id = new_state.voting_message_id or old_state.voting_message_id
        if not message_id:
            return

        try:
            await self.bot.edit_message_text(
                chat_id=new_state.telegram_chat_id,
                message_id=message_id,
                text=(
                    "⚖️ <b>Голосование завершено.</b>\n\n"
                    "Результат опубликован ниже."
                ),
                parse_mode="HTML",
                reply_markup=None,
            )
        except (TelegramForbiddenError, TelegramAPIError):
            # Message might be deleted or too old, ignore errors
            return

    async def _send_voting_panel(self, state: GameState) -> None:
        """
        Sends the voting panel to the group chat and stores message_id in state.
        """
        text = render_day_vote_started(state)
        keyboard = build_day_vote_keyboard(state)

        try:
            sent = await self.bot.send_message(
                chat_id=state.telegram_chat_id,
                text=text,
                parse_mode="HTML",
                reply_markup=keyboard,
            )
        except (TelegramForbiddenError, TelegramAPIError):
            return

        # Save message ID for future cleanup
        state.voting_message_id = sent.message_id
        await self.game_repository.save(state)

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
