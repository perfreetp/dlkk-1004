from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./cardio_assist.db"
    API_V1_PREFIX: str = "/api/v1"
    PROJECT_NAME: str = "心内科辅助诊疗服务"
    DEBUG: bool = True

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()
