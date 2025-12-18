from pydantic import HttpUrl, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_TITLE: str = "KPI Communication Bot"
    APP_VERSION: str = "1.0.0"

    ALLOWED_ORIGINS: str

    ROOT_BOT_TOKEN: SecretStr

    ROOT_ADMIN_CHAT_ID: int
    ROOT_ADMIN_LOGS_THREAD_ID: int | None = None
    ROOT_ADMIN_ERRORS_THREAD_ID: int | None = None
    ROOT_ADMIN_MESSAGES_THREAD_ID: int | None = None
    ROOT_ADMIN_VERIFICATION_THREAD_ID: int | None = None

    ROOT_ORGANIZATION_TITLE: str = "ROOT"
    ROOT_ORGANIZATION_ACCEPT_MESSAGES: bool = True
    ROOT_ORGANIZATION_PRIVATE: bool = True

    SERVICE_ACCOUNT_FILE: str
    DATABASE_URL: SecretStr

    API_URL: HttpUrl
    API_PREFIX: str = ""

    AES_TOKEN: SecretStr
    AES_TOKEN_SALT: SecretStr | None = None

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings(**{})
