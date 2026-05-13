import random
from datetime import datetime, timedelta, timezone
from uuid import UUID

from app.core.game.assignment import RoleAssignmentService
from app.core.game.locks import GameLockManager
from app.core.game.roles import PresetRegistry
from app.core.game.schemas import GamePhase, GameSettings, GameState, PlayerState
from app.infrastructure.repositories.active_game_registry import ActiveGameRegistry
from app.infrastructure.repositories.redis_game_repository import RedisGameStateRepository


class GameEngineException(Exception):
    """Base exception for GameEngine errors."""
    pass


class GameAlreadyExistsError(GameEngineException):
    """Game already exists in this chat."""
    pass


class GameNotFoundError(GameEngineException):
    """Game not found."""
    pass


class PlayerAlreadyInGameError(GameEngineException):
    """Player is already in this game."""
    pass


class GameFullError(GameEngineException):
    """Game is full."""
    pass


class PlayerNotInGameError(GameEngineException):
    """Player is not in the game."""
    pass


class InvalidGamePhaseError(GameEngineException):
    """Game is in invalid phase for this action."""
    pass


class NotEnoughPlayersError(GameEngineException):
    """Not enough players to start the game."""
    pass


class GameEngine:
    def __init__(
        self,
        state_repository: RedisGameStateRepository,
        active_game_registry: ActiveGameRegistry,
        lock_manager: GameLockManager,
    ) -> None:
        self.state_repository = state_repository
        self.active_game_registry = active_game_registry
        self.lock_manager = lock_manager

    async def create_game(
        self,
        game_id: UUID,
        chat_id: UUID,
        telegram_chat_id: int,
        settings: GameSettings | None = None,
    ) -> GameState:
        # Check if active game exists in this chat
        active_id = await self.active_game_registry.get_active_game_by_chat(
            telegram_chat_id
        )
        if active_id:
            raise GameAlreadyExistsError(
                f"Game {active_id} already exists in chat {telegram_chat_id}"
            )

        resolved_settings = settings or GameSettings()
        state = GameState(
            game_id=game_id,
            chat_id=chat_id,
            telegram_chat_id=telegram_chat_id,
            phase=GamePhase.LOBBY,
            phase_started_at=datetime.now(timezone.utc),
            settings=resolved_settings,
        )

        await self.state_repository.save(state)
        await self.active_game_registry.add_active_game(game_id, telegram_chat_id)
        return state

    async def join_game(
        self,
        game_id: UUID,
        user_id: UUID,
        telegram_id: int,
        display_name: str,
    ) -> GameState:
        async with self.lock_manager.lock(game_id):
            state = await self.state_repository.get(game_id)
            if not state:
                raise GameNotFoundError(f"Game {game_id} not found")

            if state.phase != GamePhase.LOBBY:
                raise InvalidGamePhaseError(f"Cannot join game in {state.phase} phase")

            if any(p.user_id == user_id for p in state.players):
                raise PlayerAlreadyInGameError(f"User {user_id} already in game {game_id}")

            if len(state.players) >= state.settings.max_players:
                raise GameFullError(f"Game {game_id} is full")

            player = PlayerState(
                user_id=user_id,
                telegram_id=telegram_id,
                display_name=display_name,
            )
            state.players.append(player)
            state.version += 1

            await self.state_repository.save(state)
            return state

    async def start_game(self, game_id: UUID, preset_id: str) -> GameState:
        async with self.lock_manager.lock(game_id):
            state = await self.state_repository.get(game_id)
            if not state:
                raise GameNotFoundError(f"Game {game_id} not found")

            if state.phase != GamePhase.LOBBY:
                raise InvalidGamePhaseError(f"Cannot start game from {state.phase} phase")

            preset = PresetRegistry.get_by_id(preset_id)
            players_count = len(state.players)

            if players_count < preset.min_players:
                raise NotEnoughPlayersError(
                    f"Not enough players: {players_count} < {preset.min_players}"
                )

            # Note: RoleAssignmentService.build_role_deck already checks max_players
            deck = RoleAssignmentService.build_role_deck(preset, players_count)

            # Shuffle deck using cryptographically secure randomizer
            random.SystemRandom().shuffle(deck)

            # Assign roles to players
            for i, player in enumerate(state.players):
                player.role = deck[i].value

            # Update state transitions
            now = datetime.now(timezone.utc)
            state.phase = GamePhase.NIGHT
            state.phase_started_at = now
            state.phase_end_at = now + timedelta(seconds=state.settings.night_duration_sec)
            state.version += 1

            await self.state_repository.save(state)
            return state

    async def advance_phase(self, game_id: UUID) -> GameState:
        async with self.lock_manager.lock(game_id):
            state = await self.state_repository.get(game_id)
            if not state:
                raise GameNotFoundError(f"Game {game_id} not found")

            if state.phase in (GamePhase.LOBBY, GamePhase.FINISHED):
                raise InvalidGamePhaseError(f"Cannot advance from {state.phase} phase")

            now = datetime.now(timezone.utc)
            duration_sec: int

            if state.phase == GamePhase.NIGHT:
                state.phase = GamePhase.DAY
                duration_sec = state.settings.day_duration_sec
            elif state.phase == GamePhase.DAY:
                state.phase = GamePhase.VOTING
                duration_sec = state.settings.voting_duration_sec
            elif state.phase == GamePhase.VOTING:
                state.phase = GamePhase.NIGHT
                duration_sec = state.settings.night_duration_sec
            else:
                raise InvalidGamePhaseError(
                    f"Phase {state.phase} is not supported for auto-advance"
                )

            state.phase_started_at = now
            state.phase_end_at = now + timedelta(seconds=duration_sec)
            state.version += 1

            await self.state_repository.save(state)
            return state

    async def leave_game(self, game_id: UUID, user_id: UUID) -> GameState:
        async with self.lock_manager.lock(game_id):
            state = await self.state_repository.get(game_id)
            if not state:
                raise GameNotFoundError(f"Game {game_id} not found")

            if state.phase != GamePhase.LOBBY:
                raise InvalidGamePhaseError(f"Cannot leave game in {state.phase} phase")

            player_idx = next(
                (i for i, p in enumerate(state.players) if p.user_id == user_id), None
            )
            if player_idx is None:
                raise PlayerNotInGameError(f"User {user_id} not in game {game_id}")

            state.players.pop(player_idx)
            state.version += 1

            await self.state_repository.save(state)
            return state

    async def cancel_game(self, game_id: UUID) -> None:
        async with self.lock_manager.lock(game_id):
            state = await self.state_repository.get(game_id)
            if not state:
                raise GameNotFoundError(f"Game {game_id} not found")

            await self.state_repository.delete(game_id)
            await self.active_game_registry.remove_active_game(game_id, state.telegram_chat_id)
