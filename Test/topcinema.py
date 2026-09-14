import re
from typing import Any, Dict
import requests
from bs4 import BeautifulSoup

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "ar-EG,ar;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://topcinema.io/",
}
TIMEOUT = 10


def search_topcinema(
    platform_name: str, logo_path: str, keyword: str
) -> Dict[str, Any]:
    """Extractor function for TopCinema (HTML / BeautifulSoup).

    Deduplicates series episodes into a single entry per series season.
    """
    results = []
    seen_series = set()

    search_url = "https://topcinema.io/search/"
    params = {"query": keyword, "type": "all"}

    try:
        response = requests.get(
            search_url, params=params, headers=DEFAULT_HEADERS, timeout=TIMEOUT
        )
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        # FIX: Expanded CSS selector to match movies, series, and episode grid containers
        items = soup.select(
            "div.Block--Item, div.Small--Box, div.Series--Box, div.Episode--Box, div.Movie--Box, div.Grid--Item"
        )

        for item in items:
            title_el = item.select_one(".Title, h3, a.title, .Block--Info h3")
            link_el = item.select_one("a[href]")
            img_el = item.select_one("img")

            if not title_el or not link_el or not link_el.get("href"):
                continue

            raw_title = title_el.text.strip()
            url = link_el["href"]
            poster = (
                img_el.get("data-src")
                or img_el.get("data-lazy-src")
                or img_el.get("src")
                or ""
                if img_el
                else ""
            )

            is_series = (
                "مسلسل" in raw_title
                or "/series/" in url
                or "الحلقة" in raw_title
            )

            if is_series:
                clean_title = re.sub(
                    r"الحلقة\s+\d+", "", raw_title, flags=re.IGNORECASE
                )
                clean_title = re.sub(
                    r"والاخيرة|والأخيرة|مترجمة|مترجم|اون لاين|أون لاين",
                    "",
                    clean_title,
                    flags=re.IGNORECASE,
                )
                clean_title = re.sub(r"\s+", " ", clean_title).strip()

                dedup_key = clean_title.lower()

                if dedup_key in seen_series:
                    continue

                seen_series.add(dedup_key)
                results.append(
                    {"title": clean_title, "url": url, "poster": poster}
                )
            else:
                results.append(
                    {"title": raw_title, "url": url, "poster": poster}
                )

    except Exception as e:
        print(f"[{platform_name}] Error during fetch: {e}")

    return {
        "platform": platform_name,
        "logo": logo_path,
        "results": results,
    }

# Quick Execution Test
if __name__ == "__main__":
    test_result = search_topcinema(
        "TopCinema", "static/logos/topcinema.png", "hope"
    )
    print(test_result)