from aiogram import Router
from .lobby import router as lobby_router
from .private import router as private_router
from .day_vote import router as day_vote_router

router = Router()
router.include_router(lobby_router)
router.include_router(private_router)
router.include_router(day_vote_router)
