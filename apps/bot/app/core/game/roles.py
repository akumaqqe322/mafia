from enum import Enum

from pydantic import BaseModel, Field


class MatchMode(str, Enum):
    CLASSIC = "classic"
    EXTENDED = "extended"
    FULL_HOUSE = "full_house"


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
    available_in_modes: tuple[MatchMode, ...]


class RolePreset(BaseModel):
    id: str
    mode: MatchMode
    min_players: int
    max_players: int
    role_counts: dict[RoleId, int] = Field(default_factory=dict)
    rewards_enabled: bool
    reward_multiplier: float = 1.0


class RoleRegistry:
    """
    Registry of all available roles in the platform.
    """
    _roles: dict[RoleId, RoleMetadata] = {
        RoleId.CIVILIAN: RoleMetadata(
            id=RoleId.CIVILIAN,
            name="Мирный житель",
            emoji="👤",
            side=RoleSide.CIVILIAN,
            description="Обычный гражданин, пытающийся вычислить мафию.",
            available_in_modes=(MatchMode.CLASSIC, MatchMode.EXTENDED, MatchMode.FULL_HOUSE),
        ),
        RoleId.MAFIA: RoleMetadata(
            id=RoleId.MAFIA,
            name="Мафия",
            emoji="🕵️‍♂️",
            side=RoleSide.MAFIA,
            description="Член преступной группировки, убивающий мирных жителей.",
            available_in_modes=(MatchMode.CLASSIC, MatchMode.EXTENDED, MatchMode.FULL_HOUSE),
        ),
        RoleId.DON: RoleMetadata(
            id=RoleId.DON,
            name="Дон",
            emoji="🎩",
            side=RoleSide.MAFIA,
            description="Глава мафии, ищет Шерифа ночью.",
            available_in_modes=(MatchMode.EXTENDED, MatchMode.FULL_HOUSE),
        ),
        RoleId.SHERIFF: RoleMetadata(
            id=RoleId.SHERIFF,
            name="Шериф",
            emoji="👮‍♂️",
            side=RoleSide.CIVILIAN,
            description="Блюститель закона, проверяет игроков ночью.",
            available_in_modes=(MatchMode.CLASSIC, MatchMode.EXTENDED, MatchMode.FULL_HOUSE),
        ),
        RoleId.SERGEANT: RoleMetadata(
            id=RoleId.SERGEANT,
            name="Сержант",
            emoji="🎖",
            side=RoleSide.CIVILIAN,
            description="Помощник Шерифа, узнает результаты проверок после смерти Шерифа.",
            available_in_modes=(MatchMode.EXTENDED, MatchMode.FULL_HOUSE),
        ),
        RoleId.DOCTOR: RoleMetadata(
            id=RoleId.DOCTOR,
            name="Доктор",
            emoji="👨‍⚕️",
            side=RoleSide.CIVILIAN,
            description="Спасает одного игрока от смерти ночью.",
            available_in_modes=(MatchMode.CLASSIC, MatchMode.EXTENDED, MatchMode.FULL_HOUSE),
        ),
        RoleId.MANIAC: RoleMetadata(
            id=RoleId.MANIAC,
            name="Маньяк",
            emoji="🔪",
            side=RoleSide.NEUTRAL,
            description="Одиночка, убивающий всех на своем пути.",
            available_in_modes=(MatchMode.EXTENDED, MatchMode.FULL_HOUSE),
        ),
        RoleId.LOVER: RoleMetadata(
            id=RoleId.LOVER,
            name="Любовница",
            emoji="💃",
            side=RoleSide.CIVILIAN,
            description="Блокирует ночное действие выбранного игрока.",
            available_in_modes=(MatchMode.EXTENDED, MatchMode.FULL_HOUSE),
        ),
        RoleId.LAWYER: RoleMetadata(
            id=RoleId.LAWYER,
            name="Адвокат",
            emoji="💼",
            side=RoleSide.MAFIA,
            description="Защищает члена мафии от проверок Шерифа.",
            available_in_modes=(MatchMode.FULL_HOUSE,),
        ),
        RoleId.SUICIDE: RoleMetadata(
            id=RoleId.SUICIDE,
            name="Самоубийца",
            emoji="🧟",
            side=RoleSide.NEUTRAL,
            description="Побеждает, если его казнят на голосовании.",
            available_in_modes=(MatchMode.FULL_HOUSE,),
        ),
        RoleId.HOBO: RoleMetadata(
            id=RoleId.HOBO,
            name="Бомж",
            emoji="🏚",
            side=RoleSide.CIVILIAN,
            description="Следит за игроком и узнает, кто к нему заходил ночью.",
            available_in_modes=(MatchMode.FULL_HOUSE,),
        ),
        RoleId.LUCKY: RoleMetadata(
            id=RoleId.LUCKY,
            name="Везунчик",
            emoji="🍀",
            side=RoleSide.CIVILIAN,
            description="Имеет шанс выжить после первого покушения.",
            available_in_modes=(MatchMode.FULL_HOUSE,),
        ),
        RoleId.KAMIKAZE: RoleMetadata(
            id=RoleId.KAMIKAZE,
            name="Камикадзе",
            emoji="💣",
            side=RoleSide.CIVILIAN,
            description="Забирает с собой того, кто его убил или казнил.",
            available_in_modes=(MatchMode.FULL_HOUSE,),
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
        return [r for r in cls._roles.values() if mode in r.available_in_modes]


class PresetRegistry:
    """
    Standard presets for game sessions.
    Civilians are filler roles and are not explicitly counted in role_counts.
    assignment_service will calculate: civilians = current_players - sum(role_counts).
    """

    CLASSIC_5_6 = RolePreset(
        id="classic_5_6",
        mode=MatchMode.CLASSIC,
        min_players=5,
        max_players=6,
        role_counts={
            RoleId.MAFIA: 1,
            RoleId.SHERIFF: 1,
            RoleId.DOCTOR: 1,
        },
        rewards_enabled=True,
    )

    CLASSIC_7_10 = RolePreset(
        id="classic_7_10",
        mode=MatchMode.CLASSIC,
        min_players=7,
        max_players=10,
        role_counts={
            RoleId.MAFIA: 2,
            RoleId.SHERIFF: 1,
            RoleId.DOCTOR: 1,
        },
        rewards_enabled=True,
    )

    EXTENDED_10_12 = RolePreset(
        id="extended_10_12",
        mode=MatchMode.EXTENDED,
        min_players=10,
        max_players=12,
        role_counts={
            RoleId.MAFIA: 2,
            RoleId.DON: 1,
            RoleId.SHERIFF: 1,
            RoleId.DOCTOR: 1,
            RoleId.MANIAC: 1,
        },
        rewards_enabled=True,
    )

    EXTENDED_13_15 = RolePreset(
        id="extended_13_15",
        mode=MatchMode.EXTENDED,
        min_players=13,
        max_players=15,
        role_counts={
            RoleId.MAFIA: 3,
            RoleId.DON: 1,
            RoleId.SHERIFF: 1,
            RoleId.SERGEANT: 1,
            RoleId.DOCTOR: 1,
            RoleId.MANIAC: 1,
            RoleId.LOVER: 1,
        },
        rewards_enabled=True,
    )

    FULL_HOUSE_16_20 = RolePreset(
        id="full_house_16_20",
        mode=MatchMode.FULL_HOUSE,
        min_players=16,
        max_players=20,
        role_counts={
            RoleId.MAFIA: 4,
            RoleId.DON: 1,
            RoleId.LAWYER: 1,
            RoleId.SHERIFF: 1,
            RoleId.SERGEANT: 1,
            RoleId.DOCTOR: 1,
            RoleId.MANIAC: 1,
            RoleId.LOVER: 1,
            RoleId.HOBO: 1,
            RoleId.LUCKY: 1,
            RoleId.KAMIKAZE: 1,
            RoleId.SUICIDE: 1,
        },
        rewards_enabled=True,
        reward_multiplier=1.0,
    )

    @classmethod
    def list_all(cls) -> list[RolePreset]:
        return [
            cls.CLASSIC_5_6,
            cls.CLASSIC_7_10,
            cls.EXTENDED_10_12,
            cls.EXTENDED_13_15,
            cls.FULL_HOUSE_16_20,
        ]

    @classmethod
    def get_by_id(cls, preset_id: str) -> RolePreset:
        for p in cls.list_all():
            if p.id == preset_id:
                return p
        raise ValueError(f"Preset {preset_id} not found")

