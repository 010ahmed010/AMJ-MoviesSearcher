#!/usr/bin/env python3

import json
import re
from urllib.parse import urljoin
from typing import Dict, List, Any
import requests
from bs4 import BeautifulSoup
from flask import Flask, render_template, request, Response, stream_with_context

app = Flask(__name__)

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}
TIMEOUT = 10


# ==============================================================================
# 🧩 SECTION 1: CUSTOM PLATFORM EXTRACTOR FUNCTIONS
# ==============================================================================
def parse_type_and_title(full_title: str) -> tuple[str, str]:
    """Extracts media type prefix (e.g., فيلم, مسلسل) if present."""
    parts = full_title.split(' ', 1)
    if len(parts) > 1 and any("\u0600" <= c <= "\u06FF" for c in parts[0]):
        return parts[0], parts[1]
    return "", full_title


def search_cimaleek(platform_name: str, logo_path: str, keyword: str) -> Dict[str, Any]:
    results = []
    search_url = f"https://m.cimaleek.pw/?s={keyword}"
    
    try:
        response = requests.get(search_url, headers=DEFAULT_HEADERS, timeout=TIMEOUT)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, "html.parser")
        items = soup.select("div.film_list-wrap div.item")
        
        for item in items:
            title_div = item.select_one("div.data div.title")
            link_tag = item.select_one("div.film-poster a")
            img_tag = item.select_one("img.film-poster-img")
            
            if title_div and link_tag and link_tag.get("href"):
                full_title = title_div.text.strip()
                url = link_tag["href"]
                poster = img_tag.get("data-src") or img_tag.get("src") if img_tag else ""
                
                media_type, title_name = parse_type_and_title(full_title)
                
                results.append({
                    "title": title_name,
                    "type": media_type,
                    "url": url,
                    "poster": poster
                })
                
    except Exception as e:
        print(f"[{platform_name}] Error during fetch: {e}")
        
    return {
        "platform": platform_name,
        "logo": logo_path,
        "results": results
    }


def search_topcinema(
    platform_name: str, logo_path: str, keyword: str
) -> Dict[str, Any]:
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
                clean_title = re.sub(r"الحلقة\s+\d+", "", raw_title, flags=re.IGNORECASE)
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
                
                media_type, title_name = parse_type_and_title(clean_title)
                results.append({"title": title_name, "type": media_type or "مسلسل", "url": url, "poster": poster})
            else:
                media_type, title_name = parse_type_and_title(raw_title)
                results.append({"title": title_name, "type": media_type, "url": url, "poster": poster})

    except Exception as e:
        print(f"[{platform_name}] Error during fetch: {e}")

    return {
        "platform": platform_name,
        "logo": logo_path,
        "results": results,
    }


def search_brstej(
    platform_name: str, logo_path: str, keyword: str
) -> Dict[str, Any]:
    """Extractor function for Prestige / برستيج (HTML / BeautifulSoup).

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

        # Select video grid items on Prestige (.prs-grid > li)
        items = soup.select("#prs-results .prs-grid > li")

        for item in items:
            # Locate title link inside caption or image anchor
            link_el = item.select_one(".prs-caption h3 a") or item.select_one("a.prs-image")
            if not link_el or not link_el.get("href"):
                continue

            raw_title = link_el.text.strip() or link_el.get("title", "").strip()
            url = urljoin(base_url, link_el["href"])

            # Handle poster images using img src or lazy-load attributes
            img_el = item.select_one("img")
            poster = ""
            if img_el:
                poster = (
                    img_el.get("data-original")
                    or img_el.get("data-src")
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
                # Clean up episode numbers, seasons, and filler text for deduplication
                clean_title = re.sub(
                    r"الموسم\s+\d+|الحلقة\s+\d+", "", raw_title, flags=re.IGNORECASE
                )
                clean_title = re.sub(
                    r"والاخيرة|والأخيرة|الاولى|الأولى|الثانية|الثالثة|الرابعة|الخامسة|السادسة|السابعة|الثامنة|التاسعة|العاشرة|مترجمة|مترجم|اون لاين|أون لاين|مشاهدة فيلم|فيلم",
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
                # Clean prefix for movie entries if needed
                clean_title = re.sub(r"^مشاهدة\s+فيلم\s+", "", raw_title, flags=re.IGNORECASE).strip()
                results.append(
                    {"title": clean_title, "url": url, "poster": poster}
                )

    except Exception as e:
        print(f"[{platform_name}] Error during fetch: {e}")

    return {
        "platform": platform_name,
        "logo": logo_path,
        "results": results,
    }


def search_qfilm(
    platform_name: str, logo_path: str, keyword: str
) -> Dict[str, Any]:
    """Extractor function for QFilm / كيو فيلم (HTML / BeautifulSoup).

    Deduplicates series episodes into a single entry per series.
    """
    results = []
    seen_series = set()

    base_url = "https://a.qfilm.tv"
    search_url = f"{base_url}/search.php"
    params = {"keywords": keyword}

    try:
        response = requests.get(
            search_url, params=params, headers=DEFAULT_HEADERS, timeout=TIMEOUT
        )
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        # Select items from the video grid
        items = soup.select("#pm-grid li, ul.pm-ul-browse-videos li")

        for item in items:
            # Locate title link inside thumbnail container
            link_el = item.select_one("a[title]") or item.select_one(".caption")
            if link_el and link_el.name != "a":
                link_el = link_el.find_parent("a") or item.select_one("a")

            if not link_el or not link_el.get("href"):
                continue

            raw_title = link_el.get("title") or link_el.text.strip()
            url = urljoin(base_url, link_el["href"])

            # Handle lazy-loaded poster images using data-echo or src
            img_el = item.select_one("img")
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
                # Clean up episode numbers, seasons, and filler text for deduplication
                clean_title = re.sub(
                    r"الموسم\s+\d+|الحلقة\s+\d+", "", raw_title, flags=re.IGNORECASE
                )
                clean_title = re.sub(
                    r"والاخيرة|والأخيرة|الاولى|الأولى|الثانية|الثالثة|الرابعة|الخامسة|السادسة|السابعة|الثامنة|التاسعة|العاشرة|مترجمة|مترجم|اون لاين|أون لاين|مشاهدة فيلم|فيلم",
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
                # Clean prefix for movie entries if needed
                clean_title = re.sub(r"^مشاهدة\s+فيلم\s+", "", raw_title, flags=re.IGNORECASE).strip()
                results.append(
                    {"title": clean_title, "url": url, "poster": poster}
                )

    except Exception as e:
        print(f"[{platform_name}] Error during fetch: {e}")

    return {
        "platform": platform_name,
        "logo": logo_path,
        "results": results,
    }


# ==============================================================================
# 📋 SECTION 2: REGISTER PLATFORM CONFIGURATIONS
# ==============================================================================
PLATFORMS = [
    (search_cimaleek, "CimaLeek", "https://m.cimaleek.pw/wp-content/uploads/2022/11/cropped-fav-2-192x192.png"),
    (search_topcinema, "TopCinema", "https://topcinema.io/wp-content/uploads/2023/05/cropped-icon-192x192.png"),
    (search_brstej, "Brstej", "https://aboutmsr.com/wp-content/uploads/2025/07/%D9%88%D9%82%D8%B9-%D8%A8%D8%B1%D8%B3%D8%AA%D9%8A%D8%AC.png"),
    (search_qfilm, "Qfilm", "https://a.qfilm.tv/favicons/apple-touch-icon.png"),

]


# ==============================================================================
# 🌐 SECTION 3: FLASK WEB SERVER & STREAMING ENGINE
# ==============================================================================
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/search")
def stream_search():
    keyword = request.args.get("q", "").strip()

    def generate_results():
        if not keyword:
            return

        total_platforms = len(PLATFORMS)

        for index, (search_func, name, logo) in enumerate(PLATFORMS, start=1):
            status_data = {
                "type": "status",
                "current": index,
                "total": total_platforms,
                "message": f"Searching {name} ({index}/{total_platforms})..."
            }
            yield f"data: {json.dumps(status_data)}\n\n"

            try:
                platform_payload = search_func(name, logo, keyword)
            except Exception as e:
                print(f"[!] Error executing {name}: {e}")
                platform_payload = {
                    "platform": name,
                    "logo": logo,
                    "results": []
                }

            result_data = {
                "type": "result",
                "platform": platform_payload.get("platform", name),
                "logo": platform_payload.get("logo", logo),
                "results": platform_payload.get("results", [])
            }
            yield f"data: {json.dumps(result_data)}\n\n"

        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    return Response(stream_with_context(generate_results()), content_type="text/event-stream")


if __name__ == "__main__":
    print("🚀 AMJ-MoviesSearcher running at http://127.0.0.1:5000")
    app.run(host="0.0.0.0",debug=True, port=5000)