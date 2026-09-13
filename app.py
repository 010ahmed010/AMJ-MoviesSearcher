import json
from typing import Dict, List, Any, Callable
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
                
                # Split prefix ("فيلم", "مسلسل", etc.) from main title
                parts = full_title.split(' ', 1)
                if len(parts) > 1 and any("\u0600" <= c <= "\u06FF" for c in parts[0]):
                    media_type = parts[0]  # Arabic type (e.g., فيلم)
                    title_name = parts[1]  # Title (e.g., Hope Ranch)
                else:
                    media_type = ""
                    title_name = full_title
                
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
# ==============================================================================
# 📋 SECTION 2: REGISTER PLATFORM CONFIGURATIONS
# ==============================================================================
PLATFORMS = [
    (search_cimaleek, "CimaLeek", "assests/logos/CimaLeek-logo.png"),
    # Add future platform tuples here
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
    app.run(debug=True, port=5000)