import logging
import pathlib
import datetime
from zoneinfo import ZoneInfo
import config
import db
import notifier
from scraper import scrape_all_groups, SessionExpiredError
from analyzer import analyze_post

LOG_PATH = pathlib.Path(__file__).parent / "bot.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

TIMEZONE = ZoneInfo("Asia/Jerusalem")
ACTIVE_START_HOUR = 6    # 06:00
ACTIVE_END_HOUR = 24     # 00:00 (midnight)
ERROR_ALERT_COOLDOWN = datetime.timedelta(hours=6)


def in_active_window(now: datetime.datetime | None = None) -> bool:
    now = now or datetime.datetime.now(TIMEZONE)
    return ACTIVE_START_HOUR <= now.hour < ACTIVE_END_HOUR


def run_check() -> bool:
    """Runs one scrape+analyze+notify cycle. Returns False if the Facebook session has expired."""
    logger.info("Starting check cycle")

    if not config.GROUP_IDS:
        logger.warning("No group IDs configured in groups.txt — nothing to scrape")
        return True

    try:
        posts = scrape_all_groups(config.GROUP_IDS, config.FB_COOKIES, config.PROXY_URL)
    except SessionExpiredError as exc:
        logger.error("Session expired: %s", exc)
        now = datetime.datetime.now(datetime.timezone.utc)
        last_alert = db.get_last_error_alert()
        if last_alert is None or now - last_alert > ERROR_ALERT_COOLDOWN:
            notifier.send_error(
                f"Facebook session expired. Please export fresh cookies and restart the bot.\n\n{exc}"
            )
            db.record_error_alert(now)
        else:
            logger.info("Session-expiry alert suppressed (already sent within the last 6 hours)")
        return False

    new_count = 0
    match_count = 0

    for post in posts:
        post_id = post["post_id"]

        if not db.is_new(post_id):
            continue

        new_count += 1
        logger.info("New post %s in group %s — analyzing", post_id, post["group_id"])

        result = analyze_post(post["text"])
        db.mark_seen(post_id, post["group_id"], post.get("post_url"))

        if result.matches:
            match_count += 1
            logger.info("Post %s MATCHES criteria — sending alert", post_id)
            notifier.send_alert(result, post)
        else:
            logger.debug("Post %s does not match: %s", post_id, result.reason)

    logger.info("Check complete — %d new posts, %d matches", new_count, match_count)
    db.clear_error_alert()
    return True


def main() -> None:
    logger.info("Facebook Rental Bot starting (single-shot run)")

    db.init_db()

    if not in_active_window():
        logger.info(
            "Outside active hours (%02d:00-%02d:00 Israel time) — skipping this run",
            ACTIVE_START_HOUR, ACTIVE_END_HOUR % 24,
        )
        return

    logger.info("Monitoring %d group(s)", len(config.GROUP_IDS))
    run_check()


if __name__ == "__main__":
    main()
