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


def save_history(analyses: list[dict], history_dir: str) -> None:
    """현재 분석 결과를 히스토리로 저장합니다."""
    history_path = Path(history_dir)
    history_path.mkdir(parents=True, exist_ok=True)

    # 직렬화 가능한 데이터만 저장
    serializable = []
    for a in analyses:
        entry = {
            "name": a.get("name", ""),
            "region": a.get("region", ""),
            "summary": a.get("summary", ""),
            "ux_changes": len(a.get("ux_changes", [])),
            "new_features": len(a.get("new_features", [])),
            "pricing": len(a.get("pricing", [])),
            "other": len(a.get("other", [])),
            "app_info": a.get("app_info", []),
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
