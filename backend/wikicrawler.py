import time
import requests
from urllib.parse import quote
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

UA = "PyMuLiSe/1.0 (contact: your-email@example.com) requests"  # <— anpassen!

def _session():
    s = requests.Session()
    s.headers.update({
        "User-Agent": UA,
        "Accept": "application/json, text/html;q=0.8",
        "Accept-Language": "de,en;q=0.9",
    })
    retry = Retry(
        total=5,
        backoff_factor=0.6,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "HEAD"],
        respect_retry_after_header=True,
    )
    s.mount("https://", HTTPAdapter(max_retries=retry))
    s.mount("http://", HTTPAdapter(max_retries=retry))
    return s

SES = _session()


def _wikipedia_api_infobox_genres(title: str, lang: str = "en") -> list[str]:
    try:
        r = SES.get(
            f"https://{lang}.wikipedia.org/w/api.php",
            params={
                "action": "parse",
                "page": title,
                "prop": "text",
                "redirects": 1,
                "format": "json",
            },
            timeout=8,
        )
        r.raise_for_status()
        data = r.json()
        html = data.get("parse", {}).get("text", {}).get("*")
        if not html:
            return []
        soup = BeautifulSoup(html, "html.parser")
        infobox = soup.find("table", class_=lambda c: bool(c and "infobox" in c))
        if not infobox:
            return []
        genres = set()
        for row in infobox.find_all("tr"):
            header = row.find("th")
            if header and "genre" in header.get_text(" ").lower():
                td = row.find("td")
                if not td:
                    continue
                items = [
                    a.get_text(" ").lower().strip().replace("-", " ")
                    for a in td.find_all("a")
                    if a.get_text().strip()
                ]
                if not items:
                    text = td.get_text(separator=",").lower()
                    items = [g.strip().replace("-", " ") for g in text.split(",") if g.strip()]
                for g in items:
                    if g not in ("music", "band") and g[0].isalpha():
                        genres.add(g.rstrip("s"))
        return sorted(genres)
    except requests.RequestException:
        return []


def get_band_genres(band_name: str) -> list[str]:
    """
    Extracts genres for a band name from Wikipedia.
    """
    genres = set()
    for lang in ("en", "de"):
        g = _wikipedia_api_infobox_genres(band_name, lang=lang)
        if len(g) > 3:
            return g
        genres = (genres | set(g))

    return list(genres)


if __name__ == "__main__":
    for band in [
        "Nickelback", "Fall Out Boy", "The Birthday Massacre", "Black Sabbath", "AC_DC"
    ] : print(get_band_genres(band))