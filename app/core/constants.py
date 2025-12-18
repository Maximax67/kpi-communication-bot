import re


GOOGLE_AUTH_SCOPES = ["https://www.googleapis.com/auth/drive"]

USERNAME_REGEX = re.compile(
    r"""
    (?:
        (?<!\w)@ |                              # @username
        https?://(?:t\.me|telegram\.(?:me|dog))/ |  # https://t.me/username
        tg://resolve\?domain=                  # tg://resolve?domain=username
    )
    (?P<username>
        (?!.*__)                               # no double underscores
        [a-z][a-z0-9_]{3,31}                   # 5–32 chars total
        (?<!_)                                # cannot end with underscore
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)

SPREADSHEET_URL_REGEX = re.compile(
    r"https://docs\.google\.com/spreadsheets/d/([a-zA-Z0-9-_]+)"
)
COLUMN_REGEX = re.compile(r"^[A-Z]{1,3}$")
RANGE_REGEX = re.compile(r"^(\d+)-(\d+)$")
