"""Slack 웹훅을 통한 리포트 전송 모듈 (Block Kit 기반)"""

import logging
import os
from datetime import datetime, timedelta

import requests

logger = logging.getLogger(__name__)

SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")

# Slack 제한: 메시지당 최대 50 블록, section text 최대 3000자
MAX_BLOCKS_PER_MESSAGE = 50


def send_report_to_slack(
    all_analyses: list[dict],
    suggestions: list[dict],
    backend: str,
    webhook_url: str = None,
    trend: dict = None,
    errors: list[dict] = None,
) -> bool:
    """구조화된 분석 데이터를 Slack Block Kit 메시지로 전송합니다."""
    url = webhook_url or SLACK_WEBHOOK_URL
    if not url:
        logger.error("SLACK_WEBHOOK_URL이 설정되지 않았습니다.")
        return False

    domestic = [a for a in all_analyses if a.get("region") == "domestic"]
    international = [a for a in all_analyses if a.get("region") == "international"]

    messages = []

    # 메시지 1: 헤더 + 주간 요약
    messages.append(_build_summary_message(domestic, international, backend))

    # 메시지 2: 트렌드 비교 (이전 주 대비, 있을 때만)
    if trend and trend.get("has_previous"):
        trend_msg = _build_trend_message(trend)
        if trend_msg:
            messages.append(trend_msg)

    # 메시지 3: UX 하이라이트 (있을 때만)
    ux_msg = _build_ux_highlight_message(all_analyses)
    if ux_msg:
        messages.append(ux_msg)

    # 메시지 4: 국내 경쟁사 상세
    if domestic:
        messages.append(_build_competitor_message("🇰🇷 국내 경쟁사 상세 분석", domestic))

    # 메시지 5: 해외 경쟁사 상세
    if international:
        messages.append(_build_competitor_message("🌏 해외 경쟁사 상세 분석", international))

    # 메시지 6: 앱 업데이트 현황
    app_msg = _build_app_update_message(all_analyses)
    if app_msg:
        messages.append(app_msg)

    # 메시지 7: 전략 제안
    messages.append(_build_suggestions_message(suggestions))

    # 메시지 8: 분석 실패 알림 (에러가 있을 때만)
    if errors:
        messages.append(_build_error_message(errors))

    # 전송
    for i, payload in enumerate(messages):
        success = _post_to_slack(url, payload)
        if not success:
            logger.error(f"Slack 전송 실패: 메시지 {i + 1}/{len(messages)}")
            return False

    logger.info(f"Slack 전송 완료 ({len(messages)}개 메시지)")
    return True


# ──────────────────────────────────────────────
# 메시지 빌더
# ──────────────────────────────────────────────


def _build_summary_message(domestic: list[dict], international: list[dict], backend: str) -> dict:
    """헤더 + 주간 요약 메시지"""
    now = datetime.now()
    week_ago = now - timedelta(days=7)

    backend_labels = {
        "claude": "Claude API",
        "fallback": "키워드 기반",
    }

    def count(comps, key):
        return sum(len(c.get(key, [])) for c in comps)

    d_ux, d_feat, d_price = count(domestic, "ux_changes"), count(domestic, "new_features"), count(domestic, "pricing")
    i_ux, i_feat, i_price = count(international, "ux_changes"), count(international, "new_features"), count(international, "pricing")

    summary_text = (
        f"*분석 기간*: {week_ago.strftime('%m/%d')} ~ {now.strftime('%m/%d')}  |  "
        f"*분석 엔진*: {backend_labels.get(backend, backend)}\n\n"
        f"```"
        f"{'구분':<6} {'경쟁사':>5} {'UX변경':>6} {'신기능':>6} {'요금변동':>6}\n"
        f"{'─'*38}\n"
        f"{'국내':<6} {len(domestic):>5} {d_ux:>6} {d_feat:>6} {d_price:>8}\n"
        f"{'해외':<6} {len(international):>5} {i_ux:>6} {i_feat:>6} {i_price:>8}\n"
        f"{'─'*38}\n"
        f"{'합계':<6} {len(domestic)+len(international):>5} {d_ux+i_ux:>6} {d_feat+i_feat:>6} {d_price+i_price:>8}"
        f"```"
    )

    blocks = [
        _header_block("📊 유심사 경쟁사 주간 분석 리포트"),
        _divider(),
        _section(summary_text),
    ]
    return {"blocks": blocks}


def _build_ux_highlight_message(all_analyses: list[dict]) -> dict | None:
    """UX 변경사항 하이라이트 메시지. 없으면 None 반환."""
    ux_items = []
    for a in all_analyses:
        for change in a.get("ux_changes", []):
            if isinstance(change, dict):
                ux_items.append({"competitor": a["name"], **change})

    if not ux_items:
        return None

    blocks = [
        _header_block("🎨 UX/UI 변경사항 하이라이트"),
        _divider(),
    ]

    for item in ux_items[:10]:  # 최대 10건
        title = item.get("title", "변경사항")
        desc = item.get("description", "")[:500]
        impact = item.get("impact", "")
        source = item.get("source_url", "")

        text = f"*[{item['competitor']}]  {title}*\n{desc}"
        if impact:
            text += f"\n💡 _시사점: {impact}_"
        if source:
            text += f"\n🔗 <{source}|출처>"

        blocks.append(_section(text))
        blocks.append(_divider())

    # 마지막 divider 제거
    if blocks and blocks[-1].get("type") == "divider":
        blocks.pop()

    return {"blocks": blocks}


def _build_competitor_message(title: str, competitors: list[dict]) -> dict:
    """경쟁사별 상세 분석 메시지"""
    blocks = [
        _header_block(title),
        _divider(),
    ]

    for comp in competitors:
        name = comp.get("name", "")
        summary = comp.get("summary", "특이사항 없음")

        # 경쟁사 헤더 + 요약 + 링크
        links = []
        if comp.get("url"):
            links.append(f"<{comp['url']}|웹>")
        if comp.get("app_store"):
            links.append(f"<{comp['app_store']}|iOS>")
        if comp.get("play_store"):
            links.append(f"<{comp['play_store']}|Android>")
        link_text = f"  ({' · '.join(links)})" if links else ""

        comp_text = f"*{name}*{link_text}\n> {summary}"

        # 사이트 변경 감지 표시
        site_changes = comp.get("site_changes", {})
        if site_changes.get("has_changes"):
            comp_text += f"\n🔄 _{site_changes.get('summary', '웹사이트 변경 감지')}_"

        blocks.append(_section(comp_text))

        # 카테고리별 변경사항
        details = _format_changes(comp)
        if details:
            blocks.append(_section(details))
        else:
            blocks.append(_context("변경사항 없음"))

        blocks.append(_divider())

    # 마지막 divider 제거
    if blocks and blocks[-1].get("type") == "divider":
        blocks.pop()

    # 블록 수 제한 처리
    if len(blocks) > MAX_BLOCKS_PER_MESSAGE:
        blocks = blocks[:MAX_BLOCKS_PER_MESSAGE - 1]
        blocks.append(_context("⚠️ 내용이 길어 일부가 생략되었습니다. 전체 내용은 리포트 파일을 확인하세요."))

    return {"blocks": blocks}


def _build_suggestions_message(suggestions: list[dict]) -> dict:
    """전략 제안 메시지"""
    blocks = [
        _header_block("💡 유심사 전략 제안"),
        _divider(),
    ]

    if not suggestions:
        blocks.append(_section("이번 주는 특별한 전략 제안 사항이 없습니다."))
        return {"blocks": blocks}

    priority_emoji = {"높음": "🔴", "중간": "🟡", "낮음": "🟢"}

    for i, s in enumerate(suggestions, 1):
        priority = s.get("priority", "")
        emoji = priority_emoji.get(priority, "⚪")
        category = s.get("category", "")
        action = s.get("action", "")
        reason = s.get("reason", "")

        text = f"{emoji} *[{priority}] {category}*\n{action}"
        if reason:
            text += f"\n📎 _{reason}_"

        blocks.append(_section(text))

    blocks.append(_divider())
    blocks.append(_context(
        f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')} 자동 생성"
    ))
    blocks.append(_context(
        "⚠️ 본 리포트는 AI 기반 자동 분석 결과로, 부정확하거나 누락된 정보가 포함될 수 있습니다. "
        "주요 내용은 원문 링크를 통해 반드시 확인해 주세요.\n"
        "💬 리포트 관련 문의: <@harry>"
    ))

    return {"blocks": blocks}


def _build_trend_message(trend: dict) -> dict | None:
    """이전 주 대비 트렌드 비교 메시지"""
    competitors = trend.get("competitors", {})
    if not competitors:
        return None

    direction_emoji = {"up": "📈", "down": "📉", "stable": "➡️"}

    blocks = [
        _header_block("📊 전주 대비 트렌드"),
        _divider(),
    ]

    lines = []
    for name, data in competitors.items():
        emoji = direction_emoji.get(data.get("direction", "stable"), "➡️")
        diff = data.get("diff", 0)
        diff_text = f"+{diff}" if diff > 0 else str(diff)
        curr = data.get("current_total", 0)
        lines.append(f"{emoji} *{name}*: {curr}건 ({diff_text})")

        # 앱 버전 변경
        for vc in data.get("version_changes", []):
            lines.append(f"    📱 {vc}")

    blocks.append(_section("\n".join(lines)))

    if trend.get("summary"):
        blocks.append(_context(trend["summary"]))

    return {"blocks": blocks}


def _build_app_update_message(all_analyses: list[dict]) -> dict | None:
    """앱 업데이트 현황 메시지"""
    has_app_info = any(a.get("app_info") for a in all_analyses)
    if not has_app_info:
        return None

    blocks = [
        _header_block("📱 앱 업데이트 현황"),
        _divider(),
    ]

    for a in all_analyses:
        apps = a.get("app_info", [])
        if not apps:
            continue

        lines = [f"*{a['name']}*"]
        for app in apps:
            platform = app.get("platform", "")
            version = app.get("version", "N/A")
            rating = app.get("rating", 0)
            rating_count = app.get("rating_count", 0)
            updated = app.get("updated", "")[:10]
            url = app.get("url", "")

            rating_str = f"⭐ {rating:.1f} ({rating_count:,})" if rating else "평점 없음"
            platform_emoji = "🍎" if platform == "iOS" else "🤖"
            link = f"<{url}|{platform}>" if url else platform

            lines.append(f"  {platform_emoji} {link}: v{version} | {rating_str} | {updated}")

            release_notes = app.get("release_notes", "")
            if release_notes:
                notes_preview = release_notes.replace("\n", " ")[:150]
                lines.append(f"    📝 _{notes_preview}_")

        blocks.append(_section("\n".join(lines)))

    if len(blocks) <= 2:
        return None

    return {"blocks": blocks}


def _build_error_message(errors: list[dict]) -> dict:
    """분석 실패 알림 메시지"""
    blocks = [
        _header_block("⚠️ 분석 실패 알림"),
        _divider(),
    ]

    lines = []
    for err in errors:
        name = err.get("name", "알 수 없음")
        error = err.get("error", "")[:300]
        lines.append(f"❌ *{name}*: {error}")

    blocks.append(_section("\n".join(lines)))
    blocks.append(_context(
        "위 경쟁사의 분석이 실패했습니다. 네트워크 상태 또는 API 키를 확인해 주세요."
    ))

    return {"blocks": blocks}


def _format_changes(comp: dict) -> str:
    """경쟁사의 카테고리별 변경사항을 텍스트로 포맷합니다."""
    parts = []

    categories = [
        ("ux_changes", "🎨 UX/UI"),
        ("new_features", "🆕 신기능"),
        ("pricing", "💰 요금/프로모션"),
        ("other", "📌 기타"),
    ]

    for key, label in categories:
        items = comp.get(key, [])
        if not items:
            continue
        lines = [f"*{label}*"]
        for item in items:
            if isinstance(item, dict):
                title = item.get("title", "")
                desc = item.get("description", "")[:200]
                source = item.get("source_url", "")
                line = f"  • {title}"
                if desc and desc != title:
                    line += f": {desc}"
                if source:
                    line += f" (<{source}|출처>)"
                lines.append(line)
            elif isinstance(item, str):
                lines.append(f"  • {item}")
        parts.append("\n".join(lines))

    return "\n\n".join(parts)


# ──────────────────────────────────────────────
# Block Kit 헬퍼
# ──────────────────────────────────────────────


def _header_block(text: str) -> dict:
    return {
        "type": "header",
        "text": {"type": "plain_text", "text": text[:150]},
    }


def _section(text: str) -> dict:
    return {
        "type": "section",
        "text": {"type": "mrkdwn", "text": text[:3000]},
    }


def _context(text: str) -> dict:
    return {
        "type": "context",
        "elements": [{"type": "mrkdwn", "text": text[:3000]}],
    }


def _divider() -> dict:
    return {"type": "divider"}


# ──────────────────────────────────────────────
# 전송
# ──────────────────────────────────────────────


def _post_to_slack(url: str, payload: dict) -> bool:
    """Slack 웹훅에 메시지를 전송합니다."""
    try:
        resp = requests.post(
            url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30,
        )
        if resp.status_code != 200:
            logger.error(f"Slack 전송 실패: {resp.status_code} - {resp.text}")
            return False
        return True
    except Exception as e:
        logger.error(f"Slack 전송 중 오류: {e}")
        return False
