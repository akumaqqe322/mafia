from app.core.game.schemas import GameState


def render_admin_panel(state: GameState | None) -> str:
    """Renders the admin panel status message."""
    header = "⚙️ <b>Панель управления игрой</b>\n\n"

    if state is None:
        return f"{header}Активная игра не найдена."

    alive_count = len([p for p in state.players if p.is_alive])
    total_count = len(state.players)

    return (
        f"{header}"
        f"Фаза: <b>{state.phase.value}</b>\n"
        f"Версия: <b>v{state.version}</b>\n"
        f"Игроков: <b>{alive_count} живых / {total_count} всего</b>"
    )


def render_admin_kick_panel(state: GameState) -> str:
    """Renders the kick from lobby panel text."""
    header = "👥 <b>Кик из лобби</b>\n\n"

    if not state.players:
        return f"{header}В лобби пока нет игроков."

    return f"{header}Выберите игрока, которого нужно удалить из лобби."


def render_admin_finish_confirmation(state: GameState) -> str:
    """Renders the force finish confirmation screen."""
    header = "⚠️ <b>Подтвердите остановку игры</b>\n\n"

    return (
        f"{header}"
        f"Это действие немедленно завершит текущую партию.\n"
        f"Игрокам будет отправлен финальный отчёт с раскрытием ролей.\n\n"
        f"Фаза: <b>{state.phase.value}</b>\n"
        f"Версия: <b>v{state.version}</b>\n\n"
        f"<i>Отменить это действие нельзя.</i>"
    )
