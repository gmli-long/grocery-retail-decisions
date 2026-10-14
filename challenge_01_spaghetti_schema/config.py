"""Challenge 01 — central configuration.

Environment-specific paths live here so the code itself stays portable. Override
the source CSV directory by setting the CHALLENGE_01_DATA_DIR environment
variable, or pass --data-dir on the command line (which takes precedence).
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# Source CSV directory. The fallback is the author's local Kaggle cache; anyone
# forking the repo should set CHALLENGE_01_DATA_DIR (or --data-dir) to their own
# location instead of editing this file.
DEFAULT_DATA_DIR = os.environ.get(
    "CHALLENGE_01_DATA_DIR",
    r"C:\Users\21597\.cache\kagglehub\competitions"
    r"\challenge-01-spaghetti-schema-2026\Callenge Data Sets\Challenge_01_data_V1_0",
)