"""
Kate Night Engine — Configuration
Nighttime creative exploration + predictive extrapolation system.
Integrates patterns from ARIS, Oneira, ERGODIC, and MIRAI.
"""

import os
from pathlib import Path

# Load environment from .env file
try:
    from dotenv import load_dotenv
    load_dotenv("/opt/data/.env")
except ImportError:
    pass

# === Paths ===
BASE_DIR = Path("/opt/data/kate_night_engine")
DREAMS_DIR = BASE_DIR / "dreams"
ORACLES_DIR = BASE_DIR / "oracles"
IMAGES_DIR = BASE_DIR / "images"
LOGS_DIR = BASE_DIR / "logs"
MEMORY_DIR = BASE_DIR / "memory"

# === API ===
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# === Models ===
CREATIVE_MODEL = "anthropic/claude-sonnet-4"  # For dream synthesis (creative)
ANALYTIC_MODEL = "anthropic/claude-sonnet-4"  # For oracle predictions (rigorous)
VISION_MODEL = "openai/gpt-4o"  # For evaluating generated images
IMAGE_MODEL = "openai/dall-e-3"  # For generating dream images

# === Context sources for nightly work ===
CONTEXT_DIRS = [
    "/opt/data/patent_training/",
    "/opt/data/benjamin_operating_system/",
    "/opt/data/lightrag/strategic_rag/",
    "/opt/hermes/",
]

# === Dream Mode Settings ===
DREAM_NOISE_LENGTH = 128
DREAM_AGENTS = 5  # Number of parallel creative agents (ERGODIC-style)
DREAM_MAX_TURNS = 3  # Critique rounds
DREAM_TEMPERATURE = 0.9  # High temp for creativity

# === Oracle Mode Settings ===
ORACLE_TOPICS = [
    "quantum computing IP landscape trends",
    "European DeepTech sovereignty and IP strategy",
    "AI governance and trade secret protection",
    "intangible asset valuation methodologies",
    "quantum startup competitive dynamics",
]
ORACLE_CONFIDENCE_THRESHOLD = 0.6
ORACLE_TEMPERATURE = 0.3  # Low temp for precision

# === Schedule ===
DREAM_HOUR = 2   # 2 AM
ORACLE_HOUR = 3  # 3 AM
BRIEF_HOUR = 6   # 6:30 AM delivery

# === Memory persistence ===
MEMORY_FILE = MEMORY_DIR / "night_memory.json"  # Cross-session learning
