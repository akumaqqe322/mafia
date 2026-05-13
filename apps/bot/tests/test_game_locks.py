import asyncio
from uuid import UUID, uuid4

import pytest

from app.core.game.locks import GameLockManager


@pytest.mark.asyncio
async def test_sequential_execution_for_same_game() -> None:
    manager = GameLockManager()
    game_id = uuid4()
    execution_order = []

    async def task(name: str, delay: float) -> None:
        async with manager.lock(game_id):
            # simulate work
            await asyncio.sleep(delay)
            execution_order.append(name)

    # Start task1 which takes longer but starts first
    t1 = asyncio.create_task(task("first", 0.1))
    # Wait a tiny bit to ensure t1 is scheduled first
    await asyncio.sleep(0.01)
    # Start task2 which is shorter
    t2 = asyncio.create_task(task("second", 0.01))
    
    await asyncio.gather(t1, t2)
    
    # Because they share game_id, the order must be preserved
    assert execution_order == ["first", "second"]


@pytest.mark.asyncio
async def test_parallel_execution_for_different_games() -> None:
    manager = GameLockManager()
    game1 = uuid4()
    game2 = uuid4()
    execution_order = []

    async def task(name: str, game_id: UUID, delay: float) -> None:
        async with manager.lock(game_id):
            await asyncio.sleep(delay)
            execution_order.append(name)

    # task1 has a longer delay
    t1 = asyncio.create_task(task("long", game1, 0.1))
    # task2 is shorter and has a different game_id
    t2 = asyncio.create_task(task("short", game2, 0.01))
    
    await asyncio.gather(t1, t2)
    
    # "short" task should have finished first because different game_ids don't block
    assert execution_order == ["short", "long"]


@pytest.mark.asyncio
async def test_lock_reuse() -> None:
    manager = GameLockManager()
    game_id = uuid4()
    
    lock1 = await manager.get_lock(game_id)
    lock2 = await manager.get_lock(game_id)
    
    # Should yield the exact same Lock object
    assert lock1 is lock2
