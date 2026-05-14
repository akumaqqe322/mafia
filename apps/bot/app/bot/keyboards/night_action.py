from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.callbacks import NightActionCallback
from app.core.game.actions import NightActionType
from app.core.game.roles import RoleId
from app.core.game.schemas import GameState, PlayerState


def get_available_night_targets(
    state: GameState,
    actor: PlayerState,
    action_type: NightActionType,
) -> list[PlayerState]:
    """
    Returns a list of players that can be targeted by the given actor for the given action.
    """
    mafia_team = {RoleId.MAFIA.value, RoleId.DON.value, RoleId.LAWYER.value}
    targets: list[PlayerState] = []

    for target in state.players:
        if not target.is_alive:
            continue

        # Common rule: most actions exclude self
        if target.user_id == actor.user_id:
            if action_type != NightActionType.HEAL:
                continue

        # Role-specific overrides
        if action_type == NightActionType.KILL:
            # Mafia cannot kill teammates
            if actor.role in mafia_team and target.role in mafia_team:
                continue

        targets.append(target)

    return targets


def build_night_action_keyboard(
    state: GameState,
    actor: PlayerState,
    action_type: NightActionType,
) -> InlineKeyboardMarkup:
    """
    Builds a keyboard with a list of potential targets for a night action.
    Uses telegram_id in callback_data for safety.
    """
    builder = InlineKeyboardBuilder()
    targets = get_available_night_targets(state, actor, action_type)

    for target in targets:
        callback_data = NightActionCallback.build(action_type, target.telegram_id)

        builder.button(
            text=target.display_name,
            callback_data=callback_data,
        )

    builder.adjust(2)
    return builder.as_markup()
