"""주간 트렌드 비교 모듈

이전 주 분석 결과와 비교하여 트렌드를 파악합니다.
"""

import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


def load_history(history_dir: str) -> list[dict]:
    """가장 최근 히스토리를 로드합니다."""
    history_path = Path(history_dir)
    if not history_path.exists():
        return []

    files = sorted(history_path.glob("analysis_*.json"), reverse=True)
    if not files:
        return []

    try:
        return json.loads(files[0].read_text(encoding="utf-8"))
    except (json.JSONDecodeError, IOError) as e:
        logger.warning(f"히스토리 로드 실패: {e}")
        return []


def load_previous_urls(history: list[dict]) -> set[str]:
    """이전 분석 결과에서 사용된 URL 목록을 추출합니다 (중복 방지용).

    Args:
        history: load_history()로 이미 로드한 히스토리 데이터
    """
    urls = set()
    for entry in history:
        for url in entry.get("used_urls", []):
            urls.add(url)
    if urls:
        logger.info(f"이전 주 사용 URL {len(urls)}개 로드 (중복 체크용)")
    return urls


def save_history(analyses: list[dict], history_dir: str) -> None:
    """현재 분석 결과를 히스토리로 저장합니다."""
    history_path = Path(history_dir)
    history_path.mkdir(parents=True, exist_ok=True)

    # 직렬화 가능한 데이터만 저장
    serializable = []
    for a in analyses:
        # 분석에 사용된 URL 수집 (중복 체크용)
        used_urls = set()
        for key in ("ux_changes", "new_features", "pricing", "other"):
            for item in a.get(key, []):
                if isinstance(item, dict) and item.get("source_url"):
                    used_urls.add(item["source_url"])

        # 앱 평점 정보 추출 (추이 추적용)
        app_ratings = []
        for app in a.get("app_info", []):
            if app.get("rating"):
                app_ratings.append({
                    "platform": app.get("platform", ""),
                    "rating": app.get("rating", 0),
                    "rating_count": app.get("rating_count", 0),
                    "version": app.get("version", ""),
                })

        entry = {
            "name": a.get("name", ""),
            "region": a.get("region", ""),
            "summary": a.get("summary", ""),
            "ux_changes": len(a.get("ux_changes", [])),
            "new_features": len(a.get("new_features", [])),
            "pricing": len(a.get("pricing", [])),
            "other": len(a.get("other", [])),
            "app_info": a.get("app_info", []),
            "app_ratings": app_ratings,
            "used_urls": list(used_urls),
        }
        serializable.append(entry)

    filename = f"analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    filepath = history_path / filename
    filepath.write_text(json.dumps(serializable, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"히스토리 저장: {filepath}")

    # 오래된 히스토리 정리 (최근 12주만 유지)
    files = sorted(history_path.glob("analysis_*.json"), reverse=True)
    for old_file in files[12:]:
        old_file.unlink()
        logger.info(f"오래된 히스토리 삭제: {old_file.name}")


def load_rating_history(history_dir: str, weeks: int = 8) -> dict[str, list[dict]]:
    """최근 N주간의 앱 평점 추이를 로드합니다.

    Returns:
        {경쟁사명: [{"date": "2026-03-07", "iOS": 4.5, "Android": 4.2}, ...]}
    """
    history_path = Path(history_dir)
    if not history_path.exists():
        return {}

    files = sorted(history_path.glob("analysis_*.json"), reverse=True)[:weeks]
    files.reverse()  # 오래된 것부터 정렬

    rating_history: dict[str, list[dict]] = {}

    for f in files:
        # 파일명에서 날짜 추출: analysis_20260314_010604.json
        date_str = f.stem.replace("analysis_", "")[:8]
        try:
            date_label = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
        except (IndexError, ValueError):
            continue

        try:
            entries = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, IOError):
            continue

        for entry in entries:
            name = entry.get("name", "")
            if not name:
                continue

            ratings_data = {"date": date_label}
            for app_rating in entry.get("app_ratings", []):
                platform = app_rating.get("platform", "")
                rating = app_rating.get("rating", 0)
                if platform and rating:
                    ratings_data[platform] = rating

            if len(ratings_data) > 1:  # date 외에 데이터가 있을 때만
                rating_history.setdefault(name, []).append(ratings_data)

    return rating_history


def load_release_history(history_dir: str, weeks: int = 12) -> dict[str, list[dict]]:
    """최근 N주간의 릴리즈 이력을 로드합니다 (기능 출시 속도 비교용).

    Returns:
        {경쟁사명: [{"date": "2026-03-07", "ux_changes": 2, "new_features": 1, "pricing": 0, "total": 3}, ...]}
    """
    history_path = Path(history_dir)
    if not history_path.exists():
        return {}

    files = sorted(history_path.glob("analysis_*.json"), reverse=True)[:weeks]
    files.reverse()

    release_history: dict[str, list[dict]] = {}

    for f in files:
        date_str = f.stem.replace("analysis_", "")[:8]
        try:
            date_label = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
        except (IndexError, ValueError):
            continue

        try:
            entries = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, IOError):
            continue

        for entry in entries:
            name = entry.get("name", "")
            if not name:
                continue

            ux = entry.get("ux_changes", 0)
            feat = entry.get("new_features", 0)
            pricing = entry.get("pricing", 0)

            release_history.setdefault(name, []).append({
                "date": date_label,
                "ux_changes": ux,
                "new_features": feat,
                "pricing": pricing,
                "total": ux + feat + pricing,
            })

    return release_history


def compare_with_previous(current: list[dict], previous: list[dict]) -> dict:
    """이전 주 분석 결과와 비교합니다."""
    trend = {
        "has_previous": bool(previous),
        "competitors": {},
        "summary": "",
    }

    if not previous:
        trend["summary"] = "첫 번째 분석 (이전 데이터 없음)"
        return trend

    prev_map = {a["name"]: a for a in previous}

    active_competitors = []
    increased = []
    decreased = []

    for curr in current:
        name = curr.get("name", "")
        curr_total = (
            len(curr.get("ux_changes", []))
            + len(curr.get("new_features", []))
            + len(curr.get("pricing", []))
        )

        prev = prev_map.get(name, {})
        prev_total = prev.get("ux_changes", 0) + prev.get("new_features", 0) + prev.get("pricing", 0)

        diff = curr_total - prev_total
        comp_trend = {
            "current_total": curr_total,
            "previous_total": prev_total,
            "diff": diff,
            "direction": "up" if diff > 0 else ("down" if diff < 0 else "stable"),
        }

        # 앱 버전 변경 비교
        curr_apps = curr.get("app_info", [])
        prev_apps = prev.get("app_info", [])
        prev_versions = {a.get("platform", ""): a.get("version", "") for a in prev_apps}

        version_changes = []
        for app in curr_apps:
            platform = app.get("platform", "")
            curr_ver = app.get("version", "")
            prev_ver = prev_versions.get(platform, "")
            if curr_ver and prev_ver and curr_ver != prev_ver:
                version_changes.append(f"{platform}: {prev_ver} → {curr_ver}")

        comp_trend["version_changes"] = version_changes

        trend["competitors"][name] = comp_trend

        if curr_total > 0:
            active_competitors.append(name)
        if diff > 0:
            increased.append(name)
        elif diff < 0:
            decreased.append(name)

    # 트렌드 요약
    parts = []
    if active_competitors:
        parts.append(f"활발한 경쟁사: {', '.join(active_competitors)}")
    if increased:
        parts.append(f"활동 증가: {', '.join(increased)}")
    if decreased:
        parts.append(f"활동 감소: {', '.join(decreased)}")
    if not parts:
        parts.append("전주 대비 큰 변화 없음")

    trend["summary"] = " | ".join(parts)
    return trend
