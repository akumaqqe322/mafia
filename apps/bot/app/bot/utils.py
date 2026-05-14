def build_join_url(bot_username: str, token: str) -> str:
    """Builds a Telegram deep-link for joining a lobby."""
    return f"https://t.me/{bot_username}?start=join_{token}"
