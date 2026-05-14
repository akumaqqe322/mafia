from aiogram import Router, types
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import CommandObject, CommandStart

from app.bot.keyboards.lobby import build_lobby_keyboard
from app.bot.renderers.lobby import render_lobby
from app.bot.utils import build_join_url
from app.core.game.engine import (
    GameFullError,
    GameNotFoundError,
    InvalidGamePhaseError,
    PlayerAlreadyInGameError,
)
from app.core.game.schemas import GamePhase
from app.infrastructure.container import Container

router = Router()


@router.message(CommandStart())
async def cmd_start(
    message: types.Message, command: CommandObject, container: Container
) -> None:
    """Handles /start command, including join deep-links."""
    if not message.from_user:
        return

    if not command.args or not command.args.startswith("join_"):
        await message.answer(
            "Welcome to Mafia Bot! 🕵️‍♂️\n\n"
            "To start a game, add me to a group and type /game."
        )
        return

    # Handle deep-link join
    token = command.args.removeprefix("join_")
    game_id = await container.game_invite_repository.get_game_id(token)

    if not game_id:
        await message.answer("This invite link is invalid or has expired.")
        return

    # Fast pre-check before DB session
    state = await container.game_repository.get(game_id)
    if state is None:
        await message.answer("Игра не найдена.")
        return

    if state.phase != GamePhase.LOBBY:
        await message.answer("Игра уже началась или завершилась.")
        return

    if len(state.players) >= state.settings.max_players:
        await message.answer("Лобби уже заполнено. Дождитесь следующего раунда.")
        return

    async with container.db.get_session() as session:
        user_repo = container.get_user_repository(session)
        user = await user_repo.get_or_create(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
        )
        await session.commit()

    try:
        display_name = (
            user.username or user.first_name or f"User {user.telegram_id}"
        )
        state = await container.game_engine.join_game(
            game_id=game_id,
            user_id=user.id,
            telegram_id=user.telegram_id,
            display_name=display_name,
        )

        await message.answer(
            f"✅ You joined the game in <b>{state.settings.preset_id}</b>!"
        )

        # Update lobby message in group if exists
        if state.lobby_message_id and state.phase == GamePhase.LOBBY:
            bot_info = await message.bot.get_me() if message.bot else None
            bot_username = bot_info.username if bot_info else "mafia_bot"
            invite_url = build_join_url(bot_username, token)

            try:
                await message.bot.edit_message_text(
                    chat_id=state.telegram_chat_id,
                    message_id=state.lobby_message_id,
                    text=render_lobby(state),
                    reply_markup=build_lobby_keyboard(invite_url),
                    parse_mode="HTML",
                )
            except TelegramAPIError:
                # Group message might have been deleted or edited by someone else
                pass

    except PlayerAlreadyInGameError:
        await message.answer("You are already in this game!")
    except GameFullError:
        await message.answer("Sorry, this game is full.")
    except InvalidGamePhaseError:
        await message.answer("This game has already started or finished.")
    except GameNotFoundError:
        await message.answer("Game not found.")
