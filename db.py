import json
import pathlib
import datetime

BASE_DIR = pathlib.Path(__file__).parent
SEEN_POSTS_PATH = BASE_DIR / "seen_posts.json"
ERROR_STATE_PATH = BASE_DIR / "error_state.json"

_seen_posts: dict | None = None


def _load_seen_posts() -> dict:
    global _seen_posts
    if _seen_posts is None:
        if SEEN_POSTS_PATH.exists():
            _seen_posts = json.loads(SEEN_POSTS_PATH.read_text(encoding="utf-8"))
        else:
            _seen_posts = {}
    return _seen_posts


def _save_seen_posts() -> None:
    SEEN_POSTS_PATH.write_text(
        json.dumps(_seen_posts, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def init_db() -> None:
    _load_seen_posts()


def is_new(post_id: str) -> bool:
    return post_id not in _load_seen_posts()


def mark_seen(post_id: str, group_id: str, post_url: str | None) -> None:
    posts = _load_seen_posts()
    if post_id in posts:
        return
    posts[post_id] = {
        "group_id": group_id,
        "post_url": post_url,
        "seen_at": datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
    }
    _save_seen_posts()


def get_last_error_alert() -> datetime.datetime | None:
    if not ERROR_STATE_PATH.exists():
        return None
    data = json.loads(ERROR_STATE_PATH.read_text(encoding="utf-8"))
    timestamp = data.get("last_alert_at")
    if not timestamp:
        return None
    return datetime.datetime.fromisoformat(timestamp)


def record_error_alert(now: datetime.datetime) -> None:
    ERROR_STATE_PATH.write_text(
        json.dumps({"last_alert_at": now.isoformat()}, indent=2), encoding="utf-8"
    )


def clear_error_alert() -> None:
    if ERROR_STATE_PATH.exists():
        ERROR_STATE_PATH.unlink()
