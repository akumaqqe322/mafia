from aiogram import Router, types
from aiogram.filters import CommandStart

router = Router()


@router.message(CommandStart())
async def cmd_start(message: types.Message) -> None:
    """Handles /start command."""
    await message.answer(
        "Welcome to Mafia Bot! 🕵️‍♂️\n\n"
        "To start a game, add me to a group and type /game."
    )
