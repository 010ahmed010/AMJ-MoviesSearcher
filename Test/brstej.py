import re
from typing import Any, Dict
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "ar-EG,ar;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://uo.brstej.com/",
}
TIMEOUT = 10



DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "ar-EG,ar;q=0.9,en-US;q=0.8,en;q=0.7",
    "Referer": "https://uo.brstej.com/",
}
TIMEOUT = 10


def search_brstej(
    platform_name: str, logo_path: str, keyword: str
) -> Dict[str, Any]:
    """Extractor function for Brstej / موقع برستيج (HTML / BeautifulSoup).

    Deduplicates series episodes into a single entry per series.
    """
    results = []
    seen_series = set()

    base_url = "https://uo.brstej.com"
    search_url = f"{base_url}/search.php"
    params = {"keywords": keyword}

    try:
        response = requests.get(
            search_url, params=params, headers=DEFAULT_HEADERS, timeout=TIMEOUT
        )
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        # Select video items from the grid container
        items = soup.select("#pm-grid li, ul.pm-ul-browse-videos li")

        for item in items:
            # Target the anchor in .caption h3 to bypass the watch-later modal link
            link_el = item.select_one(".caption h3 a")
            img_el = item.select_one("img")

            if not link_el or not link_el.get("href"):
                continue

            raw_title = link_el.text.strip()
            url = urljoin(base_url, link_el["href"])

            # Handle lazy-loaded poster images using data-echo or data-original
            poster = ""
            if img_el:
                poster = (
                    img_el.get("data-echo")
                    or img_el.get("data-original")
                    or img_el.get("src")
                    or ""
                )
                if poster:
                    poster = urljoin(base_url, poster)

            is_series = (
                "مسلسل" in raw_title
                or "الموسم" in raw_title
                or "الحلقة" in raw_title
            )

            if is_series:
                # Strip out episode numbers, season numbers, and adjectives for clean deduplication
                clean_title = re.sub(
                    r"الموسم\s+\d+|الحلقة\s+\d+", "", raw_title, flags=re.IGNORECASE
                )
                clean_title = re.sub(
                    r"والاخيرة|والأخيرة|الاولى|الأولى|الثانية|الثالثة|الرابعة|الخامسة|السادسة|السابعة|الثامنة|التاسعة|العاشرة|مترجمة|مترجم|اون لاين|أون لاين",
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


if __name__ == "__main__":
    test_result = search_brstej(
        "Brstej", "static/logos/brstej.png", "life"
    )
    print(test_result)