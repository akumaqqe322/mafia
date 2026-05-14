import html

from aiogram import F, Router, types
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import CommandObject, CommandStart

from app.bot.callbacks import NightActionCallback
from app.bot.keyboards.lobby import build_lobby_keyboard
from app.bot.keyboards.night_action import get_available_night_targets
from app.bot.renderers.lobby import render_lobby
from app.bot.utils import build_join_url
from app.core.game.actions import get_allowed_night_actions
from app.core.game.engine import (
    GameFullError,
    GameNotFoundError,
    InvalidGamePhaseError,
    InvalidNightActionError,
    PlayerAlreadyInGameError,
    PlayerNotAliveError,
    PlayerNotInGameError,
)
from app.bot.services import (
    MAFIA_CHAT_ACTIVE_PHASES,
    MAX_MAFIA_CHAT_MESSAGE_LENGTH,
    can_send_mafia_chat,
    get_mafia_chat_recipients,
    is_mafia_chat_phase,
    relay_mafia_chat_message,
    validate_mafia_chat_text,
)
from app.core.game.roles import RoleId
from app.core.game.schemas import GamePhase
from app.infrastructure.container import Container

router = Router()


@router.message(F.chat.type == "private", F.text, ~F.text.startswith("/"))
async def handle_private_text(
    message: types.Message, container: Container
) -> None:
    """Relays private text messages to mafia teammates during active game phases."""
    if not message.from_user or not message.text:
        return

    # Filter out commands just in case
    if message.text.startswith("/"):
        return

    # 1. Validate text
    text = validate_mafia_chat_text(message.text)
    if not text:
        await message.answer(
            f"Сообщение пустое или слишком длинное. Лимит — {MAX_MAFIA_CHAT_MESSAGE_LENGTH} символов."
        )
        return

    # 2. Resolve game
    game_id = await container.player_game_repository.get_active_game(
        message.from_user.id
    )
    if not game_id:
        # Ignore text from players not in game to avoid noisy "you are not in game" errors
        return

    # 3. Get state and validate phase
    state = await container.game_repository.get(game_id)
    if not state:
        await message.answer("Активная игра не найдена.")
        return

    if not is_mafia_chat_phase(state.phase):
        await message.answer("Сейчас мафиозный чат недоступен.")
        return

    # 4. Resolve sender and validate eligibility
    sender = next(
        (p for p in state.players if p.telegram_id == message.from_user.id), None
    )
    if not sender:
        await message.answer("Ты не участвуешь в этой игре.")
        return

    # Provide better feedback for dead mafia members
    is_mafia_side = sender.role in {RoleId.MAFIA.value, RoleId.DON.value}
    if is_mafia_side and not sender.is_alive:
        await message.answer("Ты уже не можешь отправлять сообщения мафии.")
        return

    if not can_send_mafia_chat(sender):
        await message.answer("Сейчас это сообщение никуда не отправлено.")
        return

    # 5. Check recipients
    recipients = get_mafia_chat_recipients(state, sender)
    if not recipients:
        await message.answer("Сейчас некому отправить сообщение.")
        return

    # 6. Relay
    bot = message.bot
    if not bot:
        return

    delivered = await relay_mafia_chat_message(bot, state, sender, text)
    if delivered > 0:
        await message.answer("✅ Сообщение отправлено союзникам.")
    else:
        await message.answer("Не удалось доставить сообщение союзникам.")


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

        await message.answer("✅ You joined the game!")

        # Update lobby message in group if exists
        if state.lobby_message_id and state.phase == GamePhase.LOBBY:
            bot = message.bot
            if bot:
                bot_info = await bot.get_me()
                bot_username = bot_info.username or "mafia_bot"
                invite_url = build_join_url(bot_username, token)

                try:
                    await bot.edit_message_text(
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


@router.callback_query(F.data.startswith(NightActionCallback.PREFIX))
async def handle_night_action(
    callback: types.CallbackQuery, container: Container
) -> None:
    """Handles night action choices made in private DM."""
    if not callback.from_user or not callback.message:
        return

    parsed = NightActionCallback.parse(callback.data or "")
    if not parsed:
        await callback.answer("Недопустимая кнопка", show_alert=True)
        return

    action_type, target_telegram_id = parsed

    # 1. Resolve game
    game_id = await container.player_game_repository.get_active_game(
        callback.from_user.id
    )
    if not game_id:
        await callback.answer("Игра не найдена.", show_alert=True)
        return

    # 2. Get state and validate actor
    state = await container.game_repository.get(game_id)
    if not state:
        await callback.answer("Игра не найдена в хранилище.", show_alert=True)
        return

    if state.phase != GamePhase.NIGHT:
        await callback.answer("Ночь уже закончилась.", show_alert=True)
        return

    actor = next(
        (p for p in state.players if p.telegram_id == callback.from_user.id), None
    )
    if not actor or not actor.is_alive:
        await callback.answer("Вы не участвуете в игре или мертвы.", show_alert=True)
        return

    # 3. Validate action and target
    try:
        role_id = RoleId(actor.role)
        allowed_actions = get_allowed_night_actions(role_id)
        if action_type not in allowed_actions:
            await callback.answer("Это действие вам недоступно.", show_alert=True)
            return
    except ValueError:
        await callback.answer("Ошибка определения вашей роли.", show_alert=True)
        return

    target = next((p for p in state.players if p.telegram_id == target_telegram_id), None)
    if not target or not target.is_alive:
        await callback.answer("Цель больше недоступна.", show_alert=True)
        return

    # Deep validation using same rules as keyboard
    available_targets = get_available_night_targets(state, actor, action_type)
    if not any(t.user_id == target.user_id for t in available_targets):
        await callback.answer("Этот выбор недопустим.", show_alert=True)
        return

    # 4. Submit action
    try:
        await container.game_engine.submit_night_action(
            game_id=game_id,
            actor_user_id=actor.user_id,
            action_type=action_type,
            target_user_id=target.user_id,
        )

        # 5. Confirmation
        safe_target_name = html.escape(target.display_name)
        await callback.answer(f"Выбор принят: {target.display_name}")

        # Update message to show current selection
        if isinstance(callback.message, types.Message):
            try:
                await callback.message.edit_text(
                    f"✅ Вы выбрали: <b>{safe_target_name}</b>\n"
                    f"<i>Вы можете изменить выбор до конца ночи.</i>",
                    parse_mode="HTML",
                )
            except TelegramAPIError:
                # Message might be too old to edit or already has this text
                pass

    except GameNotFoundError:
        await callback.answer("Игра не найдена.", show_alert=True)
    except InvalidGamePhaseError:
        await callback.answer("Ночь уже закончилась.", show_alert=True)
    except InvalidNightActionError:
        await callback.answer("Недопустимое действие.", show_alert=True)
    except PlayerNotAliveError:
        await callback.answer("Ты уже не можешь действовать.", show_alert=True)
    except PlayerNotInGameError:
        await callback.answer("Ты не участвуешь в этой игре.", show_alert=True)
