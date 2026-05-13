import pytest

from app.core.game.assignment import (
    InvalidPlayerCountError,
    InvalidRolePresetError,
    RoleAssignmentService,
)
from app.core.game.roles import MatchMode, RoleId, RolePreset, PresetRegistry


def test_build_role_deck_competitive_5_players() -> None:
    preset = RolePreset(
        id="test_comp_5",
        mode=MatchMode.COMPETITIVE,
        min_players=5,
        max_players=10,
        role_counts={
            RoleId.MAFIA: 1,
            RoleId.SHERIFF: 1,
            RoleId.DOCTOR: 1,
        },
        reward_eligible=True,
    )

    deck = RoleAssignmentService.build_role_deck(preset, 5)

    assert len(deck) == 5
    assert deck.count(RoleId.MAFIA) == 1
    assert deck.count(RoleId.SHERIFF) == 1
    assert deck.count(RoleId.DOCTOR) == 1
    assert deck.count(RoleId.CIVILIAN) == 2


def test_build_role_deck_competitive_9_players() -> None:
    preset = RolePreset(
        id="test_comp_9",
        mode=MatchMode.COMPETITIVE,
        min_players=5,
        max_players=10,
        role_counts={
            RoleId.MAFIA: 2,
            RoleId.SHERIFF: 1,
            RoleId.DOCTOR: 1,
        },
        reward_eligible=True,
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
        mode=MatchMode.COMPETITIVE,
        min_players=5,
        max_players=10,
        role_counts={RoleId.MAFIA: 1},
        reward_eligible=True,
    )

    with pytest.raises(InvalidPlayerCountError):
        RoleAssignmentService.build_role_deck(preset, 4)

    with pytest.raises(InvalidPlayerCountError):
        RoleAssignmentService.build_role_deck(preset, 11)


def test_invalid_role_preset_too_many_roles() -> None:
    # 6 specific roles for 5 slots
    preset = RolePreset(
        id="too_many",
        mode=MatchMode.PARTY,
        min_players=5,
        max_players=10,
        role_counts={
            RoleId.MAFIA: 3,
            RoleId.DON: 1,
            RoleId.SHERIFF: 1,
            RoleId.MANIAC: 1,
        },
        reward_eligible=False,
    )

    with pytest.raises(InvalidRolePresetError):
        RoleAssignmentService.build_role_deck(preset, 5)


def test_reward_eligible_logic() -> None:
    # Party cannot be reward eligible
    preset = RolePreset(
        id="party_ranked_cheat",
        mode=MatchMode.PARTY,
        min_players=5,
        max_players=5,
        role_counts={RoleId.MAFIA: 1},
        reward_eligible=True,
    )

    with pytest.raises(InvalidRolePresetError):
        RoleAssignmentService.build_role_deck(preset, 5)


def test_competitive_v1_restriction() -> None:
    # Attempting to use a non-competitive role in competitive mode
    preset = RolePreset(
        id="comp_with_maniac",
        mode=MatchMode.COMPETITIVE,
        min_players=5,
        max_players=10,
        role_counts={
            RoleId.MAFIA: 1,
            RoleId.MANIAC: 1,  # Not available in competitive v1
        },
        reward_eligible=True,
    )

    with pytest.raises(InvalidRolePresetError):
        RoleAssignmentService.build_role_deck(preset, 5)


def test_invalid_role_count_zero_or_negative() -> None:
    preset_zero = RolePreset(
        id="zero_count",
        mode=MatchMode.PARTY,
        min_players=5,
        max_players=10,
        role_counts={RoleId.MAFIA: 0},
        reward_eligible=False,
    )
    with pytest.raises(InvalidRolePresetError, match="must have count > 0"):
        RoleAssignmentService.build_role_deck(preset_zero, 5)

    preset_negative = RolePreset(
        id="neg_count",
        mode=MatchMode.PARTY,
        min_players=5,
        max_players=10,
        role_counts={RoleId.MAFIA: -1},
        reward_eligible=False,
    )
    with pytest.raises(InvalidRolePresetError, match="must have count > 0"):
        RoleAssignmentService.build_role_deck(preset_negative, 5)


def test_real_presets_from_registry() -> None:
    # 1. competitive_classic_5_6
    comp_5 = PresetRegistry.get_by_id("competitive_classic_5_6")
    deck_5 = RoleAssignmentService.build_role_deck(comp_5, 5)
    assert len(deck_5) == 5
    assert deck_5.count(RoleId.MAFIA) == 1
    assert deck_5.count(RoleId.SHERIFF) == 1
    assert deck_5.count(RoleId.DOCTOR) == 1
    assert deck_5.count(RoleId.CIVILIAN) == 2

    # 2. competitive_classic_7_9
    comp_9 = PresetRegistry.get_by_id("competitive_classic_7_9")
    deck_9 = RoleAssignmentService.build_role_deck(comp_9, 9)
    assert len(deck_9) == 9
    assert deck_9.count(RoleId.MAFIA) == 2
    assert deck_9.count(RoleId.SHERIFF) == 1
    assert deck_9.count(RoleId.DOCTOR) == 1
    assert deck_9.count(RoleId.CIVILIAN) == 5


def test_party_extended_deck() -> None:
    preset = RolePreset(
        id="party_test",
        mode=MatchMode.PARTY,
        min_players=5,
        max_players=20,
        role_counts={
            RoleId.MAFIA: 2,
            RoleId.DON: 1,
            RoleId.SHERIFF: 1,
            RoleId.MANIAC: 1,
        },
        reward_eligible=False,
    )

    deck = RoleAssignmentService.build_role_deck(preset, 10)
    assert len(deck) == 10
    assert deck.count(RoleId.MAFIA) == 2
    assert deck.count(RoleId.DON) == 1
    assert deck.count(RoleId.SHERIFF) == 1
    assert deck.count(RoleId.MANIAC) == 1
    assert deck.count(RoleId.CIVILIAN) == 5
