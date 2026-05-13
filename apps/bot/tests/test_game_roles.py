import typing

import pytest

from app.core.game.roles import (
    MatchMode,
    PresetRegistry,
    RoleId,
    RoleRegistry,
    RoleSide,
)


def test_role_registry_get_success() -> None:
    civilian = RoleRegistry.get(RoleId.CIVILIAN)
    assert civilian.id == RoleId.CIVILIAN
    assert civilian.side == RoleSide.CIVILIAN
    assert MatchMode.CLASSIC in civilian.available_in_modes


def test_role_registry_get_not_found() -> None:
    with pytest.raises(ValueError, match="not found"):
        # We cast to avoid mypy error but test runtime behavior
        RoleRegistry.get(typing.cast(RoleId, "non_existent_role"))


def test_role_registry_list_for_mode_classic() -> None:
    classic_roles = RoleRegistry.list_for_mode(MatchMode.CLASSIC)
    role_ids = [r.id for r in classic_roles]

    # Classic mode contains balance core + Don
    allowed_classic = {RoleId.CIVILIAN, RoleId.MAFIA, RoleId.SHERIFF, RoleId.DOCTOR, RoleId.DON}
    assert set(role_ids) == allowed_classic


def test_role_registry_list_for_mode_big_game() -> None:
    big_game_roles = RoleRegistry.list_for_mode(MatchMode.BIG_GAME)
    role_ids = [r.id for r in big_game_roles]

    # Big Game contains (almost) everything
    assert RoleId.LAWYER in role_ids
    assert RoleId.KAMIKAZE in role_ids


def test_kamikaze_side() -> None:
    kamikaze = RoleRegistry.get(RoleId.KAMIKAZE)
    assert kamikaze.side == RoleSide.CIVILIAN


def test_presets_registration() -> None:
    presets = PresetRegistry.list_all()
    assert len(presets) >= 3

    ids = [p.id for p in presets]
    assert "classic_5_6" in ids
    assert "big_game_18_20" in ids


def test_classic_preset_rules() -> None:
    preset = PresetRegistry.get_by_id("classic_9_10")
    assert preset.mode == MatchMode.CLASSIC
    assert preset.rewards_enabled is True
    assert preset.role_counts[RoleId.MAFIA] == 2


def test_big_game_preset_rules() -> None:
    preset = PresetRegistry.get_by_id("big_game_18_20")
    assert preset.mode == MatchMode.BIG_GAME
    assert preset.rewards_enabled is True
    assert RoleId.LAWYER in preset.role_counts


def test_preset_registry_get_not_found() -> None:
    with pytest.raises(ValueError, match="not found"):
        PresetRegistry.get_by_id("unknown_preset_123")
