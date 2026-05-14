from app.core.game.schemas import GameState


def render_game_started(state: GameState) -> str:
    """Renders the message sent to the group when the game starts."""
    players_count = len(state.players)

    return (
        "🚀 <b>Игра началась!</b>\n\n"
        "🌑 Наступила <b>Ночь</b>.\n"
        f"👥 Игроков в игре: {players_count}\n\n"
        "📩 Всем игрокам отправлены их роли в личные сообщения. Проверьте ЛС с ботом!"
    )
