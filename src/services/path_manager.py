from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

SETTINGS_PATH = str((ROOT / "data" / "settings.json"))

LOCALES_DIR = str((ROOT / "src" / "resources" / "locales"))
