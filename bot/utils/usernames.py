from typing import Literal
from app.core.constants import USERNAME_REGEX


def extract_usernames(text: str) -> list[str]:
    matches = USERNAME_REGEX.finditer(text)
    usernames: set[str] = set()

    for match in matches:
        username = match.group("username")
        if username:
            username = username.strip()
            if username not in usernames:
                usernames.add(username)

    return list(usernames)


def validate_usernames(
    usernames: list[str],
) -> tuple[Literal[False], str] | tuple[Literal[True], None]:
    if not usernames:
        return False, "❌ Не знайдено жодного валідного юзернейму!"

    if len(usernames) > 5:
        return False, f"❌ Забагато тегів! Максимум 5, знайдено {len(usernames)}"

    for username in usernames:
        if len(username) < 5:
            return (
                False,
                f"❌ Юзернейм '{username}' занадто короткий (мінімум 5 символів)",
            )

        if len(username) > 32:
            return (
                False,
                f"❌ Юзернейм '{username}' занадто довгий (максимум 32 символи)",
            )

        if not username[0].isalpha():
            return False, f"❌ Юзернейм '{username}' повинен починатися з літери"

        if username.endswith("_"):
            return (
                False,
                f"❌ Юзернейм '{username}' не може закінчуватися підкресленням",
            )

        if "__" in username:
            return (
                False,
                f"❌ Юзернейм '{username}' не може містити послідовні підкреслення",
            )

        if not all(c.isalnum() or c == "_" for c in username):
            return False, f"❌ Юзернейм '{username}' містить недопустимі символи"

    return True, None
