"""요금제 모니터링 모듈

경쟁사 웹사이트에서 요금제 정보를 크롤링하고 비교 테이블을 생성합니다.
LLM을 활용하여 비정형 요금 정보를 구조화합니다.

최적화: 경쟁사를 배치로 묶어 LLM 호출 횟수를 최소화합니다.
"""

import json
import logging
import time
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from llm_analyzer import ANTHROPIC_API_KEY, _parse_json_response

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

# 요금 관련 키워드 (이 키워드가 없으면 LLM 호출 스킵)
_PRICING_KEYWORDS = [
    "원", "₩", "$", "usd", "krw", "price", "pricing", "plan",
    "요금", "가격", "데이터", "gb", "무제한", "unlimited",
    "day", "일", "주", "week",
]


def fetch_pricing_page(url: str) -> str:
    """경쟁사 웹사이트에서 요금 관련 페이지 텍스트를 가져옵니다."""
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=20)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
            tag.decompose()

        return soup.get_text(separator="\n", strip=True)[:8000]
    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 403:
            logger.warning(f"요금 페이지 접근 차단 ({url}): 봇 접근이 제한된 사이트입니다.")
        else:
            logger.error(f"요금 페이지 수집 실패 ({url}): {e}")
        return ""
    except Exception as e:
        logger.error(f"요금 페이지 수집 실패 ({url}): {e}")
        return ""


def _has_pricing_content(text: str) -> bool:
    """페이지에 요금 관련 키워드가 있는지 확인합니다."""
    text_lower = text.lower()
    return sum(1 for kw in _PRICING_KEYWORDS if kw in text_lower) >= 3


def _extract_pricing_batch_with_claude(batch: dict[str, str]) -> dict[str, list[dict]]:
    """여러 경쟁사의 요금 정보를 한 번의 API 호출로 추출합니다."""
    if not ANTHROPIC_API_KEY:
        return {}

    # 배치 프롬프트 조립
    sections = []
    for name, text in batch.items():
        sections.append(f"### {name}\n{text[:3000]}")

    combined_text = "\n\n---\n\n".join(sections)
    competitor_names = ", ".join(batch.keys())

    prompt = f"""아래는 여러 eSIM 서비스의 웹페이지 텍스트입니다.
각 서비스에서 인기 여행지(일본, 태국, 미국, 유럽, 베트남)의 요금제 정보를 추출해주세요.
해당 정보가 없는 서비스는 빈 배열로 반환하세요.

## 서비스별 페이지 텍스트
{combined_text}

반드시 JSON만 응답하세요:
{{
  {', '.join(f'"{name}": [{{"destination": "국가/지역명", "data": "용량", "duration": "기간", "price": "가격", "currency": "KRW/USD"}}]' for name in batch.keys())}
}}"""

    try:
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "content-type": "application/json",
                "anthropic-version": "2023-06-01",
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 4096,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=120,
        )
        resp.raise_for_status()
        text = resp.json()["content"][0]["text"]
        data = _parse_json_response(text)
        if not data:
            return {}

        # 결과 정리
        result = {}
        for name in batch.keys():
            plans = data.get(name, [])
            if isinstance(plans, list) and plans:
                result[name] = plans
        return result

    except Exception as e:
        logger.error(f"Claude 요금 배치 추출 실패: {e}")
        return {}


def collect_pricing(competitors: list[dict]) -> dict[str, list[dict]]:
    """모든 경쟁사의 요금제 정보를 수집합니다. 배치 처리로 API 호출을 최소화합니다."""
    # 1단계: 페이지 수집 + 키워드 필터링
    pages_with_pricing = {}
    for comp in competitors:
        name = comp.get("name", "")
        url = comp.get("url", "")
        if not url:
            continue

        logger.info(f"[{name}] 요금 페이지 수집 중...")
        page_text = fetch_pricing_page(url)
        if page_text and _has_pricing_content(page_text):
            pages_with_pricing[name] = page_text
            logger.info(f"  요금 키워드 감지 → LLM 분석 대상")
        else:
            logger.info(f"  요금 키워드 미감지 → 스킵")
        time.sleep(1)

    if not pages_with_pricing:
        logger.info("요금 정보가 있는 페이지가 없습니다.")
        _save_pricing_data({})
        return {}

    # 2단계: 배치 LLM 호출 (4개씩 묶어서)
    all_pricing = {}
    batch_size = 4
    names = list(pages_with_pricing.keys())

    for i in range(0, len(names), batch_size):
        batch_names = names[i:i + batch_size]
        batch = {n: pages_with_pricing[n] for n in batch_names}

        logger.info(f"요금 배치 추출: {', '.join(batch_names)}")
        result = _extract_pricing_batch_with_claude(batch)
        all_pricing.update(result)

        if i + batch_size < len(names):
            time.sleep(3)

    for name, plans in all_pricing.items():
        logger.info(f"  [{name}] {len(plans)}개 요금제 추출")

    _save_pricing_data(all_pricing)
    return all_pricing


def _save_pricing_data(pricing: dict) -> None:
    """요금 데이터를 파일로 저장합니다."""
    try:
        PRICING_DATA_DIR.mkdir(parents=True, exist_ok=True)
        filename = f"pricing_{datetime.now().strftime('%Y%m%d')}.json"
        filepath = PRICING_DATA_DIR / filename
        filepath.write_text(json.dumps(pricing, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as e:
        logger.warning(f"요금 데이터 저장 실패: {e}")


def _load_previous_pricing() -> dict:
    """가장 최근의 이전 요금 데이터를 로드합니다."""
    if not PRICING_DATA_DIR.exists():
        return {}
    files = sorted(PRICING_DATA_DIR.glob("pricing_*.json"), reverse=True)
    # 오늘 파일 제외, 그 이전 것 사용
    today_prefix = f"pricing_{datetime.now().strftime('%Y%m%d')}"
    for f in files:
        if not f.stem.startswith(today_prefix):
            try:
                return json.loads(f.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, IOError):
                continue
    return {}


def detect_pricing_changes(current: dict[str, list[dict]]) -> list[dict]:
    """이전 주 대비 가격 변동을 감지합니다."""
    previous = _load_previous_pricing()
    if not previous or not current:
        return []

    changes = []
    for comp_name, curr_plans in current.items():
        prev_plans = previous.get(comp_name, [])
        if not prev_plans:
            continue

        # 이전 요금 인덱싱: (destination, data, duration) → price
        prev_index = {}
        for p in prev_plans:
            key = (p.get("destination", ""), p.get("data", ""), p.get("duration", ""))
            prev_index[key] = p.get("price", "")

        for plan in curr_plans:
            key = (plan.get("destination", ""), plan.get("data", ""), plan.get("duration", ""))
            prev_price = prev_index.get(key)
            curr_price = plan.get("price", "")

            if prev_price and curr_price and prev_price != curr_price:
                changes.append({
                    "competitor": comp_name,
                    "destination": plan.get("destination", ""),
                    "data": plan.get("data", ""),
                    "duration": plan.get("duration", ""),
                    "previous_price": prev_price,
                    "current_price": curr_price,
                    "currency": plan.get("currency", ""),
                })

    if changes:
        logger.info(f"가격 변동 {len(changes)}건 감지")
    return changes


def generate_comparison_table(pricing: dict[str, list[dict]], price_changes: list[dict] = None) -> str:
    """요금제 비교 마크다운 테이블을 생성합니다."""
    if not pricing:
        return ""

    lines = ["## 요금제 비교 (인기 여행지)", ""]

    # 가격 변동 요약 (있으면 상단에 표시)
    if price_changes:
        lines.append("### ⚡ 가격 변동 감지")
        lines.append("| 서비스 | 여행지 | 요금제 | 이전 가격 | 현재 가격 |")
        lines.append("|--------|--------|--------|----------|----------|")
        for c in price_changes:
            lines.append(
                f"| {c['competitor']} | {c['destination']} | "
                f"{c['data']} / {c['duration']} | "
                f"{c['previous_price']} {c['currency']} | "
                f"**{c['current_price']} {c['currency']}** |"
            )
        lines.append("")

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
