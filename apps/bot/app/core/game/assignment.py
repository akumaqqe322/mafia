from app.core.game.roles import MatchMode, RoleId, RolePreset, RoleRegistry


class RoleAssignmentError(Exception):
    """Base exception for role assignment errors."""
    pass


class InvalidPlayerCountError(RoleAssignmentError):
    """Player count is outside the preset range."""
    pass


class InvalidRolePresetError(RoleAssignmentError):
    """Role preset is invalid for the requested configuration."""
    pass


class RoleAssignmentService:
    @staticmethod
    def build_role_deck(preset: RolePreset, players_count: int) -> list[RoleId]:
        """
        Builds a deterministic list of roles for the given preset and count.
        Civilians are used as fillers.
        """
        # 1. Validate player count
        if not (preset.min_players <= players_count <= preset.max_players):
            raise InvalidPlayerCountError(
                f"Preset {preset.id} requires {preset.min_players}-{preset.max_players} players, "
                f"but {players_count} were provided."
            )

        # 2. (Deprecated reward_eligible block removed)

        # 3. Calculate used slots
        deck: list[RoleId] = []
        for role_id, count in preset.role_counts.items():
            # Validate role count
            if count <= 0:
                raise InvalidRolePresetError(
                    f"Role {role_id} in preset {preset.id} "
                    f"must have count > 0, but got {count}."
                )

            # Validate role existence and mode compatibility
            role_meta = RoleRegistry.get(role_id)
            if preset.mode not in role_meta.available_in_modes:
                raise InvalidRolePresetError(
                    f"Role {role_id} is not available in "
                    f"{preset.mode} mode but used in preset {preset.id}"
                )

            for _ in range(count):
                deck.append(role_id)

        used_slots = len(deck)
        if used_slots > players_count:
            raise InvalidRolePresetError(
                f"Preset {preset.id} requires {used_slots} special roles, "
                f"but only {players_count} slots available."
            )

        # 4. Fill remaining slots with civilians
        civilians_needed = players_count - used_slots
        for _ in range(civilians_needed):
            deck.append(RoleId.CIVILIAN)

        return deck
