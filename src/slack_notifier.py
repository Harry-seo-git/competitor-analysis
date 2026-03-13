"""Slack 웹훅을 통한 리포트 전송 모듈"""

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
    chunks = _split_report(report)

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


def _split_report(report: str, max_length: int = 2800) -> list[str]:
    """긴 리포트를 Slack 메시지 크기에 맞게 분할합니다.

    1차: '---' 구분자로 분할
    2차: 큰 섹션은 '### ' 소제목 단위로 재분할
    3차: 그래도 크면 줄 단위로 분할
    """
    if len(report) <= max_length:
        return [report]

    # 1차: --- 구분자로 분할
    raw_sections = report.split("\n---\n")

    # 2차: 큰 섹션은 ### 소제목 단위로 재분할
    fine_sections = []
    for section in raw_sections:
        if len(section) <= max_length:
            fine_sections.append(section)
        else:
            # ### 소제목 기준으로 분할
            subsections = _split_by_headings(section, max_length)
            fine_sections.extend(subsections)

    # 3차: 청크로 병합 (max_length 이내)
    chunks = []
    current_chunk = ""
    for section in fine_sections:
        separator = "\n---\n" if current_chunk and not current_chunk.endswith("\n") else ""
        if len(current_chunk) + len(separator) + len(section) > max_length:
            if current_chunk:
                chunks.append(current_chunk.strip())
            # 단일 섹션이 아직 크면 줄 단위 분할
            if len(section) > max_length:
                line_chunks = _split_by_lines(section, max_length)
                chunks.extend(line_chunks)
                current_chunk = ""
            else:
                current_chunk = section
        else:
            current_chunk += separator + section if current_chunk else section

    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return chunks if chunks else [report[:max_length]]


def _split_by_headings(text: str, max_length: int) -> list[str]:
    """### 소제목 기준으로 텍스트를 분할합니다."""
    import re
    parts = re.split(r'(?=\n### )', text)
    if len(parts) <= 1:
        return [text]

    result = []
    current = ""
    # 첫 파트에 섹션 제목(## )이 있으면 보존
    header = ""
    first = parts[0]
    if first.strip().startswith("## "):
        header_end = first.find("\n", first.find("## "))
        if header_end > 0:
            header = first[:header_end + 1]

    for part in parts:
        if len(current) + len(part) > max_length:
            if current:
                result.append(current.strip())
            current = header + part if header and not part.strip().startswith("## ") else part
        else:
            current += part
    if current.strip():
        result.append(current.strip())
    return result


def _split_by_lines(text: str, max_length: int) -> list[str]:
    """줄 단위로 텍스트를 분할합니다."""
    lines = text.split("\n")
    chunks = []
    current = ""
    for line in lines:
        if len(current) + len(line) + 1 > max_length:
            if current:
                chunks.append(current.strip())
            current = line
        else:
            current += "\n" + line if current else line
    if current.strip():
        chunks.append(current.strip())
    return chunks
