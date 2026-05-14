from app.core.game.schemas import GameState


def render_game_started(state: GameState, dm_failed: bool = False) -> str:
    """Renders the message sent to the group when the game starts."""
    players_count = len(state.players)

    dm_text = (
        "📩 Всем игрокам отправлены их роли в личные сообщения. Проверьте ЛС с ботом!"
        if not dm_failed
        else "⚠️ Некоторым игрокам не удалось отправить роль в ЛС. Убедитесь, что бот не заблокирован и проверьте ЛС!"
    )

    return (
        "🚀 <b>Игра началась!</b>\n\n"
        "🌑 Наступила <b>Ночь</b>.\n"
        f"👥 Игроков в игре: {players_count}\n\n"
        f"{dm_text}"
    )
