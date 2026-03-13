"""웹 검색을 통한 경쟁사 정보 수집 모듈"""

import logging
import os
import time
from datetime import datetime, timedelta
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Google Custom Search API 또는 SerpAPI 사용
SERPAPI_KEY = os.environ.get("SERPAPI_KEY", "")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
GOOGLE_CSE_ID = os.environ.get("GOOGLE_CSE_ID", "")


def search_competitor(competitor: dict, days_back: int = 7) -> list[dict]:
    """경쟁사에 대한 최근 정보를 웹에서 검색합니다."""
    all_results = []

    for keyword in competitor.get("keywords", []):
        results = _perform_search(keyword, days_back)
        all_results.extend(results)
        time.sleep(1)  # Rate limiting

    # 중복 제거 (URL 기준)
    seen_urls = set()
    unique_results = []
    for r in all_results:
        if r["url"] not in seen_urls:
            seen_urls.add(r["url"])
            unique_results.append(r)

    return unique_results


def _perform_search(query: str, days_back: int) -> list[dict]:
    """검색 API를 사용하여 검색을 수행합니다."""
    if SERPAPI_KEY:
        return _search_with_serpapi(query, days_back)
    elif GOOGLE_API_KEY and GOOGLE_CSE_ID:
        return _search_with_google_cse(query, days_back)
    else:
        logger.warning("검색 API 키가 설정되지 않았습니다. 기본 스크래핑을 시도합니다.")
        return _search_with_scraping(query, days_back)


def _search_with_serpapi(query: str, days_back: int) -> list[dict]:
    """SerpAPI를 사용한 검색"""
    try:
        params = {
            "q": query,
            "api_key": SERPAPI_KEY,
            "engine": "google",
            "num": 10,
            "tbs": f"qdr:w",  # 최근 1주일
            "hl": "ko",
            "gl": "kr",
        }
        resp = requests.get(
            "https://serpapi.com/search", params=params, timeout=30
        )
        resp.raise_for_status()
        data = resp.json()

        results = []
        for item in data.get("organic_results", []):
            results.append({
                "title": item.get("title", ""),
                "url": item.get("link", ""),
                "snippet": item.get("snippet", ""),
                "source": "serpapi",
                "date": item.get("date", ""),
            })
        return results
    except Exception as e:
        logger.error(f"SerpAPI 검색 실패: {e}")
        return []


def _search_with_google_cse(query: str, days_back: int) -> list[dict]:
    """Google Custom Search Engine API를 사용한 검색"""
    try:
        date_restrict = f"d{days_back}"
        params = {
            "key": GOOGLE_API_KEY,
            "cx": GOOGLE_CSE_ID,
            "q": query,
            "num": 10,
            "dateRestrict": date_restrict,
            "lr": "lang_ko|lang_en",
        }
        resp = requests.get(
            "https://www.googleapis.com/customsearch/v1",
            params=params,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()

        results = []
        for item in data.get("items", []):
            results.append({
                "title": item.get("title", ""),
                "url": item.get("link", ""),
                "snippet": item.get("snippet", ""),
                "source": "google_cse",
                "date": item.get("pagemap", {})
                .get("metatags", [{}])[0]
                .get("article:published_time", ""),
            })
        return results
    except Exception as e:
        logger.error(f"Google CSE 검색 실패: {e}")
        return []


def _search_with_scraping(query: str, days_back: int) -> list[dict]:
    """API 없이 기본 웹 스크래핑으로 검색 (폴백)"""
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }
        url = f"https://www.google.com/search?q={quote_plus(query)}&tbs=qdr:w&hl=ko"
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        results = []

        for g in soup.select("div.g")[:10]:
            title_el = g.select_one("h3")
            link_el = g.select_one("a")
            snippet_el = g.select_one("div.VwiC3b")

            if title_el and link_el:
                href = link_el.get("href", "")
                if href.startswith("/url?q="):
                    href = href.split("/url?q=")[1].split("&")[0]

                results.append({
                    "title": title_el.get_text(),
                    "url": href,
                    "snippet": snippet_el.get_text() if snippet_el else "",
                    "source": "scraping",
                    "date": "",
                })
        return results
    except Exception as e:
        logger.error(f"웹 스크래핑 검색 실패: {e}")
        return []


def fetch_page_content(url: str, max_length: int = 5000) -> str:
    """웹페이지의 본문 텍스트를 가져옵니다."""
    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        # 불필요한 태그 제거
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        text = soup.get_text(separator="\n", strip=True)
        return text[:max_length]
    except Exception as e:
        logger.error(f"페이지 콘텐츠 가져오기 실패 ({url}): {e}")
        return ""
