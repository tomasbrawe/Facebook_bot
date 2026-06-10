import logging
import requests
import config
from analyzer import AnalysisResult

logger = logging.getLogger(__name__)

TELEGRAM_API = f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/sendMessage"


def _send(text: str) -> None:
    try:
        resp = requests.post(
            TELEGRAM_API,
            json={
                "chat_id": config.TELEGRAM_CHAT_ID,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": False,
            },
            timeout=10,
        )
        resp.raise_for_status()
    except Exception as exc:
        logger.error("Failed to send Telegram message: %s", exc)


def send_alert(result: AnalysisResult, post: dict) -> None:
    preview = (post["text"] or "")[:300]
    if len(post["text"] or "") > 300:
        preview += "..."

    location_line = f"📍 <b>Location:</b> {result.location}" if result.location else ""
    price_line = f"💰 <b>Price:</b> {result.price}" if result.price else ""
    size_line = f"📐 <b>Size:</b> {result.size}" if result.size else ""

    details = "\n".join(filter(None, [location_line, price_line, size_line]))
    link_line = f'\n🔗 <a href="{post["post_url"]}">View post</a>' if post.get("post_url") else ""

    message = f"""\
🏠 <b>New matching rental found!</b>

{details}

📝 {preview}

✅ <i>{result.reason}</i>{link_line}"""

    _send(message.strip())


def send_error(message: str) -> None:
    _send(f"⚠️ <b>Rental Bot Error</b>\n\n{message}")
