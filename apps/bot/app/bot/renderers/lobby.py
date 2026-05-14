from app.core.game.schemas import GameState


def render_lobby(state: GameState) -> str:
    """Renders the lobby message."""
    players_count = len(state.players)
    max_players = state.settings.max_players
    
    players_list = ""
    if state.players:
        players_list = "\n".join(
            f"{i + 1}. {p.display_name}" for i, p in enumerate(state.players)
        )
        players_list = f"\n\n<b>Players:</b>\n{players_list}"

    text = (
        f"<b>🎮 Mafia Lobby</b>\n"
        f"Mode: <i>{state.settings.preset_id}</i>\n"
        f"Players: {players_count}/{max_players}"
        f"{players_list}\n\n"
        f"Click <b>Join</b> to enter the game!"
    )
    return text
