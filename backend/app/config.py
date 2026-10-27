from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    database_url: str = "postgresql+psycopg://postgres@localhost:5432/talotrace_dev"
    anthropic_api_key: str = ""
    scorer_model: str = "claude-opus-5-5"
    # No defaults on purpose: the app refuses to start without them.
    hr_password: str
    secret_key: str
    web_url: str = "http://localhost:3000"  # base of the candidate links the seed prints
    data_dir: Path = BACKEND_DIR.parent / "data"
    uploads_dir: Path = BACKEND_DIR / "uploads"


settings = Settings()
