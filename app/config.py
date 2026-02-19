"""Configuration from environment variables."""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "storybook.db"
GENERATED_DIR = DATA_DIR / "generated"
IMAGES_DIR = GENERATED_DIR / "images"
VIDEOS_DIR = GENERATED_DIR / "videos"
COMPOSED_DIR = GENERATED_DIR / "composed"

# Ensure dirs exist
for d in [DATA_DIR, IMAGES_DIR, VIDEOS_DIR, COMPOSED_DIR]:
    d.mkdir(parents=True, exist_ok=True)

DATABASE_URL = f"sqlite:///{DB_PATH}"

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
XAI_API_KEY = os.getenv("XAI_API_KEY", "")

PORT = int(os.getenv("PORT", "8094"))
