"""Slack 웹훅을 통한 리포트 전송 모듈"""

import json
import logging
import os

import requests

logger = logging.getLogger(__name__)

SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")


def send_to_slack(report: str, webhook_url: str = None) -> bool:
    """마크다운 리포트를 Slack 채널로 전송합니다."""
    url = webhook_url or SLACK_WEBHOOK_URL
    if not url:
        logger.error("SLACK_WEBHOOK_URL이 설정되지 않았습니다.")
        return False

    # Slack 메시지 길이 제한 (약 40,000자)으로 분할 전송
    chunks = _split_report(report, max_length=3000)

    for i, chunk in enumerate(chunks):
        payload = _build_slack_payload(chunk, part=i + 1, total=len(chunks))
        success = _post_to_slack(url, payload)
        if not success:
            return False

    logger.info(f"Slack 전송 완료 ({len(chunks)}개 메시지)")
    return True


def _build_slack_payload(content: str, part: int = 1, total: int = 1) -> dict:
    """Slack 메시지 페이로드를 구성합니다."""
    header = ""
    if total > 1:
        header = f"📄 *경쟁사 분석 리포트 ({part}/{total})*\n\n"

    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": header + content,
            },
        },
    ]

    # 첫 번째 메시지에는 헤더 블록 추가
    if part == 1:
        blocks.insert(0, {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "🔍 유심사 경쟁사 주간 분석 리포트",
            },
        })
        blocks.insert(1, {"type": "divider"})

    return {"blocks": blocks}


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


def _split_report(report: str, max_length: int = 3000) -> list[str]:
    """긴 리포트를 Slack 메시지 크기에 맞게 분할합니다."""
    if len(report) <= max_length:
        return [report]

    chunks = []
    sections = report.split("\n---\n")

    current_chunk = ""
    for section in sections:
        if len(current_chunk) + len(section) + 5 > max_length:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = section
        else:
            current_chunk += "\n---\n" + section if current_chunk else section

    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return chunks if chunks else [report[:max_length]]
