"""웹 검색을 통한 경쟁사 정보 수집 모듈"""

import logging
import os
import time
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Google Custom Search API 또는 SerpAPI 사용
SERPAPI_KEY = os.environ.get("SERPAPI_KEY", "")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY", "")
GOOGLE_CSE_ID = os.environ.get("GOOGLE_CSE_ID", "")


def search_competitor(competitor: dict, days_back: int = 7, previous_urls: set[str] = None) -> list[dict]:
    """경쟁사에 대한 최근 정보를 웹에서 검색합니다. 이전 주 URL은 제외합니다."""
    comp_name = competitor.get("name", "")
    prev_urls = previous_urls or set()
    all_results = []

    for keyword in competitor.get("keywords", []):
        results = _perform_search(keyword, days_back)
        all_results.extend(results)
        time.sleep(1)  # Rate limiting

    # 중복 제거 + 무관한 도메인 필터링 + 관련성 필터링 + 전주 중복 제거
    seen_urls = set()
    unique_results = []
    skipped_prev = 0
    for r in all_results:
        url = r["url"]
        if url in seen_urls or _should_skip_url(url):
            continue
        if url in prev_urls:
            skipped_prev += 1
            continue
        if not _is_relevant_result(r, comp_name):
            logger.debug(f"  관련성 낮은 결과 제외: {r['title'][:60]}")
            continue
        seen_urls.add(url)
        unique_results.append(r)

    if skipped_prev:
        logger.info(f"  [{comp_name}] 전주 중복 {skipped_prev}건 제외")

    return unique_results


# 관련성 판단용 eSIM/로밍 키워드
_ESIM_KEYWORDS = [
    "esim", "이심", "로밍", "roaming", "sim", "유심", "데이터",
    "travel", "여행", "통신", "요금", "pricing", "plan",
    "mobile", "모바일", "앱", "app",
]


def _is_relevant_result(result: dict, competitor_name: str) -> bool:
    """검색 결과가 해당 경쟁사 및 eSIM 서비스와 관련 있는지 확인합니다."""
    text = f"{result.get('title', '')} {result.get('snippet', '')}".lower()
    comp_lower = competitor_name.lower()

    # 경쟁사 이름이 제목/요약에 포함되면 관련 있음
    if comp_lower in text:
        return True

    # eSIM/로밍 관련 키워드가 2개 이상 포함되면 관련 있음
    match_count = sum(1 for kw in _ESIM_KEYWORDS if kw in text)
    return match_count >= 2


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
            "tbs": "qdr:w",  # 최근 1주일
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


def fetch_page_content(url: str, max_length: int = 5000) -> dict:
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

        title = soup.title.get_text(strip=True) if soup.title else ""

        # 불필요한 태그 제거
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        text = soup.get_text(separator="\n", strip=True)
        return {"url": url, "title": title, "content": text[:max_length]}
    except Exception as e:
        logger.error(f"페이지 콘텐츠 가져오기 실패 ({url}): {e}")
        return {"url": url, "title": "", "content": ""}


# 스크래핑이 차단되거나 eSIM/로밍과 무관한 도메인
SKIP_DOMAINS = [
    # SNS / 동영상
    "reddit.com", "facebook.com", "instagram.com", "tiktok.com",
    "twitter.com", "x.com", "linkedin.com", "threads.com",
    "youtube.com", "youtu.be", "pinterest.com",
    # 백과 / 위키
    "namu.wiki", "wikipedia.org",
    # 구인 / 리모트 잡
    "wantapply.com", "dailyremote.com", "remoteok.com", "weworkremotely.com",
    # 개발자 / 기술 (eSIM 무관)
    "dev.to", "github.com", "stackoverflow.com",
    # 쇼핑 / 마켓플레이스
    "alibaba.com", "aliexpress.com", "mozillion.com",
    # 게임 / 커뮤니티
    "inven.co.kr", "dcinside.com", "fmkorea.com",
    # 여행 (경쟁사 분석과 무관한 여행 사이트)
    "trip.com", "kkday.com", "klook.com",
    # APK / 앱 분석
    "apkmirror.com", "appbrain.com",
    # 여행사 / 부동산 / 기타 무관
    "hanatour.com", "realhouse.hu", "rpakr.com",
    "tesztevok.hu", "cybernews.com", "purrweb.com",
    "contactcentertechnologyinsights.com", "vocus.cc",
]


def _should_skip_url(url: str) -> bool:
    """스크래핑이 차단되는 도메인인지 확인합니다."""
    return any(domain in url for domain in SKIP_DOMAINS)


def fetch_pages_for_results(search_results: list[dict], max_pages: int = 5) -> list[dict]:
    """검색 결과 중 상위 N개의 페이지 본문을 가져옵니다."""
    pages = []
    fetched = 0
    for result in search_results:
        if fetched >= max_pages:
            break
        url = result.get("url", "")
        if not url or _should_skip_url(url):
            continue
        logger.info(f"    페이지 수집: {url[:80]}...")
        page = fetch_page_content(url)
        if page["content"]:
            pages.append(page)
            fetched += 1
        time.sleep(0.5)
    return pages
