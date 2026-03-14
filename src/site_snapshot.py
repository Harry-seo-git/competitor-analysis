"""경쟁사 웹사이트 스냅샷 및 변경 감지 모듈

경쟁사 웹사이트를 주기적으로 스냅샷하고 이전 대비 변경사항을 감지합니다.
"""

import hashlib
import json
import logging
import re
import time
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

SNAPSHOTS_DIR = Path(__file__).resolve().parent.parent / "data" / "snapshots"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
}


def _sanitize_name(name: str) -> str:
    """파일명에 안전한 문자열로 변환합니다."""
    return re.sub(r"[^\w\-]", "_", name).strip("_").lower()


def _extract_page_structure(html: str) -> dict:
    """HTML에서 구조적 정보를 추출합니다."""
    soup = BeautifulSoup(html, "html.parser")

    title = soup.title.get_text(strip=True) if soup.title else ""

    # 메타 정보
    meta_desc = ""
    meta_tag = soup.find("meta", attrs={"name": "description"})
    if meta_tag:
        meta_desc = meta_tag.get("content", "")

    # 주요 텍스트 추출 (nav/footer/script 제거)
    for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
        tag.decompose()

    # 주요 섹션 헤딩
    headings = []
    for h in soup.find_all(["h1", "h2", "h3"])[:20]:
        text = h.get_text(strip=True)
        if text:
            headings.append({"tag": h.name, "text": text[:200]})

    # 주요 링크 (내비게이션 구조 파악)
    links = []
    for a in soup.find_all("a", href=True)[:50]:
        href = a.get("href", "")
        text = a.get_text(strip=True)
        if text and not href.startswith(("javascript:", "#", "mailto:")):
            links.append({"text": text[:100], "href": href[:200]})

    # 본문 텍스트 요약
    body_text = soup.get_text(separator="\n", strip=True)[:5000]

    return {
        "title": title,
        "meta_description": meta_desc,
        "headings": headings,
        "links": links,
        "body_text": body_text,
        "content_hash": hashlib.md5(body_text.encode()).hexdigest(),
    }


def fetch_site_snapshot(url: str) -> dict:
    """웹사이트를 스냅샷합니다."""
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=20)
        resp.raise_for_status()
        structure = _extract_page_structure(resp.text)
        structure["url"] = url
        structure["fetched_at"] = datetime.now().isoformat()
        return structure
    except Exception as e:
        logger.error(f"사이트 스냅샷 실패 ({url}): {e}")
        return {}


def _load_previous_snapshot(name: str) -> dict:
    """이전 스냅샷을 로드합니다."""
    filepath = SNAPSHOTS_DIR / f"{_sanitize_name(name)}.json"
    if filepath.exists():
        try:
            return json.loads(filepath.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def _save_snapshot(name: str, snapshot: dict) -> None:
    """스냅샷을 저장합니다."""
    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    filepath = SNAPSHOTS_DIR / f"{_sanitize_name(name)}.json"
    filepath.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")


def detect_changes(name: str, current: dict) -> dict:
    """이전 스냅샷과 비교하여 변경사항을 감지합니다."""
    previous = _load_previous_snapshot(name)
    changes = {
        "has_changes": False,
        "title_changed": False,
        "content_changed": False,
        "headings_changed": False,
        "new_headings": [],
        "removed_headings": [],
        "summary": "",
    }

    if not previous:
        changes["summary"] = "첫 번째 스냅샷 (이전 데이터 없음)"
        _save_snapshot(name, current)
        return changes

    # 제목 변경
    if previous.get("title", "") != current.get("title", ""):
        changes["title_changed"] = True
        changes["has_changes"] = True

    # 콘텐츠 해시 변경
    if previous.get("content_hash", "") != current.get("content_hash", ""):
        changes["content_changed"] = True
        changes["has_changes"] = True

    # 헤딩 변경 감지
    prev_headings = {h["text"] for h in previous.get("headings", [])}
    curr_headings = {h["text"] for h in current.get("headings", [])}

    new_h = curr_headings - prev_headings
    removed_h = prev_headings - curr_headings

    if new_h or removed_h:
        changes["headings_changed"] = True
        changes["has_changes"] = True
        changes["new_headings"] = list(new_h)[:10]
        changes["removed_headings"] = list(removed_h)[:10]

    # 변경 요약
    parts = []
    if changes["title_changed"]:
        parts.append(f"제목 변경: '{previous.get('title', '')}' → '{current.get('title', '')}'")
    if changes["content_changed"]:
        parts.append("페이지 콘텐츠 변경 감지")
    if changes["new_headings"]:
        parts.append(f"새 섹션 추가: {', '.join(changes['new_headings'][:3])}")
    if changes["removed_headings"]:
        parts.append(f"섹션 제거: {', '.join(changes['removed_headings'][:3])}")

    changes["summary"] = " | ".join(parts) if parts else "변경사항 없음"

    # 현재 스냅샷 저장
    _save_snapshot(name, current)
    return changes


def monitor_all_sites(competitors: list[dict]) -> dict[str, dict]:
    """모든 경쟁사 사이트를 스냅샷하고 변경사항을 감지합니다."""
    results = {}
    for comp in competitors:
        name = comp.get("name", "")
        url = comp.get("url", "")
        if not url:
            continue

        logger.info(f"[{name}] 사이트 스냅샷 수집 중... ({url})")
        snapshot = fetch_site_snapshot(url)
        if snapshot:
            changes = detect_changes(name, snapshot)
            results[name] = changes
            if changes["has_changes"]:
                logger.info(f"  변경 감지: {changes['summary']}")
            else:
                logger.info(f"  변경사항 없음")
        else:
            results[name] = {"has_changes": False, "summary": "스냅샷 수집 실패"}

        time.sleep(1)

    return results
