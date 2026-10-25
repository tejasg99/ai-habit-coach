from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    LLM_API_KEY: str = ""
    LLM_MODEL: str = ""
    LLM_BASE_URL: str = "https://generativelanguage.googleapis.com/v1beta/openai/"

    LLM_TIMEOUT_SECONDS: float = 60.0
    LLM_MAX_ATTEMPTS: int = 3


settings = Settings()
