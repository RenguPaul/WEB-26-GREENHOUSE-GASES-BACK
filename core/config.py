from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_USER: str = "myuser"
    DB_PASSWORD: str = "mypassword"
    DB_NAME: str = "greenhouse_gases_db"

    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ROOT_USER: str = "root"
    MINIO_ROOT_PASSWORD: str = "rootpassword"
    MINIO_BUCKET: str = "climate-media"
    MINIO_SECURE: bool = False

    REDIS_URL: str = "redis://localhost:6379/0"
    SESSION_COOKIE_NAME: str = "greenhouse_session"
    SESSION_TTL_SECONDS: int = 86400
    SESSION_COOKIE_SECURE: bool = False
    # Список имён через запятую; такие аккаунты получают роль moderator
    # при регистрации. Для production используйте отдельный безопасный процесс назначения роли.
    MODERATOR_USERNAMES: str = ""

    @property
    def DATABASE_URL(self) -> str:
        return (
            "postgresql+asyncpg://"
            f"{self.DB_USER}:{self.DB_PASSWORD}@"
            f"{self.DB_HOST}:{self.DB_PORT}/"
            f"{self.DB_NAME}"
        )

    @property
    def moderator_usernames(self) -> set[str]:
        return {name.strip() for name in self.MODERATOR_USERNAMES.split(",") if name.strip()}

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
