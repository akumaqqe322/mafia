from app.core.game.actions import NightActionType


def render_night_action_dm(action_type: NightActionType) -> str:
    """Renders the instruction message for a night action."""
    mapping = {
        NightActionType.KILL: "🔫 <b>Выберите цель для устранения:</b>",
        NightActionType.HEAL: "💊 <b>Выберите, кого хотите вылечить:</b>",
        NightActionType.CHECK: "🔍 <b>Выберите игрока для проверки:</b>",
        NightActionType.BLOCK: "💋 <b>Выберите, кого хотите заблокировать:</b>",
        NightActionType.PROTECT: "🛡️ <b>Выберите, кого хотите защитить:</b>",
        NightActionType.OBSERVE: "🔭 <b>Выберите, за кем хотите последить:</b>",
    }

    return mapping.get(action_type, "❓ <b>Выберите цель действия:</b>")
