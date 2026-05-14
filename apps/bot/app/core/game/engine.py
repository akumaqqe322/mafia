import random
from datetime import datetime, timedelta, timezone
from uuid import UUID

from app.core.game.actions import (
    NightAction,
    NightActionType,
    deserialize_night_actions,
    get_allowed_night_actions,
    night_action_requires_target,
    serialize_night_actions,
)
from app.core.game.assignment import RoleAssignmentService
from app.core.game.day_resolver import DayVoteResolutionResult, DayVoteResolver
from app.core.game.events import EventVisibility, GameEvent, GameEventType
from app.core.game.locks import GameLockManager
from app.core.game.night_resolver import NightResolutionResult, NightResolver
from app.core.game.roles import PresetRegistry, RoleId
from app.core.game.schemas import GamePhase, GameSettings, GameState, PlayerState
from app.core.game.victory import VictoryConditionService, WinnerSide
from app.infrastructure.repositories.active_game_registry import ActiveGameRegistry
from app.infrastructure.repositories.redis_game_repository import (
    RedisGameStateRepository,
)


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


class InvalidNightActionError(GameEngineException):
    """Night action is invalid."""
    pass


class InvalidVoteError(GameEngineException):
    """Day vote is invalid."""
    pass


class PlayerNotAliveError(GameEngineException):
    """Player is not alive."""
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
        creator_telegram_id: int | None = None,
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
            creator_telegram_id=creator_telegram_id,
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
                raise PlayerAlreadyInGameError(
                    f"User {user_id} already in game {game_id}"
                )

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
                raise InvalidGamePhaseError(
                    f"Cannot start game from {state.phase} phase"
                )

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
            state.phase_end_at = now + timedelta(
                seconds=state.settings.night_duration_sec
            )
            state.version += 1

            await self.state_repository.save(state)
            return state

    async def advance_phase(self, game_id: UUID) -> GameState:
        async with self.lock_manager.lock(game_id):
            state = await self.state_repository.get(game_id)
            if not state:
                raise GameNotFoundError(f"Game {game_id} not found")

            if state.phase == GamePhase.FINISHED:
                return state

            if state.phase == GamePhase.LOBBY:
                raise InvalidGamePhaseError(f"Cannot advance from {state.phase} phase")

            self._advance_phase_in_state(state)
            state.version += 1

            await self.state_repository.save(state)
            return state

    def _advance_phase_in_state(
        self, state: GameState, now: datetime | None = None
    ) -> None:
        """Transitions state to next phase without locks or saves."""
        if not now:
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
            await self.active_game_registry.remove_active_game(
                game_id, state.telegram_chat_id
            )

    async def submit_night_action(
        self,
        game_id: UUID,
        actor_user_id: UUID,
        action_type: NightActionType,
        target_user_id: UUID | None,
    ) -> GameState:
        async with self.lock_manager.lock(game_id):
            state = await self.state_repository.get(game_id)
            if not state:
                raise GameNotFoundError(f"Game {game_id} not found")

            if state.phase != GamePhase.NIGHT:
                raise InvalidGamePhaseError(
                    f"Cannot submit night action in {state.phase} phase"
                )

            actor = next((p for p in state.players if p.user_id == actor_user_id), None)
            if not actor:
                raise PlayerNotInGameError(
                    f"User {actor_user_id} not in game {game_id}"
                )

            if not actor.is_alive:
                raise PlayerNotAliveError(f"Actor {actor_user_id} is dead")

            if not actor.role:
                raise InvalidNightActionError(f"Actor {actor_user_id} has no role")

            try:
                actor_role = RoleId(actor.role)
            except ValueError as exc:
                raise InvalidNightActionError(
                    f"Actor {actor_user_id} has invalid role: {actor.role}"
                ) from exc

            allowed_actions = get_allowed_night_actions(actor_role)
            if action_type not in allowed_actions:
                raise InvalidNightActionError(
                    f"Action {action_type} is not allowed for role {actor_role}"
                )

            if night_action_requires_target(action_type) and target_user_id is None:
                raise InvalidNightActionError(f"Action {action_type} requires a target")

            if target_user_id:
                target = next(
                    (p for p in state.players if p.user_id == target_user_id), None
                )
                if not target:
                    raise InvalidNightActionError(f"Target {target_user_id} not in game")
                if not target.is_alive:
                    raise InvalidNightActionError(f"Target {target_user_id} is dead")

            # Create action
            new_action = NightAction(
                actor_user_id=actor_user_id,
                actor_role=actor_role,
                action_type=action_type,
                target_user_id=target_user_id,
                created_at=datetime.now(timezone.utc),
            )

            # Load and update actions
            actions = deserialize_night_actions(state.night_actions)
            # Remove existing action from this actor if any
            actions = [a for a in actions if a.actor_user_id != actor_user_id]
            actions.append(new_action)

            # Save back
            state.night_actions = serialize_night_actions(actions)
            state.version += 1

            await self.state_repository.save(state)
            return state

    def _apply_victory_to_state(
        self,
        state: GameState,
        winner_side: WinnerSide,
    ) -> None:
        """Transitions state to FINISHED."""
        state.phase = GamePhase.FINISHED
        state.phase_end_at = None
        state.winner_side = winner_side.value

    def _resolve_night_in_state(self, state: GameState) -> NightResolutionResult:
        """Core night resolution logic without locks or saves."""
        result = NightResolver.resolve(state)

        # Apply deaths
        for killed_id in result.killed_user_ids:
            player = next((p for p in state.players if p.user_id == killed_id), None)
            if player:
                player.is_alive = False

        # Clear actions for next night
        state.night_actions = {}

        # Check victory
        victory_result = VictoryConditionService.check(state)
        if victory_result.winner_side != WinnerSide.NONE:
            self._apply_victory_to_state(state, victory_result.winner_side)

        return result

    async def resolve_night(self, game_id: UUID) -> NightResolutionResult:
        async with self.lock_manager.lock(game_id):
            state = await self.state_repository.get(game_id)
            if not state:
                raise GameNotFoundError(f"Game {game_id} not found")

            if state.phase != GamePhase.NIGHT:
                raise InvalidGamePhaseError(
                    f"Cannot resolve night in {state.phase} phase"
                )

            result = self._resolve_night_in_state(state)
            state.version += 1
            await self.state_repository.save(state)

            if state.phase == GamePhase.FINISHED:
                await self.active_game_registry.remove_active_game(
                    game_id, state.telegram_chat_id
                )

            return result

    async def submit_day_vote(
        self,
        game_id: UUID,
        voter_user_id: UUID,
        target_user_id: UUID,
    ) -> GameState:
        async with self.lock_manager.lock(game_id):
            state = await self.state_repository.get(game_id)
            if not state:
                raise GameNotFoundError(f"Game {game_id} not found")

            if state.phase != GamePhase.VOTING:
                raise InvalidGamePhaseError(
                    f"Cannot submit day vote in {state.phase} phase"
                )

            voter = next((p for p in state.players if p.user_id == voter_user_id), None)
            if not voter:
                raise PlayerNotInGameError(f"Voter {voter_user_id} not in game {game_id}")

            if not voter.is_alive:
                raise PlayerNotAliveError(f"Voter {voter_user_id} is dead")

            if voter_user_id == target_user_id:
                raise InvalidVoteError("Voter cannot vote for themselves")

            target = next((p for p in state.players if p.user_id == target_user_id), None)
            if not target:
                raise InvalidVoteError(f"Target {target_user_id} not in game")

            if not target.is_alive:
                raise InvalidVoteError(f"Target {target_user_id} is dead")

            state.votes[str(voter_user_id)] = str(target_user_id)
            state.version += 1

            await self.state_repository.save(state)
            return state

    def _build_day_vote_events(
        self,
        result: DayVoteResolutionResult,
    ) -> list[GameEvent]:
        if result.executed_user_id:
            votes_count = result.vote_counts.get(result.executed_user_id, 0)
            return [
                GameEvent(
                    type=GameEventType.DAY_PLAYER_EXECUTED,
                    visibility=EventVisibility.PUBLIC,
                    target_user_id=result.executed_user_id,
                    payload={"votes_count": votes_count},
                )
            ]

        if result.is_tie:
            max_votes = max(result.vote_counts.values()) if result.vote_counts else 0
            tied_user_ids = [
                user_id
                for user_id, count in result.vote_counts.items()
                if count == max_votes
            ]
            return [
                GameEvent(
                    type=GameEventType.DAY_VOTE_TIE,
                    visibility=EventVisibility.PUBLIC,
                    related_user_ids=tied_user_ids,
                    payload={"votes_count": max_votes},
                )
            ]

        return [
            GameEvent(
                type=GameEventType.DAY_VOTE_NO_VOTES,
                visibility=EventVisibility.PUBLIC,
            )
        ]

    def _resolve_day_votes_in_state(self, state: GameState) -> DayVoteResolutionResult:
        """Core day vote resolution logic without locks or saves."""
        result = DayVoteResolver.resolve(state)

        # Build and store events
        state.last_events = self._build_day_vote_events(result)

        if result.executed_user_id:
            player = next(
                (p for p in state.players if p.user_id == result.executed_user_id),
                None,
            )
            if player:
                player.is_alive = False

        # Clear votes for next day
        state.votes = {}

        # Check victory
        victory_result = VictoryConditionService.check(state)
        if victory_result.winner_side != WinnerSide.NONE:
            self._apply_victory_to_state(state, victory_result.winner_side)

        return result

    async def resolve_day_votes(self, game_id: UUID) -> DayVoteResolutionResult:
        async with self.lock_manager.lock(game_id):
            state = await self.state_repository.get(game_id)
            if not state:
                raise GameNotFoundError(f"Game {game_id} not found")

            if state.phase != GamePhase.VOTING:
                raise InvalidGamePhaseError(
                    f"Cannot resolve day votes in {state.phase} phase"
                )

            result = self._resolve_day_votes_in_state(state)
            state.version += 1
            await self.state_repository.save(state)

            if state.phase == GamePhase.FINISHED:
                await self.active_game_registry.remove_active_game(
                    game_id, state.telegram_chat_id
                )

            return result

    async def tick_game(self, game_id: UUID) -> GameState:
        """Processes time-based phase transitions and resolutions."""
        async with self.lock_manager.lock(game_id):
            state = await self.state_repository.get(game_id)
            if not state:
                raise GameNotFoundError(f"Game {game_id} not found")

            if state.phase in (GamePhase.FINISHED, GamePhase.LOBBY):
                return state

            now = datetime.now(timezone.utc)

            if state.phase == GamePhase.NIGHT:
                self._resolve_night_in_state(state)
                if state.phase != GamePhase.FINISHED:
                    self._advance_phase_in_state(state, now)
            elif state.phase == GamePhase.DAY:
                self._advance_phase_in_state(state, now)
            elif state.phase == GamePhase.VOTING:
                self._resolve_day_votes_in_state(state)
                if state.phase != GamePhase.FINISHED:
                    self._advance_phase_in_state(state, now)

            state.version += 1
            await self.state_repository.save(state)

            if state.phase == GamePhase.FINISHED:
                await self.active_game_registry.remove_active_game(
                    game_id, state.telegram_chat_id
                )

            return state
