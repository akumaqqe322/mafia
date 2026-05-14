from app.core.game.schemas import GameState


def render_day_vote_started(state: GameState) -> str:
    """Renders the message for the start of the voting phase."""
    alive_count = sum(1 for p in state.players if p.is_alive)

    return (
        "⚖️ <b>Голосование началось.</b>\n\n"
        "Выберите игрока, которого город отправит на суд.\n"
        "Можно изменить голос до конца фазы.\n\n"
        f"Живых игроков: {alive_count}"
    )
