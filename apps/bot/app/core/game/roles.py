from enum import Enum
from pydantic import BaseModel, Field


class MatchMode(str, Enum):
    COMPETITIVE = "competitive"
    PARTY = "party"


class RoleSide(str, Enum):
    CIVILIAN = "civilian"
    MAFIA = "mafia"
    NEUTRAL = "neutral"


class RoleId(str, Enum):
    CIVILIAN = "civilian"
    MAFIA = "mafia"
    DON = "don"
    SHERIFF = "sheriff"
    SERGEANT = "sergeant"
    DOCTOR = "doctor"
    MANIAC = "maniac"
    LOVER = "lover"
    LAWYER = "lawyer"
    SUICIDE = "suicide"
    HOBO = "hobo"
    LUCKY = "lucky"
    KAMIKAZE = "kamikaze"


class RoleMetadata(BaseModel):
    id: RoleId
    name: str
    emoji: str
    side: RoleSide
    description: str
    available_in_competitive: bool
    available_in_party: bool


class RolePreset(BaseModel):
    id: str
    mode: MatchMode
    min_players: int
    max_players: int
    role_counts: dict[RoleId, int] = Field(default_factory=dict)
    reward_eligible: bool


class RoleRegistry:
    _roles: dict[RoleId, RoleMetadata] = {
        RoleId.CIVILIAN: RoleMetadata(
            id=RoleId.CIVILIAN,
            name="Мирный житель",
            emoji="👤",
            side=RoleSide.CIVILIAN,
            description="Обычный гражданин, пытающийся вычислить мафию.",
            available_in_competitive=True,
            available_in_party=True,
        ),
        RoleId.MAFIA: RoleMetadata(
            id=RoleId.MAFIA,
            name="Мафия",
            emoji="🕵️‍♂️",
            side=RoleSide.MAFIA,
            description="Член преступной группировки, убивающий мирных жителей.",
            available_in_competitive=True,
            available_in_party=True,
        ),
        RoleId.DON: RoleMetadata(
            id=RoleId.DON,
            name="Дон",
            emoji="🎩",
            side=RoleSide.MAFIA,
            description="Глава мафии, ищет Шерифа ночью.",
            available_in_competitive=False,
            available_in_party=True,
        ),
        RoleId.SHERIFF: RoleMetadata(
            id=RoleId.SHERIFF,
            name="Шериф",
            emoji="👮‍♂️",
            side=RoleSide.CIVILIAN,
            description="Блюститель закона, проверяет игроков ночью.",
            available_in_competitive=True,
            available_in_party=True,
        ),
        RoleId.SERGEANT: RoleMetadata(
            id=RoleId.SERGEANT,
            name="Сержант",
            emoji="🎖",
            side=RoleSide.CIVILIAN,
            description="Помощник Шерифа, узнает результаты проверок после смерти Шерифа.",
            available_in_competitive=False,
            available_in_party=True,
        ),
        RoleId.DOCTOR: RoleMetadata(
            id=RoleId.DOCTOR,
            name="Доктор",
            emoji="👨‍⚕️",
            side=RoleSide.CIVILIAN,
            description="Спасает одного игрока от смерти ночью.",
            available_in_competitive=True,
            available_in_party=True,
        ),
        RoleId.MANIAC: RoleMetadata(
            id=RoleId.MANIAC,
            name="Маньяк",
            emoji="🔪",
            side=RoleSide.NEUTRAL,
            description="Одиночка, убивающий всех на своем пути.",
            available_in_competitive=False,
            available_in_party=True,
        ),
        RoleId.LOVER: RoleMetadata(
            id=RoleId.LOVER,
            name="Любовница",
            emoji="💃",
            side=RoleSide.CIVILIAN,
            description="Блокирует ночное действие выбранного игрока.",
            available_in_competitive=False,
            available_in_party=True,
        ),
        RoleId.LAWYER: RoleMetadata(
            id=RoleId.LAWYER,
            name="Адвокат",
            emoji="💼",
            side=RoleSide.MAFIA,
            description="Защищает члена мафии от проверок Шерифа.",
            available_in_competitive=False,
            available_in_party=True,
        ),
        RoleId.SUICIDE: RoleMetadata(
            id=RoleId.SUICIDE,
            name="Самоубийца",
            emoji="🧟",
            side=RoleSide.NEUTRAL,
            description="Побеждает, если его казнят на голосовании.",
            available_in_competitive=False,
            available_in_party=True,
        ),
        RoleId.HOBO: RoleMetadata(
            id=RoleId.HOBO,
            name="Бомж",
            emoji="🏚",
            side=RoleSide.CIVILIAN,
            description="Следит за игроком и узнает, кто к нему заходил ночью.",
            available_in_competitive=False,
            available_in_party=True,
        ),
        RoleId.LUCKY: RoleMetadata(
            id=RoleId.LUCKY,
            name="Везунчик",
            emoji="🍀",
            side=RoleSide.CIVILIAN,
            description="Имеет шанс выжить после первого покушения.",
            available_in_competitive=False,
            available_in_party=True,
        ),
        RoleId.KAMIKAZE: RoleMetadata(
            id=RoleId.KAMIKAZE,
            name="Камикадзе",
            emoji="💣",
            side=RoleSide.NEUTRAL,
            description="Забирает с собой того, кто его убил или казнил.",
            available_in_competitive=False,
            available_in_party=True,
        ),
    }

    @classmethod
    def get(cls, role_id: RoleId) -> RoleMetadata:
        if role_id not in cls._roles:
            raise ValueError(f"Role {role_id} not found in registry")
        return cls._roles[role_id]

    @classmethod
    def list_all(cls) -> list[RoleMetadata]:
        return list(cls._roles.values())

    @classmethod
    def list_for_mode(cls, mode: MatchMode) -> list[RoleMetadata]:
        if mode == MatchMode.COMPETITIVE:
            return [r for r in cls._roles.values() if r.available_in_competitive]
        return [r for r in cls._roles.values() if r.available_in_party]


class PresetRegistry:
    """
    Standard presets for game sessions.
    Civilians are filler roles and are not explicitly counted in role_counts.
    assignment_service will calculate: civilians = current_players - sum(role_counts).
    """
    
    COMPETITIVE_CLASSIC_5_6 = RolePreset(
        id="competitive_classic_5_6",
        mode=MatchMode.COMPETITIVE,
        min_players=5,
        max_players=6,
        role_counts={
            RoleId.MAFIA: 1,
            RoleId.SHERIFF: 1,
            RoleId.DOCTOR: 1,
        },
        reward_eligible=True,
    )
    
    COMPETITIVE_CLASSIC_7_9 = RolePreset(
        id="competitive_classic_7_9",
        mode=MatchMode.COMPETITIVE,
        min_players=7,
        max_players=9,
        role_counts={
            RoleId.MAFIA: 2,
            RoleId.SHERIFF: 1,
            RoleId.DOCTOR: 1,
        },
        reward_eligible=True,
    )
    
    PARTY_EXTENDED = RolePreset(
        id="party_extended",
        mode=MatchMode.PARTY,
        min_players=4,
        max_players=12,
        role_counts={
            RoleId.MAFIA: 2,
            RoleId.DON: 1,
            RoleId.SHERIFF: 1,
            RoleId.DOCTOR: 1,
            RoleId.MANIAC: 1,
        },
        reward_eligible=False,
    )

    @classmethod
    def list_all(cls) -> list[RolePreset]:
        return [
            cls.COMPETITIVE_CLASSIC_5_6,
            cls.COMPETITIVE_CLASSIC_7_9,
            cls.PARTY_EXTENDED,
        ]

    @classmethod
    def get_by_id(cls, preset_id: str) -> RolePreset:
        for p in cls.list_all():
            if p.id == preset_id:
                return p
        raise ValueError(f"Preset {preset_id} not found")
