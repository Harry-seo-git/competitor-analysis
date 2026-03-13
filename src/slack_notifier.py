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

    # 메시지 2: UX 하이라이트 (있을 때만)
    ux_msg = _build_ux_highlight_message(all_analyses)
    if ux_msg:
        messages.append(ux_msg)

    # 메시지 3: 국내 경쟁사 상세
    if domestic:
        messages.append(_build_competitor_message("🇰🇷 국내 경쟁사 상세 분석", domestic))

    # 메시지 4: 해외 경쟁사 상세
    if international:
        messages.append(_build_competitor_message("🌏 해외 경쟁사 상세 분석", international))

    # 메시지 5: 전략 제안
    messages.append(_build_suggestions_message(suggestions))

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
        "gemini": "Gemini (무료)",
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

        # 경쟁사 헤더 + 요약
        comp_text = f"*{name}*\n> {summary}"
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
        f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')} 자동 생성  |  상세 내용은 리포트 파일을 확인하세요."
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
