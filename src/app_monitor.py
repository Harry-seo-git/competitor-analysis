"""앱스토어 모니터링 모듈

iOS App Store, Google Play Store에서 앱 정보(버전, 업데이트 노트, 평점, 리뷰)를 수집합니다.
"""

import json
import logging
import re
import time

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
}


def _safe_int(value, default: int = 0) -> int:
    """안전한 정수 변환. 변환 실패 시 기본값 반환."""
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def _safe_float(value, default: float = 0.0) -> float:
    """안전한 실수 변환. 변환 실패 시 기본값 반환."""
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


# ──────────────────────────────────────────────
# iOS App Store (iTunes Lookup API)
# ──────────────────────────────────────────────

def _extract_app_id(app_store_url: str) -> str:
    """App Store URL에서 앱 ID를 추출합니다."""
    match = re.search(r"id(\d+)", app_store_url)
    return match.group(1) if match else ""


def fetch_ios_app_info(app_store_url: str) -> dict:
    """iTunes Lookup API로 iOS 앱 정보를 가져옵니다."""
    app_id = _extract_app_id(app_store_url)
    if not app_id:
        logger.warning(f"App Store ID 추출 실패: {app_store_url}")
        return {}

    try:
        resp = requests.get(
            f"https://itunes.apple.com/lookup?id={app_id}&country=kr",
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

        if not data.get("results"):
            return {}

        app = data["results"][0]
        return {
            "platform": "iOS",
            "app_name": app.get("trackName", ""),
            "version": app.get("version", ""),
            "updated": app.get("currentVersionReleaseDate", ""),
            "release_notes": app.get("releaseNotes", ""),
            "rating": app.get("averageUserRating", 0),
            "rating_count": app.get("userRatingCount", 0),
            "url": app_store_url,
        }
    except Exception as e:
        logger.error(f"iOS 앱 정보 수집 실패: {e}")
        return {}


# ──────────────────────────────────────────────
# Google Play Store (웹 스크래핑)
# ──────────────────────────────────────────────

def fetch_android_app_info(play_store_url: str) -> dict:
    """Google Play Store 페이지에서 앱 정보를 스크래핑합니다."""
    try:
        resp = requests.get(
            play_store_url + "&hl=ko",
            headers=_HEADERS,
            timeout=15,
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        app_name = ""
        title_tag = soup.select_one("h1")
        if title_tag:
            app_name = title_tag.get_text(strip=True)

        # 메타데이터에서 정보 추출
        version = ""
        updated = ""
        rating = 0
        rating_count = 0

        # JSON-LD 스크립트에서 정보 추출 시도
        for script in soup.select('script[type="application/ld+json"]'):
            try:
                ld = json.loads(script.string)
                if ld.get("@type") == "SoftwareApplication":
                    version = ld.get("version", "")
                    rating_obj = ld.get("aggregateRating", {})
                    rating = rating_obj.get("ratingValue", 0)
                    rating_count = rating_obj.get("ratingCount", 0)
            except (json.JSONDecodeError, TypeError):
                continue

        # "업데이트 날짜" 텍스트 찾기
        for div in soup.select("div"):
            text = div.get_text(strip=True)
            if re.match(r"\d{4}\.\s?\d{1,2}\.\s?\d{1,2}\.", text):
                updated = text
                break

        # "새로운 기능" 섹션에서 릴리즈 노트 추출
        release_notes = ""
        for heading in soup.find_all(string=re.compile(r"새로운\s*기능|What's New", re.I)):
            parent = heading.find_parent()
            if parent:
                sibling = parent.find_next_sibling()
                if sibling:
                    release_notes = sibling.get_text(separator="\n", strip=True)[:1000]
                    break

        return {
            "platform": "Android",
            "app_name": app_name,
            "version": version,
            "updated": updated,
            "release_notes": release_notes,
            "rating": _safe_float(rating),
            "rating_count": _safe_int(rating_count),
            "url": play_store_url,
        }
    except Exception as e:
        logger.error(f"Android 앱 정보 수집 실패: {e}")
        return {}


# ──────────────────────────────────────────────
# 앱 리뷰 수집 (iOS)
# ──────────────────────────────────────────────

def fetch_ios_reviews(app_store_url: str, max_reviews: int = 20) -> list[dict]:
    """iTunes RSS API로 최근 iOS 앱 리뷰를 가져옵니다."""
    app_id = _extract_app_id(app_store_url)
    if not app_id:
        return []

    try:
        resp = requests.get(
            f"https://itunes.apple.com/kr/rss/customerreviews/id={app_id}/sortBy=mostRecent/json",
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

        entries = data.get("feed", {}).get("entry", [])
        reviews = []
        for entry in entries[:max_reviews]:
            if isinstance(entry, dict) and "content" in entry:
                reviews.append({
                    "author": entry.get("author", {}).get("name", {}).get("label", ""),
                    "rating": _safe_int(entry.get("im:rating", {}).get("label", "0")),
                    "title": entry.get("title", {}).get("label", ""),
                    "content": entry.get("content", {}).get("label", "")[:500],
                    "version": entry.get("im:version", {}).get("label", ""),
                })
        return reviews
    except Exception as e:
        logger.error(f"iOS 리뷰 수집 실패: {e}")
        return []


def analyze_review_sentiment(reviews: list[dict]) -> dict:
    """리뷰의 감성을 간단히 분석합니다 (키워드 기반)."""
    if not reviews:
        return {"positive": 0, "negative": 0, "neutral": 0, "avg_rating": 0, "top_complaints": [], "top_praises": []}

    positive_kw = ["좋", "편리", "최고", "추천", "만족", "빠르", "great", "love", "best", "easy", "good"]
    negative_kw = ["불편", "느리", "오류", "버그", "안됨", "실망", "worst", "bad", "slow", "error", "crash", "terrible"]

    pos = neg = neu = 0
    total_rating = 0
    complaints = []
    praises = []

    for r in reviews:
        text = f"{r.get('title', '')} {r.get('content', '')}".lower()
        rating = r.get("rating", 3)
        total_rating += rating

        has_pos = any(kw in text for kw in positive_kw)
        has_neg = any(kw in text for kw in negative_kw)

        if rating >= 4 or (has_pos and not has_neg):
            pos += 1
            if r.get("title"):
                praises.append(r["title"][:80])
        elif rating <= 2 or (has_neg and not has_pos):
            neg += 1
            if r.get("title"):
                complaints.append(r["title"][:80])
        else:
            neu += 1

    return {
        "positive": pos,
        "negative": neg,
        "neutral": neu,
        "avg_rating": round(total_rating / len(reviews), 1) if reviews else 0,
        "top_complaints": complaints[:5],
        "top_praises": praises[:5],
    }


# ──────────────────────────────────────────────
# 통합 수집
# ──────────────────────────────────────────────

def fetch_app_info(competitor: dict) -> list[dict]:
    """경쟁사의 iOS/Android 앱 정보를 모두 수집합니다."""
    results = []

    app_store_url = competitor.get("app_store", "")
    play_store_url = competitor.get("play_store", "")

    if app_store_url:
        ios_info = fetch_ios_app_info(app_store_url)
        if ios_info:
            # iOS 리뷰 감성 분석 추가
            reviews = fetch_ios_reviews(app_store_url)
            if reviews:
                ios_info["review_sentiment"] = analyze_review_sentiment(reviews)
                ios_info["recent_reviews_count"] = len(reviews)
            results.append(ios_info)
        time.sleep(0.5)

    if play_store_url:
        android_info = fetch_android_app_info(play_store_url)
        if android_info:
            results.append(android_info)
        time.sleep(0.5)

    return results


def fetch_all_app_info(competitors: list[dict]) -> dict[str, list[dict]]:
    """모든 경쟁사의 앱 정보를 수집합니다. {경쟁사명: [앱정보]} 형태로 반환."""
    all_info = {}
    for comp in competitors:
        name = comp.get("name", "")
        logger.info(f"[{name}] 앱스토어 정보 수집 중...")
        app_info = fetch_app_info(comp)
        if app_info:
            all_info[name] = app_info
            logger.info(f"  {len(app_info)}개 플랫폼 수집 완료")
        else:
            logger.info(f"  앱 정보 없음")
        time.sleep(1)
    return all_info
