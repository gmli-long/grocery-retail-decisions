"""Challenge 01 — central configuration.

Environment-specific paths live here so the code itself stays portable. Override
the source CSV directory by setting the CHALLENGE_01_DATA_DIR environment
variable, or pass --data-dir on the command line (which takes precedence).
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# Source CSV directory. Defaults to the standard kagglehub cache location,
# resolved from the user's home directory so it works on any machine that
# fetched the dataset with `kagglehub` — not just the author's machine. Set
# CHALLENGE_01_DATA_DIR (or --data-dir) to point elsewhere without editing.
DEFAULT_DATA_DIR = os.environ.get(
    "CHALLENGE_01_DATA_DIR",
    str(Path.home() / ".cache" / "kagglehub" / "competitions"
        / "challenge-01-spaghetti-schema-2026" / "Callenge Data Sets"
        / "Challenge_01_data_V1_0"),
)