import requests
from bs4 import BeautifulSoup
from typing import Dict, Any

# Define the missing constants inside your test script
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}
TIMEOUT = 10


def search_cimaleek(platform_name: str, logo_path: str, keyword: str) -> Dict[str, Any]:
    """
    Extractor function for CimaLeek (HTML / BeautifulSoup)
    """
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
                title = title_div.text.strip()
                url = link_tag["href"]
                # CimaLeek uses lazy-loading; data-src holds the full thumbnail URL
                poster = img_tag.get("data-src") or img_tag.get("src") if img_tag else ""
                
                results.append({
                    "title": title,
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
# Quick Execution Test
if __name__ == "__main__":
    test_result = search_cimaleek("CimaLeek", "static/logos/cimaleek.png", "batman")
    print(test_result)