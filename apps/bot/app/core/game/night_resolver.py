from uuid import UUID
from pydantic import BaseModel
from app.core.game.roles import RoleId
from app.core.game.schemas import GameState
from app.core.game.actions import deserialize_night_actions, NightActionType


class NightCheckResult(BaseModel):
    actor_user_id: UUID
    target_user_id: UUID
    target_role: RoleId
    is_mafia: bool


class NightResolutionResult(BaseModel):
    killed_user_ids: list[UUID] = []
    saved_user_ids: list[UUID] = []
    checks: list[NightCheckResult] = []
    summary_events: list[str] = []


class NightResolver:
    @staticmethod
    def resolve(state: GameState) -> NightResolutionResult:
        actions = deserialize_night_actions(state.night_actions)

        killed_targets: set[UUID] = set()
        healed_targets: set[UUID] = set()
        checks: list[NightCheckResult] = []

        for action in actions:
            if action.target_user_id is None:
                continue

            if action.action_type == NightActionType.KILL:
                killed_targets.add(action.target_user_id)
            elif action.action_type == NightActionType.HEAL:
                healed_targets.add(action.target_user_id)
            elif action.action_type == NightActionType.CHECK:
                target = next(
                    (p for p in state.players if p.user_id == action.target_user_id),
                    None,
                )
                if target and target.role:
                    try:
                        role_id = RoleId(target.role)
                        is_mafia = role_id in {RoleId.MAFIA, RoleId.DON, RoleId.LAWYER}
                        checks.append(
                            NightCheckResult(
                                actor_user_id=action.actor_user_id,
                                target_user_id=action.target_user_id,
                                target_role=role_id,
                                is_mafia=is_mafia,
                            )
                        )
                    except ValueError:
                        # Should not happen with valid state
                        continue

        final_killed: list[UUID] = []
        final_saved: list[UUID] = []

        # Simple kill/heal logic
        for kill_target in killed_targets:
            if kill_target in healed_targets:
                final_saved.append(kill_target)
            else:
                final_killed.append(kill_target)

        return NightResolutionResult(
            killed_user_ids=final_killed,
            saved_user_ids=final_saved,
            checks=checks,
        )
