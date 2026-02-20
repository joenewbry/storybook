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
SHOT_MAPS_DIR = GENERATED_DIR / "shot_maps"
REFERENCES_DIR = GENERATED_DIR / "references"
CHAR_REF_DIR = REFERENCES_DIR / "characters"
LOC_REF_DIR = REFERENCES_DIR / "locations"
PROP_REF_DIR = REFERENCES_DIR / "props"

# Ensure dirs exist
for d in [DATA_DIR, IMAGES_DIR, VIDEOS_DIR, COMPOSED_DIR, SHOT_MAPS_DIR, CHAR_REF_DIR, LOC_REF_DIR, PROP_REF_DIR]:
    d.mkdir(parents=True, exist_ok=True)

DATABASE_URL = f"sqlite:///{DB_PATH}"

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
XAI_API_KEY = os.getenv("XAI_API_KEY", "")

PORT = int(os.getenv("PORT", "8094"))
