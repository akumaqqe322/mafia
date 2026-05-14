from aiogram import Router
from .lobby import router as lobby_router
from .private import router as private_router

router = Router()
router.include_router(lobby_router)
router.include_router(private_router)
