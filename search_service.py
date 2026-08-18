"""TangoWeb search service — privacy-first metasearch via DDGS."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any

from ddgs import DDGS
from ddgs.exceptions import DDGSException

DDG_INSTANT_API = "https://api.duckduckgo.com/"
RESULTS_PER_PAGE = 10
MAX_INFO_TOPICS = 8


@dataclass
class InfoBox:
    """Knowledge panel from DuckDuckGo instant answers and Wikipedia."""

    heading: str = ""
    abstract: str = ""
    source: str = ""
    source_url: str = ""
    image_url: str = ""
    related: list[dict[str, str]] = field(default_factory=list)
    wikipedia_title: str = ""
    wikipedia_url: str = ""
    wikipedia_summary: str = ""

    @property
    def visible(self) -> bool:
        return bool(self.heading or self.abstract or self.wikipedia_summary)


@dataclass
class SearchResults:
    query: str
    tab: str
    page: int
    region: str
    safesearch: str
    info: InfoBox
    web: list[dict[str, Any]] = field(default_factory=list)
    images: list[dict[str, Any]] = field(default_factory=list)
    videos: list[dict[str, Any]] = field(default_factory=list)
    files: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None


def video_thumbnail(video: dict[str, Any]) -> str:
    images = video.get("images")
    if isinstance(images, dict):
        for key in ("large", "medium", "small", "motion"):
            url = images.get(key) or ""
            if url:
                return url
    if isinstance(images, list):
        for item in images:
            if isinstance(item, str) and item:
                return item
    return video.get("image", "") or video.get("thumbnail", "")


def image_src(image: dict[str, Any]) -> str:
    return image.get("thumbnail") or image.get("image") or image.get("url") or ""


def image_link(image: dict[str, Any]) -> str:
    return image.get("image") or image.get("url") or image.get("thumbnail") or ""


def _clean_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "").strip()


def _fetch_ddg_instant(query: str) -> InfoBox:
    params = urllib.parse.urlencode(
        {
            "q": query,
            "format": "json",
            "no_html": "1",
            "skip_disambig": "1",
        }
    )
    url = f"{DDG_INSTANT_API}?{params}"
    info = InfoBox()

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "TangoWeb/1.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError):
        return info

    info.heading = data.get("Heading") or ""
    info.abstract = data.get("AbstractText") or data.get("Abstract") or ""
    info.source = data.get("AbstractSource") or ""
    info.source_url = data.get("AbstractURL") or ""

    image = data.get("Image") or ""
    if image:
        info.image_url = image if image.startswith("http") else f"https://duckduckgo.com{image}"

    related: list[dict[str, str]] = []
    for topic in data.get("RelatedTopics") or []:
        if "Topics" in topic:
            for sub in topic.get("Topics") or []:
                text = _clean_html(sub.get("Text", ""))
                link = sub.get("FirstURL", "")
                if text and link:
                    related.append({"text": text, "url": link})
        else:
            text = _clean_html(topic.get("Text", ""))
            link = topic.get("FirstURL", "")
            if text and link:
                related.append({"text": text, "url": link})
        if len(related) >= MAX_INFO_TOPICS:
            break

    info.related = related[:MAX_INFO_TOPICS]
    return info


def _fetch_wikipedia(query: str) -> InfoBox:
    info = InfoBox()
    try:
        with DDGS(timeout=12) as ddgs:
            results = list(ddgs.text(query, backend="wikipedia", max_results=1))
    except (DDGSException, TimeoutError, OSError):
        return info

    if not results:
        return info

    hit = results[0]
    info.wikipedia_title = hit.get("title", "")
    info.wikipedia_url = hit.get("href", "")
    info.wikipedia_summary = hit.get("body", "")
    return info


def _merge_info(ddg: InfoBox, wiki: InfoBox) -> InfoBox:
    merged = InfoBox(
        heading=ddg.heading or wiki.wikipedia_title,
        abstract=ddg.abstract,
        source=ddg.source,
        source_url=ddg.source_url or wiki.wikipedia_url,
        image_url=ddg.image_url,
        related=ddg.related,
        wikipedia_title=wiki.wikipedia_title,
        wikipedia_url=wiki.wikipedia_url,
        wikipedia_summary=wiki.wikipedia_summary if not ddg.abstract else "",
    )
    if not merged.abstract and wiki.wikipedia_summary:
        merged.abstract = wiki.wikipedia_summary
        merged.source = merged.source or "Wikipedia"
        merged.source_url = merged.source_url or wiki.wikipedia_url
    return merged


def _search_web(query: str, page: int, region: str, safesearch: str) -> list[dict[str, Any]]:
    with DDGS(timeout=15) as ddgs:
        return list(
            ddgs.text(
                query,
                region=region,
                safesearch=safesearch,
                max_results=RESULTS_PER_PAGE,
                page=page,
                backend="auto",
            )
        )


def _search_images(query: str, page: int, region: str, safesearch: str) -> list[dict[str, Any]]:
    with DDGS(timeout=15) as ddgs:
        return list(
            ddgs.images(
                query,
                region=region,
                safesearch=safesearch,
                max_results=RESULTS_PER_PAGE,
                page=page,
                backend="auto",
            )
        )


def _search_videos(query: str, page: int, region: str, safesearch: str) -> list[dict[str, Any]]:
    with DDGS(timeout=15) as ddgs:
        return list(
            ddgs.videos(
                query,
                region=region,
                safesearch=safesearch,
                max_results=RESULTS_PER_PAGE,
                page=page,
                backend="auto",
            )
        )


def _search_files(query: str, page: int, region: str, safesearch: str) -> list[dict[str, Any]]:
    file_query = f"{query} filetype:pdf OR filetype:doc OR filetype:docx OR filetype:xls OR filetype:ppt"
    results: list[dict[str, Any]] = []

    with DDGS(timeout=15) as ddgs:
        try:
            results.extend(
                list(
                    ddgs.text(
                        file_query,
                        region=region,
                        safesearch=safesearch,
                        max_results=RESULTS_PER_PAGE,
                        page=page,
                        backend="auto",
                    )
                )
            )
        except DDGSException:
            pass

        if len(results) < RESULTS_PER_PAGE:
            try:
                books = list(ddgs.books(query, max_results=RESULTS_PER_PAGE, page=page))
                for book in books:
                    results.append(
                        {
                            "title": book.get("title", "Untitled"),
                            "href": book.get("url", ""),
                            "body": f"{book.get('author', '')} · {book.get('info', '')}".strip(" ·"),
                            "kind": "book",
                            "thumbnail": book.get("thumbnail", ""),
                        }
                    )
            except DDGSException:
                pass

    return results[:RESULTS_PER_PAGE]


def search(
    query: str,
    tab: str = "all",
    page: int = 1,
    region: str = "us-en",
    safesearch: str = "off",
) -> SearchResults:
    query = query.strip()
    if not query:
        return SearchResults(
            query="",
            tab=tab,
            page=page,
            region=region,
            safesearch=safesearch,
            info=InfoBox(),
        )

    page = max(1, page)
    tab = tab if tab in ("all", "web", "images", "videos", "files") else "all"

    ddg_info = _fetch_ddg_instant(query)
    wiki_info = _fetch_wikipedia(query)
    info = _merge_info(ddg_info, wiki_info)

    result = SearchResults(
        query=query,
        tab=tab,
        page=page,
        region=region,
        safesearch=safesearch,
        info=info,
    )

    try:
        if tab in ("all", "web"):
            result.web = _search_web(query, page, region, safesearch)
        if tab in ("all", "images"):
            limit = 8 if tab == "all" else RESULTS_PER_PAGE
            with DDGS(timeout=15) as ddgs:
                result.images = list(
                    ddgs.images(
                        query,
                        region=region,
                        safesearch=safesearch,
                        max_results=limit,
                        page=page,
                        backend="auto",
                    )
                )
        if tab in ("all", "videos"):
            limit = 4 if tab == "all" else RESULTS_PER_PAGE
            result.videos = _search_videos(query, page, region, safesearch)[:limit]
        if tab in ("all", "files"):
            limit = 4 if tab == "all" else RESULTS_PER_PAGE
            result.files = _search_files(query, page, region, safesearch)[:limit]
    except (DDGSException, TimeoutError, OSError) as exc:
        # Only set error if we have no results at all
        has_any_results = result.web or result.images or result.videos or result.files
        if not has_any_results:
            result.error = str(exc) or "Search temporarily unavailable. Please try again."

    return result
