"""Bandcamp: у yt-dlp нет поиска по Bandcamp, поэтому парсим страницу поиска."""
from __future__ import annotations

import httpx
from bs4 import BeautifulSoup

from ..models import MediaRef


class BandcampSearcher:
    name = "bandcamp"
    URL = "https://bandcamp.com/search"
    HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/126 Safari/537.36"}

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def search(self, query: str, limit: int = 10) -> list[MediaRef]:
        resp = await self._client.get(
            self.URL, params={"q": query, "item_type": "a"}, headers=self.HEADERS, follow_redirects=True
        )
        resp.raise_for_status()
        return parse_search_page(resp.text)[:limit]


def parse_search_page(html: str) -> list[MediaRef]:
    soup = BeautifulSoup(html, "html.parser")
    refs: list[MediaRef] = []
    for item in soup.select("li.searchresult"):
        itemtype = item.select_one(".itemtype")
        if itemtype and itemtype.get_text(strip=True).upper() != "ALBUM":
            continue
        heading = item.select_one(".heading a")
        if not heading:
            continue
        url_el = item.select_one(".itemurl a")
        url = url_el.get_text(strip=True) if url_el else str(heading.get("href", "")).split("?")[0]
        subhead = item.select_one(".subhead")
        artist = subhead.get_text(" ", strip=True) if subhead else ""
        if artist.lower().startswith("by "):
            artist = artist[3:].strip()
        if url:
            refs.append(MediaRef(url=url, title=heading.get_text(strip=True), uploader=artist or None))
    return refs
