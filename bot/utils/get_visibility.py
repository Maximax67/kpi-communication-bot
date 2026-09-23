from app.core.enums import VisibilityLevel

VISIBILITY_EMOJI = {
    VisibilityLevel.PUBLIC.value: "🌐",
    VisibilityLevel.INTERNAL.value: "🏢",
    VisibilityLevel.PRIVATE.value: "🔒",
}

VISIBILITY_LABELS = {
    VisibilityLevel.PUBLIC.value: "Публічний",
    VisibilityLevel.INTERNAL.value: "Організація",
    VisibilityLevel.PRIVATE.value: "Приватний",
}


def get_visibility_emoji(level: VisibilityLevel | str) -> str:
    return VISIBILITY_EMOJI.get(level, "❓")


def get_visibility_label(level: VisibilityLevel | str) -> str:
    emoji = get_visibility_emoji(level)
    label = VISIBILITY_LABELS.get(level, "Помилка")

    return f"{emoji} {label}"
