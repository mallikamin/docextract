"""Application configuration via pydantic-settings + .env support."""

from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Anthropic
    anthropic_api_key: str = ""
    haiku_model: str = "claude-haiku-4-5-20251001"
    sonnet_model: str = "claude-sonnet-4-5-20250929"

    # Processing
    ocr_dpi: int = 300
    max_file_size_mb: int = 50
    ocr_languages: str = "eng"
    ocr_min_confidence: int = 30

    # Preprocessing
    preprocessing_deskew: bool = True
    preprocessing_denoise: bool = True
    preprocessing_contrast: bool = True
    preprocessing_binarize: bool = False

    # Paths
    data_dir: Path = Path("data")
    jobs_dir: Path = Path("data/jobs")

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    def ensure_dirs(self):
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.jobs_dir.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_dirs()
