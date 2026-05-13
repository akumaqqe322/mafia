import pytest

from app.core.game.assignment import (
    InvalidPlayerCountError,
    InvalidRolePresetError,
    RoleAssignmentService,
)
from app.core.game.roles import MatchMode, PresetRegistry, RoleId, RolePreset


def test_build_role_deck_classic_5_players() -> None:
    preset = RolePreset(
        id="test_classic_5",
        mode=MatchMode.CLASSIC,
        min_players=5,
        max_players=10,
        role_counts={
            RoleId.MAFIA: 1,
            RoleId.SHERIFF: 1,
            RoleId.DOCTOR: 1,
        },
        rewards_enabled=True,
    )

    deck = RoleAssignmentService.build_role_deck(preset, 5)

    assert len(deck) == 5
    assert deck.count(RoleId.MAFIA) == 1
    assert deck.count(RoleId.SHERIFF) == 1
    assert deck.count(RoleId.DOCTOR) == 1
    assert deck.count(RoleId.CIVILIAN) == 2


def test_build_role_deck_classic_9_players() -> None:
    preset = RolePreset(
        id="test_classic_9",
        mode=MatchMode.CLASSIC,
        min_players=5,
        max_players=10,
        role_counts={
            RoleId.MAFIA: 2,
            RoleId.SHERIFF: 1,
            RoleId.DOCTOR: 1,
        },
        rewards_enabled=True,
    )

    deck = RoleAssignmentService.build_role_deck(preset, 9)

    assert len(deck) == 9
    assert deck.count(RoleId.MAFIA) == 2
    assert deck.count(RoleId.SHERIFF) == 1
    assert deck.count(RoleId.DOCTOR) == 1
    assert deck.count(RoleId.CIVILIAN) == 5


def test_invalid_player_count() -> None:
    preset = RolePreset(
        id="test_range",
        mode=MatchMode.CLASSIC,
        min_players=5,
        max_players=10,
        role_counts={RoleId.MAFIA: 1},
        rewards_enabled=True,
    )

    with pytest.raises(InvalidPlayerCountError):
        RoleAssignmentService.build_role_deck(preset, 4)

    with pytest.raises(InvalidPlayerCountError):
        RoleAssignmentService.build_role_deck(preset, 11)


def test_invalid_role_preset_too_many_roles() -> None:
    # 6 specific roles for 5 slots
    preset = RolePreset(
        id="too_many",
        mode=MatchMode.EXTENDED,
        min_players=5,
        max_players=10,
        role_counts={
            RoleId.MAFIA: 3,
            RoleId.DON: 1,
            RoleId.SHERIFF: 1,
            RoleId.MANIAC: 1,
        },
        rewards_enabled=False,
    )

    with pytest.raises(InvalidRolePresetError):
        RoleAssignmentService.build_role_deck(preset, 5)


def test_mode_restriction() -> None:
    # Attempting to use a non-classic role in classic mode
    preset = RolePreset(
        id="classic_with_maniac",
        mode=MatchMode.CLASSIC,
        min_players=5,
        max_players=10,
        role_counts={
            RoleId.MAFIA: 1,
            RoleId.MANIAC: 1,  # Not available in classic
        },
        rewards_enabled=True,
    )

    with pytest.raises(InvalidRolePresetError, match="not available in classic mode"):
        RoleAssignmentService.build_role_deck(preset, 5)


def test_invalid_role_count_zero_or_negative() -> None:
    preset_zero = RolePreset(
        id="zero_count",
        mode=MatchMode.EXTENDED,
        min_players=5,
        max_players=10,
        role_counts={RoleId.MAFIA: 0},
        rewards_enabled=False,
    )
    with pytest.raises(InvalidRolePresetError, match="must have count > 0"):
        RoleAssignmentService.build_role_deck(preset_zero, 5)

    preset_negative = RolePreset(
        id="neg_count",
        mode=MatchMode.EXTENDED,
        min_players=5,
        max_players=10,
        role_counts={RoleId.MAFIA: -1},
        rewards_enabled=False,
    )
    with pytest.raises(InvalidRolePresetError, match="must have count > 0"):
        RoleAssignmentService.build_role_deck(preset_negative, 5)


def test_real_presets_from_registry() -> None:
    # 1. classic_5_6
    comp_5 = PresetRegistry.get_by_id("classic_5_6")
    deck_5 = RoleAssignmentService.build_role_deck(comp_5, 5)
    assert len(deck_5) == 5
    assert deck_5.count(RoleId.MAFIA) == 1
    assert deck_5.count(RoleId.SHERIFF) == 1
    assert deck_5.count(RoleId.DOCTOR) == 1
    assert deck_5.count(RoleId.CIVILIAN) == 2

    # 2. classic_7_10
    comp_10 = PresetRegistry.get_by_id("classic_7_10")
    deck_10 = RoleAssignmentService.build_role_deck(comp_10, 10)
    assert len(deck_10) == 10
    assert deck_10.count(RoleId.MAFIA) == 2
    assert deck_10.count(RoleId.SHERIFF) == 1
    assert deck_10.count(RoleId.DOCTOR) == 1
    assert deck_10.count(RoleId.CIVILIAN) == 6


def test_full_house_16_20_deck() -> None:
    preset = PresetRegistry.get_by_id("full_house_16_20")

    deck = RoleAssignmentService.build_role_deck(preset, 20)
    assert len(deck) == 20
    assert deck.count(RoleId.MAFIA) == 4
    assert deck.count(RoleId.DON) == 1
    assert deck.count(RoleId.LAWYER) == 1
    assert deck.count(RoleId.SHERIFF) == 1
    assert deck.count(RoleId.SERGEANT) == 1
    assert deck.count(RoleId.DOCTOR) == 1
    assert deck.count(RoleId.MANIAC) == 1
    assert deck.count(RoleId.LOVER) == 1
    assert deck.count(RoleId.HOBO) == 1
    assert deck.count(RoleId.LUCKY) == 1
    assert deck.count(RoleId.KAMIKAZE) == 1
    assert deck.count(RoleId.SUICIDE) == 1
    assert deck.count(RoleId.CIVILIAN) == 5
