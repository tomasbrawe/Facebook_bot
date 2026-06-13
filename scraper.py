import random
import time
import json
import re
import logging
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)

MAX_POSTS_PER_GROUP = 20
SLEEP_MIN = 2
SLEEP_MAX = 8
SCROLL_ROUNDS = 4

POST_ID_PATTERNS = [
    re.compile(r"/groups/\d+/posts/(\d+)"),
    re.compile(r"/permalink/(\d+)"),
    re.compile(r"story_fbid=(\d+)"),
    re.compile(r"/posts/(\d+)"),
]

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


class SessionExpiredError(Exception):
    pass


def _parse_cookies(raw: str) -> list[dict]:
    """Accepts a Cookie-Editor JSON export ([{"name":..,"value":..,"domain":..}, ...])
    or a header-string export ("name=value; name2=value2"). Returns Playwright-format cookies."""
    raw = raw.strip()

    if raw.startswith("["):
        try:
            entries = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Could not parse FB_COOKIES as JSON: {exc}") from exc
        cookies = []
        for e in entries:
            if "name" not in e or "value" not in e:
                continue
            cookies.append({
                "name": e["name"],
                "value": e["value"],
                "domain": e.get("domain") or ".facebook.com",
                "path": e.get("path") or "/",
            })
        return cookies

    cookies = []
    for part in raw.split(";"):
        part = part.strip()
        if "=" in part:
            name, _, value = part.partition("=")
            cookies.append({
                "name": name.strip(),
                "value": value.strip(),
                "domain": ".facebook.com",
                "path": "/",
            })
    return cookies


def _parse_proxy(proxy_url: str | None) -> dict | None:
    """Turns 'http://user:pass@host:port' into Playwright's proxy dict.
    Returns None if no proxy is configured (browser then connects directly)."""
    if not proxy_url or not proxy_url.strip():
        return None
    parsed = urlparse(proxy_url.strip())
    if not parsed.hostname:
        logger.warning("PROXY_URL set but could not be parsed — connecting directly")
        return None
    scheme = parsed.scheme or "http"
    server = f"{scheme}://{parsed.hostname}"
    if parsed.port:
        server += f":{parsed.port}"
    proxy = {"server": server}
    if parsed.username:
        proxy["username"] = parsed.username
    if parsed.password:
        proxy["password"] = parsed.password
    return proxy


def _extract_post_id(url: str | None) -> str | None:
    if not url:
        return None
    for pattern in POST_ID_PATTERNS:
        match = pattern.search(url)
        if match:
            return match.group(1)
    return None


def _scrape_group(page, group_id: str) -> list[dict]:
    url = f"https://www.facebook.com/groups/{group_id}"
    page.goto(url, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(3000)

    if "login" in page.url.lower() or page.locator('input[name="pass"]').count() > 0:
        raise SessionExpiredError(f"Facebook redirected to login for group {group_id} — session expired")

    for _ in range(SCROLL_ROUNDS):
        page.mouse.wheel(0, 4000)
        page.wait_for_timeout(random.uniform(1500, 3000))

    posts: list[dict] = []
    seen_ids: set[str] = set()
    articles = page.locator('div[role="article"]')
    count = articles.count()

    for i in range(count):
        article = articles.nth(i)
        try:
            text = article.inner_text(timeout=2000)
        except Exception:
            continue
        if not text.strip():
            continue

        post_id = None
        post_url = None
        links = article.locator(
            "a[href*='/posts/'], a[href*='/permalink/'], a[href*='story_fbid=']"
        )
        for j in range(min(links.count(), 5)):
            href = links.nth(j).get_attribute("href")
            pid = _extract_post_id(href)
            if pid:
                post_id = pid
                clean = href.split("?")[0]
                post_url = clean if clean.startswith("http") else f"https://www.facebook.com{clean}"
                break

        if not post_id or post_id in seen_ids:
            continue
        seen_ids.add(post_id)

        posts.append({
            "post_id": post_id,
            "group_id": group_id,
            "text": text.strip(),
            "post_url": post_url,
            "time": None,
        })

        if len(posts) >= MAX_POSTS_PER_GROUP:
            break

    if not posts:
        logger.warning("No posts extracted from group %s — page layout may have changed", group_id)

    return posts


def scrape_all_groups(group_ids: list[str], cookie_str: str, proxy_url: str | None = None) -> list[dict]:
    cookies = _parse_cookies(cookie_str)
    all_posts: list[dict] = []

    launch_kwargs: dict = {"headless": True}
    proxy = _parse_proxy(proxy_url)
    if proxy:
        launch_kwargs["proxy"] = proxy
        logger.info("Routing browser through proxy %s", proxy["server"])
    else:
        logger.info("No proxy configured — connecting directly")

    with sync_playwright() as p:
        browser = p.chromium.launch(**launch_kwargs)
        context = browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1280, "height": 800},
            locale="en-US",
        )
        context.add_cookies(cookies)
        page = context.new_page()

        try:
            for i, group_id in enumerate(group_ids):
                logger.info("Scraping group %s (%d/%d)", group_id, i + 1, len(group_ids))
                try:
                    posts = _scrape_group(page, group_id)
                    all_posts.extend(posts)
                    logger.info("Fetched %d posts from group %s", len(posts), group_id)
                except SessionExpiredError:
                    raise
                except Exception as exc:
                    logger.warning("Error scraping group %s: %s", group_id, exc)

                if i < len(group_ids) - 1:
                    sleep_time = random.uniform(SLEEP_MIN, SLEEP_MAX)
                    logger.debug("Sleeping %.1fs before next group", sleep_time)
                    time.sleep(sleep_time)
        finally:
            context.close()
            browser.close()

    return all_posts
