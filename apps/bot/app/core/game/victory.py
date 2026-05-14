from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field

from app.core.game.roles import RoleId
from app.core.game.schemas import GameState


class WinnerSide(str, Enum):
    CIVILIANS = "civilians"
    MAFIA = "mafia"
    MANIAC = "maniac"
    DRAW = "draw"
    NONE = "none"


class VictoryCheckResult(BaseModel):
    winner_side: WinnerSide
    reason: str
    winning_player_ids: list[UUID] = Field(default_factory=list)
    alive_counts: dict[str, int] = Field(default_factory=dict)


class VictoryConditionService:
    @staticmethod
    def check(state: GameState) -> VictoryCheckResult:
        town_alive: list[UUID] = []
        mafia_alive: list[UUID] = []
        maniac_alive: list[UUID] = []
        independent_alive: list[UUID] = []

        town_all: list[UUID] = []
        mafia_all: list[UUID] = []
        maniac_all: list[UUID] = []

        faction_mapping = {
            RoleId.CIVILIAN: "town",
            RoleId.SHERIFF: "town",
            RoleId.SERGEANT: "town",
            RoleId.DOCTOR: "town",
            RoleId.LOVER: "town",
            RoleId.HOBO: "town",
            RoleId.LUCKY: "town",
            RoleId.KAMIKAZE: "town",
            RoleId.MAFIA: "mafia",
            RoleId.DON: "mafia",
            RoleId.LAWYER: "mafia",
            RoleId.MANIAC: "maniac",
            RoleId.SUICIDE: "independent",
        }

        for p in state.players:
            if not p.role:
                continue

            try:
                role_id = RoleId(p.role)
            except ValueError:
                continue

            faction = faction_mapping.get(role_id)
            if not faction:
                continue

            # Track all members for winning list
            if faction == "town":
                town_all.append(p.user_id)
            elif faction == "mafia":
                mafia_all.append(p.user_id)
            elif faction == "maniac":
                maniac_all.append(p.user_id)

            # Track alive members for victory conditions
            if p.is_alive:
                if faction == "town":
                    town_alive.append(p.user_id)
                elif faction == "mafia":
                    mafia_alive.append(p.user_id)
                elif faction == "maniac":
                    maniac_alive.append(p.user_id)
                elif faction == "independent":
                    independent_alive.append(p.user_id)

        alive_total = (
            len(town_alive)
            + len(mafia_alive)
            + len(maniac_alive)
            + len(independent_alive)
        )

        counts = {
            "town": len(town_alive),
            "mafia": len(mafia_alive),
            "maniac": len(maniac_alive),
            "independent": len(independent_alive),
            "total": alive_total,
        }

        # A. DRAW
        if alive_total == 0:
            return VictoryCheckResult(
                winner_side=WinnerSide.DRAW,
                reason="all_players_dead",
                winning_player_ids=[],
                alive_counts=counts,
            )

        # B. MANIAC WIN
        if len(maniac_alive) > 0 and len(mafia_alive) == 0 and len(town_alive) <= 1:
            return VictoryCheckResult(
                winner_side=WinnerSide.MANIAC,
                reason="maniac_last_threat",
                winning_player_ids=maniac_all,
                alive_counts=counts,
            )

        # C. CIVILIANS WIN
        if len(mafia_alive) == 0 and len(maniac_alive) == 0:
            return VictoryCheckResult(
                winner_side=WinnerSide.CIVILIANS,
                reason="all_threats_eliminated",
                winning_player_ids=town_all,
                alive_counts=counts,
            )

        # D. MAFIA WIN
        if (
            len(mafia_alive) > 0
            and len(maniac_alive) == 0
            and len(mafia_alive) >= len(town_alive)
        ):
            return VictoryCheckResult(
                winner_side=WinnerSide.MAFIA,
                reason="mafia_parity",
                winning_player_ids=mafia_all,
                alive_counts=counts,
            )

        # E. NONE
        return VictoryCheckResult(
            winner_side=WinnerSide.NONE,
            reason="game_continues",
            winning_player_ids=[],
            alive_counts=counts,
        )
