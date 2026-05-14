from app.core.game.roles import PresetRegistry


def select_preset_for_players(players_count: int) -> str | None:
    """Selects the best suitable preset for the given number of players."""
    presets = PresetRegistry.list_all()
    
    suitable_presets = [
        p for p in presets 
        if p.min_players <= players_count <= p.max_players
    ]
    
    if not suitable_presets:
        return None
        
    # If multiple presets match, select the one with the smallest range (max_players - min_players)
    # or just the first one for now as they are usually defined for specific ranges.
    # In the current registry, they don't overlap much.
    suitable_presets.sort(key=lambda p: p.max_players - p.min_players)
    
    return suitable_presets[0].id
