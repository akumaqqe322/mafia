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
    assert civilian.available_in_competitive is True


def test_role_registry_get_not_found() -> None:
    with pytest.raises(ValueError, match="not found"):
        # We cast to avoid mypy error but test runtime behavior
        RoleRegistry.get(typing.cast(RoleId, "non_existent_role"))


def test_role_registry_list_for_mode_competitive_v1() -> None:
    comp_roles = RoleRegistry.list_for_mode(MatchMode.COMPETITIVE)
    role_ids = [r.id for r in comp_roles]

    # Competitive v1 MUST include only these 4 roles
    allowed_v1 = {RoleId.CIVILIAN, RoleId.MAFIA, RoleId.SHERIFF, RoleId.DOCTOR}
    assert set(role_ids) == allowed_v1


def test_role_registry_list_for_mode_party() -> None:
    party_roles = RoleRegistry.list_for_mode(MatchMode.PARTY)
    role_ids = [r.id for r in party_roles]

    # Party should have all roles defined in RoleId enum
    assert set(role_ids) == set(RoleId)


def test_kamikaze_side() -> None:
    kamikaze = RoleRegistry.get(RoleId.KAMIKAZE)
    assert kamikaze.side == RoleSide.CIVILIAN


def test_presets_registration() -> None:
    presets = PresetRegistry.list_all()
    assert len(presets) >= 3

    ids = [p.id for p in presets]
    assert "competitive_classic_5_6" in ids
    assert "party_extended" in ids


def test_competitive_preset_rules() -> None:
    preset = PresetRegistry.get_by_id("competitive_classic_7_9")
    assert preset.mode == MatchMode.COMPETITIVE
    assert preset.reward_eligible is True
    assert preset.role_counts[RoleId.MAFIA] == 2


def test_party_preset_rules() -> None:
    preset = PresetRegistry.get_by_id("party_extended")
    assert preset.mode == MatchMode.PARTY
    assert preset.reward_eligible is False
    assert RoleId.MANIAC in preset.role_counts


def test_preset_registry_get_not_found() -> None:
    with pytest.raises(ValueError, match="not found"):
        PresetRegistry.get_by_id("unknown_preset_123")
