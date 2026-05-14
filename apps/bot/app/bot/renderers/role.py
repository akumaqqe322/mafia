import html

from app.core.game.roles import RoleId, RoleRegistry


def render_role_dm(role_id: RoleId) -> str:
    """Renders the private message sent to a player when the game starts."""
    role = RoleRegistry.get(role_id)
    name = html.escape(role.name)
    description = html.escape(role.description)

    return (
        f"🎭 <b>Твоя роль: {role.emoji} {name}</b>\n\n"
        f"📝 <i>{description}</i>\n\n"
        "🌑 Сейчас ночь. Если у твоей роли есть действие, оно появится следующим этапом.\n"
        "⚠️ Не раскрывай свою роль в общем чате!"
    )
