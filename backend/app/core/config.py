from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import AnyHttpUrl, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    jwt_secret: str = Field(min_length=32)
    jwt_algorithm: Literal["HS256"]
    access_token_expire_minutes: int = Field(gt=0)
    refresh_token_expire_days: int = Field(gt=0)
    refresh_cookie_secure: bool
    cors_origins: Annotated[list[AnyHttpUrl], NoDecode]
    login_max_failed_attempts: int = Field(default=5, gt=0)
    login_failed_window_seconds: int = Field(default=900, gt=0)
    login_ip_max_requests: int = Field(default=30, gt=0)
    login_ip_window_seconds: int = Field(default=60, gt=0)
    storage_provider: Literal["local", "s3"] = "local"
    local_upload_dir: Path = Path(".uploads/attachments")
    aws_access_key_id: SecretStr | None = Field(default=None, repr=False, exclude=True)
    aws_secret_access_key: SecretStr | None = Field(default=None, repr=False, exclude=True)
    aws_region: str | None = None
    aws_bucket_name: str | None = None
    aws_s3_prefix: str = "helpdesk-mini/attachments/"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )

    @field_validator("database_url")
    @classmethod
    def require_postgresql(cls, value: str) -> str:
        if not value.startswith(("postgresql://", "postgresql+psycopg://")):
            raise ValueError("DATABASE_URL must use PostgreSQL")
        return value

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: Any) -> Any:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @model_validator(mode="after")
    def validate_storage(self) -> "Settings":
        if self.storage_provider == "s3":
            if not self.aws_region or not self.aws_bucket_name:
                raise ValueError("S3 storage requires AWS_REGION and AWS_BUCKET_NAME")
            if bool(self.aws_access_key_id) != bool(self.aws_secret_access_key):
                raise ValueError("Supply both AWS key variables or use the AWS credential chain")
        prefix = self.aws_s3_prefix.rstrip("/")
        if "\\" in prefix or self.aws_s3_prefix.startswith("/") or (prefix and any(part in {"", ".", ".."} for part in prefix.split("/"))):
            raise ValueError("AWS_S3_PREFIX must be a relative prefix without traversal")
        return self

    @field_validator("aws_access_key_id", "aws_secret_access_key", "aws_region", "aws_bucket_name", mode="before")
    @classmethod
    def empty_aws_value(cls, value: Any) -> Any:
        return None if value == "" else value


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
