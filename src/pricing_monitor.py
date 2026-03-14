"""요금제 모니터링 모듈

경쟁사 웹사이트에서 요금제 정보를 크롤링하고 비교 테이블을 생성합니다.
LLM을 활용하여 비정형 요금 정보를 구조화합니다.
"""

import json
import logging
import os
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

PRICING_DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "pricing"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
}

# 인기 여행지 (요금 비교 대상)
POPULAR_DESTINATIONS = ["일본", "태국", "미국", "유럽", "베트남"]


def fetch_pricing_page(url: str) -> str:
    """경쟁사 웹사이트에서 요금 관련 페이지 텍스트를 가져옵니다."""
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=20)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
            tag.decompose()

        return soup.get_text(separator="\n", strip=True)[:8000]
    except Exception as e:
        logger.error(f"요금 페이지 수집 실패 ({url}): {e}")
        return ""


def extract_pricing_with_llm(competitor_name: str, page_text: str) -> list[dict]:
    """LLM을 사용하여 페이지 텍스트에서 요금제 정보를 추출합니다."""
    has_llm = os.environ.get("GEMINI_API_KEY", "") or os.environ.get("ANTHROPIC_API_KEY", "")
    if not has_llm or not page_text:
        return []

    prompt = f"""아래는 '{competitor_name}' eSIM 서비스의 웹페이지 텍스트입니다.
이 텍스트에서 요금제 정보를 추출해주세요.

## 페이지 텍스트
{page_text[:5000]}

## 추출 요청
인기 여행지(일본, 태국, 미국, 유럽, 베트남)의 요금제를 찾아 아래 JSON 형식으로 응답하세요.
해당 정보가 없으면 빈 배열을 반환하세요.

반드시 JSON만 응답하세요:
{{
  "plans": [
    {{
      "destination": "국가/지역명",
      "data": "데이터 용량 (예: 1GB, 무제한)",
      "duration": "사용 기간 (예: 3일, 7일, 30일)",
      "price": "가격 (원화 또는 달러)",
      "currency": "KRW 또는 USD"
    }}
  ]
}}"""

    try:
        if os.environ.get("GEMINI_API_KEY"):
            return _extract_with_gemini(prompt)
        else:
            return _extract_with_claude(prompt)
    except Exception as e:
        logger.error(f"LLM 요금 추출 실패: {e}")
        return []


def _extract_with_gemini(prompt: str) -> list[dict]:
    try:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"gemini-2.0-flash:generateContent?key={os.environ['GEMINI_API_KEY']}"
        )
        resp = requests.post(
            url,
            headers={"Content-Type": "application/json"},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"},
            },
            timeout=60,
        )
        resp.raise_for_status()
        text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        data = json.loads(text)
        return data.get("plans", [])
    except Exception as e:
        logger.error(f"Gemini 요금 추출 실패: {e}")
        return []


def _extract_with_claude(prompt: str) -> list[dict]:
    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": os.environ["ANTHROPIC_API_KEY"],
                "content-type": "application/json",
                "anthropic-version": "2023-06-01",
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 2048,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=60,
        )
        resp.raise_for_status()
        text = resp.json()["content"][0]["text"]
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        data = json.loads(text.strip())
        return data.get("plans", [])
    except Exception as e:
        logger.error(f"Claude 요금 추출 실패: {e}")
        return []


def collect_pricing(competitors: list[dict]) -> dict[str, list[dict]]:
    """모든 경쟁사의 요금제 정보를 수집합니다."""
    all_pricing = {}
    for comp in competitors:
        name = comp.get("name", "")
        url = comp.get("url", "")
        if not url:
            continue

        logger.info(f"[{name}] 요금제 정보 수집 중...")
        page_text = fetch_pricing_page(url)
        if page_text:
            plans = extract_pricing_with_llm(name, page_text)
            if plans:
                all_pricing[name] = plans
                logger.info(f"  {len(plans)}개 요금제 수집")
            else:
                logger.info(f"  요금제 정보 추출 실패")
        else:
            logger.info(f"  페이지 수집 실패")

        time.sleep(2)

    # 요금 데이터 저장
    _save_pricing_data(all_pricing)
    return all_pricing


def _save_pricing_data(pricing: dict) -> None:
    """요금 데이터를 파일로 저장합니다."""
    PRICING_DATA_DIR.mkdir(parents=True, exist_ok=True)
    from datetime import datetime
    filename = f"pricing_{datetime.now().strftime('%Y%m%d')}.json"
    filepath = PRICING_DATA_DIR / filename
    filepath.write_text(json.dumps(pricing, ensure_ascii=False, indent=2), encoding="utf-8")


def generate_comparison_table(pricing: dict[str, list[dict]]) -> str:
    """요금제 비교 마크다운 테이블을 생성합니다."""
    if not pricing:
        return ""

    lines = ["## 요금제 비교 (인기 여행지)", ""]

    for dest in POPULAR_DESTINATIONS:
        dest_plans = []
        for comp_name, plans in pricing.items():
            for plan in plans:
                if dest in plan.get("destination", ""):
                    dest_plans.append({"competitor": comp_name, **plan})

        if not dest_plans:
            continue

        lines.append(f"### {dest}")
        lines.append("| 서비스 | 데이터 | 기간 | 가격 |")
        lines.append("|--------|--------|------|------|")
        for p in dest_plans:
            lines.append(
                f"| {p['competitor']} | {p.get('data', '-')} | "
                f"{p.get('duration', '-')} | {p.get('price', '-')} {p.get('currency', '')} |"
            )
        lines.append("")

    return "\n".join(lines)
