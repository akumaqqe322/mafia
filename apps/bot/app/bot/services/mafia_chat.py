import html
from typing import Final

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError

from app.core.game.roles import RoleId
from app.core.game.schemas import GamePhase, GameState, PlayerState


MAFIA_CHAT_ROLE_VALUES: Final[set[str]] = {
    RoleId.MAFIA.value,
    RoleId.DON.value,
}

MAFIA_CHAT_ACTIVE_PHASES: Final[set[GamePhase]] = {
    GamePhase.NIGHT,
    GamePhase.DAY,
    GamePhase.VOTING,
}

MAX_MAFIA_CHAT_MESSAGE_LENGTH: Final[int] = 1000


def is_mafia_chat_phase(phase: GamePhase) -> bool:
    """Returns True if the mafia chat is available during the given phase."""
    return phase in MAFIA_CHAT_ACTIVE_PHASES


def can_send_mafia_chat(player: PlayerState) -> bool:
    """
    Returns True if the player is allowed to send messages to the mafia chat.
    Allowed only for alive Mafia or Don members.
    """
    return (
        player.is_alive
        and player.role is not None
        and player.role in MAFIA_CHAT_ROLE_VALUES
    )


def can_receive_mafia_chat(player: PlayerState) -> bool:
    """
    Returns True if the player is allowed to receive messages from the mafia chat.
    Allowed for all Mafia or Don members, including dead ones.
    """
    return player.role is not None and player.role in MAFIA_CHAT_ROLE_VALUES


def get_mafia_chat_recipients(
    state: GameState,
    sender: PlayerState,
) -> list[PlayerState]:
    """
    Returns a list of players who should receive the mafia chat message from the sender.
    Dead Mafia/Don members receive messages but cannot send them.
    Sender is excluded from the list.
    """
    if not can_send_mafia_chat(sender):
        return []

    return [
        p
        for p in state.players
        if can_receive_mafia_chat(p) and p.telegram_id != sender.telegram_id
    ]


def validate_mafia_chat_text(text: str) -> str | None:
    """
    Validates the message text for the mafia chat.
    Returns stripped text if valid, None otherwise.
    """
    stripped = text.strip()
    if not stripped:
        return None
    if len(stripped) > MAX_MAFIA_CHAT_MESSAGE_LENGTH:
        return None
    return stripped


def render_mafia_chat_message(
    sender: PlayerState,
    text: str,
) -> str:
    """
    Renders a mafia chat message for delivery to other teammates.
    Escapes HTML to prevent injection.
    """
    sender_name = html.escape(sender.display_name)
    message_text = html.escape(text)

    return (
        f"💬 Сообщение от <b>{sender_name}</b>:\n"
        f"{message_text}"
    )


async def relay_mafia_chat_message(
    bot: Bot,
    state: GameState,
    sender: PlayerState,
    text: str,
) -> int:
    """
    Sends rendered mafia chat message to recipients.
    Returns number of successful deliveries.
    """
    recipients = get_mafia_chat_recipients(state, sender)
    rendered = render_mafia_chat_message(sender, text)
    delivered_count = 0

    for recipient in recipients:
        try:
            await bot.send_message(
                chat_id=recipient.telegram_id,
                text=rendered,
                parse_mode="HTML",
            )
            delivered_count += 1
        except (TelegramForbiddenError, TelegramAPIError):
            # Skip recipients who blocked the bot or other API errors
            continue

    return delivered_count
