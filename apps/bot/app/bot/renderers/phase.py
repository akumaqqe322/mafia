import html

from app.core.game.roles import RoleId, RoleRegistry
from app.core.game.schemas import GameState, PlayerState


def _format_player_with_role(player: PlayerState) -> str:
    """Formats a player's name with their revealed role and emoji."""
    name = html.escape(player.display_name)
    if player.role is None:
        return f"<b>{name}</b> — роль неизвестна"

    try:
        role_id = RoleId(player.role)
        role = RoleRegistry.get(role_id)
        role_text = f"{role.emoji} {html.escape(role.name)}"
        return f"<b>{name}</b> — {role_text}"
    except ValueError:
        return f"<b>{name}</b> — роль неизвестна"


def _render_players_section(title: str, players: list[PlayerState]) -> str:
    """Renders a section of players (e.g., survivors or deceased)."""
    if not players:
        return f"{title}\n— нет"

    lines = [f"• {_format_player_with_role(p)}" for p in players]
    return f"{title}\n" + "\n".join(lines)


def get_newly_dead_players(
    old_state: GameState,
    new_state: GameState,
) -> list[PlayerState]:
    """
    Detects players who were alive in old_state but are dead in new_state.
    """
    old_players = {p.user_id: p for p in old_state.players}
    newly_dead: list[PlayerState] = []

    for player in new_state.players:
        old_player = old_players.get(player.user_id)
        if old_player and old_player.is_alive and not player.is_alive:
            newly_dead.append(player)

    return newly_dead


def render_night_started(state: GameState, dm_failed: bool = False) -> str:
    """
    Renders message for NIGHT started.
    """
    _ = state
    msg = "<b>🌙 Наступила ночь.</b>\n\nВсе активные роли получили инструкции в личные сообщения."
    if dm_failed:
        msg += (
            "\n\n⚠️ Некоторым игрокам не удалось отправить личное сообщение. "
            "Пожалуйста, убедитесь, что вы начали диалог с ботом."
        )
    return msg


def render_day_started(
    old_state: GameState | None,
    new_state: GameState,
) -> str:
    """
    Renders message for DAY started.
    """
    msg = "<b>☀️ Наступил день!</b>\n\n"

    if old_state:
        newly_dead = get_newly_dead_players(old_state, new_state)
        if newly_dead:
            dead_names = ", ".join(
                f"<b>{html.escape(p.display_name)}</b>" for p in newly_dead
            )
            msg += f"Сегодня ночью нас покинули: {dead_names}"
        else:
            msg += "Город проснулся без потерь. Все живы!"
    else:
        msg += "Город проснулся."

    return msg


def render_voting_started(state: GameState) -> str:
    """
    Renders message for VOTING started.
    """
    _ = state
    return (
        "<b>⚖️ Началось голосование!</b>\n\n"
        "Обсудите события и выберите, кто покинет город сегодня. "
        "Само голосование будет доступно в ближайшее время."
    )


def render_game_finished(state: GameState) -> str:
    """
    Renders message for FINISHED.
    """
    winner = state.winner_side
    if winner:
        winner_text = f"Победила сторона: <b>{html.escape(winner)}</b>"
    else:
        winner_text = "Победитель не определён."

    alive_players = [p for p in state.players if p.is_alive]
    dead_players = [p for p in state.players if not p.is_alive]

    alive_section = _render_players_section("🟢 <b>Выжившие:</b>", alive_players)
    dead_section = _render_players_section("🔴 <b>Выбывшие:</b>", dead_players)

    return (
        f"<b>🏁 Игра окончена!</b>\n\n"
        f"{winner_text}\n\n"
        f"{alive_section}\n\n"
        f"{dead_section}"
    )
