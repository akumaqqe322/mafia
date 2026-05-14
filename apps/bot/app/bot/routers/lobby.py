from uuid import uuid4

from aiogram import F, Router, types
from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError
from aiogram.filters import Command

from app.bot.callbacks import LobbyCallback
from app.bot.keyboards.lobby import build_lobby_keyboard
from app.bot.presets import select_preset_for_players
from app.bot.keyboards.night_action import build_night_action_keyboard
from app.bot.renderers.game import render_game_started
from app.bot.renderers.lobby import render_lobby
from app.bot.renderers.role import render_role_dm
from app.bot.renderers.night_action import render_night_action_dm
from app.bot.utils import build_join_url
from app.core.game.actions import get_allowed_night_actions
from app.core.game.engine import (
    GameAlreadyExistsError,
    GameNotFoundError,
    InvalidGamePhaseError,
    NotEnoughPlayersError,
    PlayerNotInGameError,
)
from app.core.game.roles import RoleId
from app.core.game.schemas import GamePhase
from app.infrastructure.container import Container

router = Router()


def _get_callback_message(
    callback: types.CallbackQuery,
) -> types.Message | None:
    """Safely extracts message from callback query."""
    if isinstance(callback.message, types.Message):
        return callback.message
    return None


@router.message(Command("game"))
async def cmd_game(message: types.Message, container: Container) -> None:
    """Handles /game command to create a lobby."""
    if not message.chat or message.chat.type not in ("group", "supergroup"):
        await message.answer("Please use this command in a group chat.")
        return

    if not message.from_user:
        return

    tg_chat_id = message.chat.id

    async with container.db.get_session() as session:
        chat_repo = container.get_chat_repository(session)

        chat = await chat_repo.get_or_create(
            telegram_chat_id=tg_chat_id,
            title=message.chat.title,
            chat_type=message.chat.type,
        )
        await session.commit()

        game_id = uuid4()
        try:
            state = await container.game_engine.create_game(
                game_id=game_id,
                chat_id=chat.id,
                telegram_chat_id=tg_chat_id,
            )

            # Create invite token
            token = await container.game_invite_repository.create_invite(game_id)
            bot_info = await message.bot.get_me() if message.bot else None
            bot_username = bot_info.username if bot_info else "mafia_bot"
            invite_url = build_join_url(bot_username, token)

            sent = await message.answer(
                render_lobby(state),
                reply_markup=build_lobby_keyboard(invite_url),
                parse_mode="HTML",
            )

            # Save lobby message id
            state.lobby_message_id = sent.message_id
            await container.game_repository.save(state)
        except GameAlreadyExistsError:
            await message.answer("An active game already exists in this chat!")


@router.callback_query(F.data == LobbyCallback.JOIN.value)
async def handle_join(callback: types.CallbackQuery) -> None:
    """Inform user they must join via private message deep-link."""
    await callback.answer(
        "Нажми кнопку Join со ссылкой, чтобы открыть ЛС с ботом и войти в игру.",
        show_alert=True,
    )


@router.callback_query(F.data == LobbyCallback.LEAVE.value)
async def handle_leave(callback: types.CallbackQuery, container: Container) -> None:
    message = _get_callback_message(callback)
    if message is None or not callback.from_user:
        if not callback.from_user:
            return
        await callback.answer(
            "This lobby message is no longer available.",
            show_alert=True,
        )
        return

    tg_chat_id = message.chat.id
    active_game_id = await container.active_game_registry.get_active_game_by_chat(
        tg_chat_id
    )

    if not active_game_id:
        await callback.answer("No active game found.", show_alert=True)
        return

    async with container.db.get_session() as session:
        user_repo = container.get_user_repository(session)
        user = await user_repo.get_by_telegram_id(callback.from_user.id)
        if not user:
            await callback.answer("You are not in the game!", show_alert=True)
            return

    try:
        state = await container.game_engine.leave_game(
            game_id=active_game_id,
            user_id=user.id,
        )

        # Get invite URL
        token = await container.game_invite_repository.create_invite(active_game_id)
        bot_info = await message.bot.get_me() if message.bot else None
        bot_username = bot_info.username if bot_info else "mafia_bot"
        invite_url = build_join_url(bot_username, token)

        await message.edit_text(
            render_lobby(state),
            reply_markup=build_lobby_keyboard(invite_url),
            parse_mode="HTML",
        )
        await callback.answer("You left the game.")
    except PlayerNotInGameError:
        await callback.answer("You are not in the game!", show_alert=True)
    except InvalidGamePhaseError:
        await callback.answer("You can only leave during lobby phase!", show_alert=True)
    except GameNotFoundError:
        await callback.answer("Game not found.", show_alert=True)


@router.callback_query(F.data == LobbyCallback.CANCEL.value)
async def handle_cancel(callback: types.CallbackQuery, container: Container) -> None:
    message = _get_callback_message(callback)
    if message is None:
        await callback.answer(
            "This lobby message is no longer available.",
            show_alert=True,
        )
        return

    # TODO: restrict to creator or admin
    tg_chat_id = message.chat.id
    active_game_id = await container.active_game_registry.get_active_game_by_chat(
        tg_chat_id
    )

    if not active_game_id:
        await callback.answer("No active game found.", show_alert=True)
        return

    # Cleanup invite
    await container.game_invite_repository.delete_by_game_id(active_game_id)

    await container.game_engine.cancel_game(active_game_id)
    await message.edit_text("🚫 Game canceled.")
    await callback.answer("Game canceled.")


@router.callback_query(F.data == LobbyCallback.START.value)
async def handle_start(callback: types.CallbackQuery, container: Container) -> None:
    message = _get_callback_message(callback)
    if message is None:
        await callback.answer(
            "This lobby message is no longer available.",
            show_alert=True,
        )
        return

    tg_chat_id = message.chat.id
    active_game_id = await container.active_game_registry.get_active_game_by_chat(
        tg_chat_id
    )

    if not active_game_id:
        await callback.answer("Лобби устарело или игра не найдена.", show_alert=True)
        return

    state = await container.game_repository.get(active_game_id)
    if state is None:
        await callback.answer("Игра не найдена.", show_alert=True)
        return

    if state.phase != GamePhase.LOBBY:
        await callback.answer("Игра уже началась!", show_alert=True)
        return

    players_count = len(state.players)
    if players_count == 0:
        await callback.answer("В лобби пока нет игроков!", show_alert=True)
        return

    preset_id = select_preset_for_players(players_count)
    if preset_id is None:
        await callback.answer(
            f"Недостаточно игроков ({players_count}) для доступных режимов.",
            show_alert=True,
        )
        return

    bot = callback.bot
    if bot is None:
        await callback.answer("Bot instance unavailable.", show_alert=True)
        return

    try:
        # 1. Start game in engine
        started_state = await container.game_engine.start_game(
            active_game_id, preset_id
        )

        # 2. Cleanup invite token
        await container.game_invite_repository.delete_by_game_id(active_game_id)

        # 3. Send roles and action menus
        # TODO: strict DM validation before start / remove blocked players
        dm_failed_players = []
        for player in started_state.players:
            # Always map player to game for DM interactions
            await container.player_game_repository.set_active_game(
                player.telegram_id, active_game_id
            )

            if player.role is None:
                continue

            try:
                role_id = RoleId(player.role)
            except ValueError:
                dm_failed_players.append(player.display_name)
                continue

            try:
                # Send Role DM
                await bot.send_message(
                    chat_id=player.telegram_id,
                    text=render_role_dm(role_id),
                    parse_mode="HTML",
                )

                # Send Night Action Menu if player has actions
                allowed_actions = get_allowed_night_actions(role_id)
                if allowed_actions and player.is_alive:
                    # For MVP, we only send the first allowed action menu if there are many.
                    # Usually there's only one.
                    action_type = list(allowed_actions)[0]
                    await bot.send_message(
                        chat_id=player.telegram_id,
                        text=render_night_action_dm(action_type),
                        reply_markup=build_night_action_keyboard(
                            started_state, player, action_type
                        ),
                        parse_mode="HTML",
                    )
            except (TelegramForbiddenError, TelegramAPIError):
                dm_failed_players.append(player.display_name)

        # 4. Update group message
        group_text = render_game_started(
            started_state,
            dm_failed=bool(dm_failed_players),
        )

        await message.edit_text(
            text=group_text,
            reply_markup=None,
            parse_mode="HTML",
        )
        await callback.answer("Игра началась!")

    except NotEnoughPlayersError:
        await callback.answer("Недостаточно игроков!", show_alert=True)
    except InvalidGamePhaseError:
        await callback.answer("Игра уже началась!", show_alert=True)
    except GameNotFoundError:
        await callback.answer("Игра не найдена.", show_alert=True)
