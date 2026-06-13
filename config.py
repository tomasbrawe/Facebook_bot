import os
import pathlib
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = pathlib.Path(__file__).parent

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
FB_COOKIES = os.environ["FB_COOKIES"]

# Optional: route the scraper's browser through a fixed proxy so Facebook always
# sees one steady connection. Format: http://user:pass@host:port
# If unset (e.g. running on a home machine), the browser connects directly.
PROXY_URL = os.environ.get("PROXY_URL", "").strip()

def _parse_groups(text: str) -> list[str]:
    groups = []
    for line in text.splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            groups.append(line)
    return groups

def _load_groups() -> list[str]:
    env_value = os.environ.get("GROUP_IDS")
    if env_value:
        return _parse_groups(env_value)
    path = BASE_DIR / "groups.txt"
    return _parse_groups(path.read_text(encoding="utf-8"))

def _load_criteria() -> str:
    env_value = os.environ.get("RENTAL_CRITERIA")
    if env_value:
        return env_value
    path = BASE_DIR / "criteria.md"
    return path.read_text(encoding="utf-8")

GROUP_IDS: list[str] = _load_groups()
RENTAL_CRITERIA: str = _load_criteria()
