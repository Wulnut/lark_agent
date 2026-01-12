from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    LARK_APP_ID: str
    LARK_APP_SECRET: str
    LARK_ENCRYPT_KEY: str | None = None
    LARK_VERIFICATION_TOKEN: str | None = None

    # Project specific
    FEISHU_PROJECT_USER_TOKEN: str | None = None  # X-PLUGIN-TOKEN
    FEISHU_PROJECT_USER_KEY: str | None = None  # X-USER-KEY

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


settings = Settings()
