from enum import Enum


class CryptoInfo(bytes, Enum):
    BOT_TOKEN = b"bot-token"
    WEBHOOK_SECRET = b"webhook-secret"


class VisibilityLevel(str, Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    PRIVATE = "private"


class MessageType(str, Enum):
    SERVICE = "service"
    REQUEST = "request"
    TASK = "task"
    INFO = "info"
    SPAM = "spam"
    INFO_REPLY = "info_reply"


class ChatType(str, Enum):
    EXTERNAL = "external"
    INTERNAL = "internal"


class MessageStatus(str, Enum):
    NEW = "new"
    IN_PROCESS = "in_process"
    COMPLETED = "completed"


class SpamType(str, Enum):
    GROUPS = "groups"
    CAPTAINS = "captains"
    ALL_GROUPS = "all_groups"
    ALL_CAPTAINS = "all_captains"
