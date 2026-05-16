def render_profile(name: str) -> str:
    return name.title()


def display_profile(username: str) -> str:
    return render_profile(username=username)


def user_badge_label(name: str) -> str:
    return f"@{name.lower()}"
