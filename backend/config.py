import os
from pathlib import Path
from pydantic import BaseModel
from dotenv import load_dotenv

# Load .env file from project root
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

class Settings(BaseModel):
    # App
    PROJECT_NAME: str = "OmniFlow AI"
    VERSION: str = "1.0.0"
    HOST: str = os.getenv("OMNIFLOW_HOST", "127.0.0.1")
    PORT: int = int(os.getenv("OMNIFLOW_PORT", "8000"))
    API_BASE_URL: str = os.getenv("OMNIFLOW_API_BASE_URL", f"http://127.0.0.1:{PORT}")

    # Database
    DATABASE_URL: str = os.getenv("OMNIFLOW_DATABASE_URL", f"sqlite:///{BASE_DIR.as_posix()}/omniflow.db")

    # Gemini
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    # Browser & Execution
    PLAYWRIGHT_HEADLESS: bool = os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() in ("1", "true", "yes")
    BROWSER_TIMEOUT_MS: int = int(os.getenv("BROWSER_TIMEOUT_MS", "15000"))
    MAX_STEP_RETRIES: int = int(os.getenv("MAX_STEP_RETRIES", "2"))
    MAX_SOURCES_PER_QUERY: int = int(os.getenv("MAX_SOURCES_PER_QUERY", "3"))

    # Demo & Test Controls
    DEMO_MODE: bool = os.getenv("DEMO_MODE", "false").lower() in ("1", "true", "yes")
    SIMULATE_CONTROLLED_FAILURE: bool = os.getenv("SIMULATE_CONTROLLED_FAILURE", "false").lower() in ("1", "true", "yes")

    # Storage Paths
    STORAGE_DIR: Path = BASE_DIR / "storage"
    REPORTS_DIR: Path = BASE_DIR / "storage" / "reports"

    def has_gemini_key(self) -> bool:
        return bool(self.GEMINI_API_KEY and self.GEMINI_API_KEY.strip())

settings = Settings()

# Ensure storage directories exist
settings.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
settings.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
