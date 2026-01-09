"""Application configuration using pydantic-settings."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Mattermost (Incoming Webhook)
    mattermost_webhook_url: str = Field(default="", description="Mattermost Incoming Webhook URL")

    # Target Repository (local path)
    target_repo_path: str = Field(
        default="./exemONE_front",
        description="Local path to target repository",
    )
    target_repo_name: str = Field(
        default="exemONE_front",
        description="Repository name for display",
    )

    # Claude Code CLI
    claude_code_path: str = Field(default="claude", description="Path to Claude Code CLI")

    # Database
    database_url: str = Field(
        default="sqlite:///./quiz.db",
        description="Database connection URL",
    )

    # Quiz Schedule (cron format)
    quiz_publish_cron: str = Field(
        default="0 10 * * 1-5",
        description="Cron expression for quiz publishing (default: weekdays 10:00)",
    )
    quiz_grading_cron: str = Field(
        default="0 16 * * 1-5",
        description="Cron expression for grading (default: weekdays 16:00)",
    )


settings = Settings()
