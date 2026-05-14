from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup

from app.core.game.schemas import GameState, PlayerState
from app.core.game.actions import NightActionType


def build_night_action_keyboard(
    state: GameState, 
    actor: PlayerState, 
    action_type: NightActionType
) -> InlineKeyboardMarkup:
    """
    Builds a keyboard with a list of potential targets for a night action.
    Target ID is the UUID of the player.
    """
    builder = InlineKeyboardBuilder()
    
    # Filter alive players
    # For most actions, actor cannot target themselves.
    # Exception: Doctor can heal themselves (by default in many mafia versions).
    # For MVP, let's allow Doctor to heal themselves if needed, 
    # but for KILL/CHECK let's exclude self.
    
    for player in state.players:
        # Skip dead players
        if not player.is_alive:
            continue
            
        # Self-target logic
        if player.user_id == actor.user_id:
            if action_type != NightActionType.HEAL:
                continue
        
        # Callback data: na:<action_type>:<target_user_id>
        callback_data = f"na:{action_type.value}:{player.user_id}"
        
        builder.button(
            text=player.display_name,
            callback_data=callback_data
        )
        
    builder.adjust(2)
    return builder.as_markup()
