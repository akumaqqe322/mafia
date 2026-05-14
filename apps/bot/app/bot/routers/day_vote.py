from aiogram import F, Router, types

from app.bot.callbacks import DayVoteCallback
from app.core.game.engine import (
    GameNotFoundError,
    InvalidGamePhaseError,
    InvalidVoteError,
    PlayerNotAliveError,
    PlayerNotInGameError,
)
from app.core.game.schemas import GamePhase
from app.infrastructure.container import Container

router = Router()


def _get_callback_message(callback: types.CallbackQuery) -> types.Message | None:
    if isinstance(callback.message, types.Message):
        return callback.message
    return None


@router.callback_query(F.data.startswith("dv:"))
async def handle_day_vote(
    callback: types.CallbackQuery,
    container: Container,
) -> None:
    """Handles day voting callback."""
    if not callback.from_user:
        return

    if callback.data is None:
        await callback.answer("Некорректное голосование.", show_alert=True)
        return

    parsed = DayVoteCallback.parse(callback.data)
    if parsed is None:
        await callback.answer("Некорректное голосование.", show_alert=True)
        return

    message = _get_callback_message(callback)
    if message is None:
        await callback.answer(
            "Это сообщение голосования больше недоступно.",
            show_alert=True,
        )
        return

    tg_chat_id = message.chat.id
    active_game_id = await container.active_game_registry.get_active_game_by_chat(
        tg_chat_id
    )
    if not active_game_id:
        await callback.answer("Активная игра не найдена.", show_alert=True)
        return

    state = await container.game_repository.get(active_game_id)
    if state is None:
        await callback.answer("Игра не найдена.", show_alert=True)
        return

    if state.phase != GamePhase.VOTING:
        await callback.answer("Сейчас голосование недоступно.", show_alert=True)
        return

    voter = next(
        (p for p in state.players if p.telegram_id == callback.from_user.id),
        None,
    )
    if voter is None:
        await callback.answer("Ты не участвуешь в этой игре.", show_alert=True)
        return

    if not voter.is_alive:
        await callback.answer("Мертвые игроки не голосуют.", show_alert=True)
        return

    target = next(
        (p for p in state.players if p.telegram_id == parsed.target_telegram_id),
        None,
    )
    if target is None:
        await callback.answer("Цель голосования не найдена.", show_alert=True)
        return

    if not target.is_alive:
        await callback.answer("За этого игрока уже нельзя голосовать.", show_alert=True)
        return

    if target.telegram_id == voter.telegram_id:
        await callback.answer("Нельзя голосовать за себя.", show_alert=True)
        return

    try:
        await container.game_engine.submit_day_vote(
            game_id=active_game_id,
            voter_user_id=voter.user_id,
            target_user_id=target.user_id,
        )
        await callback.answer(
            f"✅ Голос за {target.display_name} принят.",
            show_alert=False,
        )
    except GameNotFoundError:
        await callback.answer("Игра не найдена.", show_alert=True)
    except InvalidGamePhaseError:
        await callback.answer("Сейчас голосование недоступно.", show_alert=True)
    except PlayerNotInGameError:
        await callback.answer("Ты не участвуешь в этой игре.", show_alert=True)
    except PlayerNotAliveError:
        await callback.answer("Мертвые игроки не голосуют.", show_alert=True)
    except InvalidVoteError:
        await callback.answer("Голос не принят.", show_alert=True)
