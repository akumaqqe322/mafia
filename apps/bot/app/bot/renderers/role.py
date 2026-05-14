from app.core.game.roles import RoleId, RoleRegistry


def render_role_dm(role_id: RoleId) -> str:
    """Renders the private message sent to a player when the game starts."""
    role = RoleRegistry.get(role_id)
    
    return (
        f"🎭 <b>Твоя роль: {role.emoji} {role.name}</b>\n\n"
        f"📝 <i>{role.description}</i>\n\n"
        "🌑 Сейчас ночь. Если у твоей роли есть действие, оно появится следующим этапом.\n"
        "⚠️ Не раскрывай свою роль в общем чате!"
    )
