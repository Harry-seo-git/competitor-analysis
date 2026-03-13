"""LLM 기반 경쟁사 분석 모듈

지원 백엔드:
  1. Claude API (ANTHROPIC_API_KEY) - 유료, 최고 품질
  2. Google Gemini (GEMINI_API_KEY) - 무료 티어 제공, 우수 품질
  3. 키워드 기반 폴백 - API 없이 동작
"""

import json
import logging
import os
import time

import requests

logger = logging.getLogger(__name__)

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

ANALYSIS_PROMPT = """당신은 eSIM/로밍 서비스 시장의 전문 UX 분석가입니다.
아래는 '{competitor_name}' 경쟁사에 대한 최근 웹 검색 결과와 페이지 내용입니다.

## 검색 결과
{search_data}

## 분석 요청
위 정보를 바탕으로 다음을 분석해주세요:

1. **UX/UI 변경사항**: 앱이나 웹사이트의 디자인, 사용자 경험 관련 변화 (가장 중요)
2. **새로운 기능**: 새로 출시되거나 업데이트된 기능
3. **요금/프로모션**: 가격 변경, 할인, 이벤트
4. **기타 주요 동향**: 지역 확대, 파트너십 등

각 항목에 대해:
- 변경 내용을 구체적으로 설명
- 유심사에 미치는 영향 또는 시사점 한 줄 제시
- 해당 정보가 없으면 "변경사항 없음"으로 표시

반드시 아래 JSON 형식으로만 응답하세요:
{{
  "ux_changes": [{{"title": "변경 제목", "description": "구체적 설명", "impact": "유심사 시사점", "source_url": "출처 URL"}}],
  "new_features": [{{"title": "기능명", "description": "설명", "impact": "시사점", "source_url": "URL"}}],
  "pricing": [{{"title": "변경 내용", "description": "설명", "impact": "시사점", "source_url": "URL"}}],
  "other": [{{"title": "제목", "description": "설명", "impact": "시사점", "source_url": "URL"}}],
  "summary": "이 경쟁사의 이번 주 핵심 동향 1-2줄 요약"
}}
"""

SUGGESTION_PROMPT = """당신은 '유심사'의 전략 컨설턴트입니다.
아래는 이번 주 경쟁사 분석 결과입니다.

{all_analyses_text}

위 분석을 바탕으로 유심사에 대한 구체적인 전략 제안을 3-5개 해주세요.
각 제안은 실행 가능하고 구체적이어야 합니다.

반드시 아래 JSON 형식으로만 응답하세요:
{{
  "suggestions": [
    {{"priority": "높음/중간/낮음", "category": "UX/기능/요금/마케팅", "action": "구체적 제안 내용", "reason": "근거"}}
  ]
}}
"""


def get_active_backend() -> str:
    """사용 가능한 LLM 백엔드를 확인합니다."""
    if ANTHROPIC_API_KEY:
        return "claude"
    elif GEMINI_API_KEY:
        return "gemini"
    else:
        return "fallback"


def analyze_competitor(competitor_name: str, search_results: list[dict], page_contents: list[dict]) -> dict:
    """경쟁사 데이터를 LLM으로 분석합니다."""
    backend = get_active_backend()
    logger.info(f"  분석 백엔드: {backend}")

    search_data = _format_search_data(search_results, page_contents)

    if not search_data.strip():
        return _empty_analysis(competitor_name)

    prompt = ANALYSIS_PROMPT.format(
        competitor_name=competitor_name,
        search_data=search_data,
    )

    if backend == "claude":
        return _analyze_with_claude(prompt, competitor_name)
    elif backend == "gemini":
        return _analyze_with_gemini(prompt, competitor_name)
    else:
        return _analyze_with_fallback(competitor_name, search_results, page_contents)


def generate_suggestions(all_analyses: list[dict]) -> list[dict]:
    """전체 분석 결과를 바탕으로 전략 제안을 생성합니다."""
    backend = get_active_backend()

    analyses_text = ""
    for a in all_analyses:
        analyses_text += f"\n### {a['name']}\n"
        analyses_text += f"요약: {a.get('summary', '정보 없음')}\n"
        for change in a.get("ux_changes", []):
            analyses_text += f"- [UX] {change['title']}: {change['description']}\n"
        for feat in a.get("new_features", []):
            analyses_text += f"- [기능] {feat['title']}: {feat['description']}\n"
        for price in a.get("pricing", []):
            analyses_text += f"- [요금] {price['title']}: {price['description']}\n"

    if not analyses_text.strip() or all(a.get("summary", "") == "이번 주 특이사항 없음" for a in all_analyses):
        return [{"priority": "낮음", "category": "모니터링", "action": "이번 주 특별한 경쟁사 동향이 감지되지 않았습니다. 정기적인 모니터링을 계속하세요.", "reason": "탐지된 변화 없음"}]

    prompt = SUGGESTION_PROMPT.format(all_analyses_text=analyses_text)

    if backend == "claude":
        result = _call_claude(prompt)
    elif backend == "gemini":
        result = _call_gemini(prompt)
    else:
        return _fallback_suggestions(all_analyses)

    parsed = _parse_json_response(result)
    return parsed.get("suggestions", _fallback_suggestions(all_analyses))


# ──────────────────────────────────────────────
# Claude API
# ──────────────────────────────────────────────

def _analyze_with_claude(prompt: str, competitor_name: str) -> dict:
    result = _call_claude(prompt)
    parsed = _parse_json_response(result)
    if parsed:
        parsed["name"] = competitor_name
        return parsed
    return _empty_analysis(competitor_name)


def _call_claude(prompt: str) -> str:
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
                "max_tokens": 2000,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["content"][0]["text"]
    except Exception as e:
        logger.error(f"Claude API 호출 실패: {e}")
        return ""


# ──────────────────────────────────────────────
# Google Gemini (무료)
# ──────────────────────────────────────────────

def _analyze_with_gemini(prompt: str, competitor_name: str) -> dict:
    result = _call_gemini(prompt)
    parsed = _parse_json_response(result)
    if parsed:
        parsed["name"] = competitor_name
        return parsed
    return _empty_analysis(competitor_name)


def _call_gemini(prompt: str, max_retries: int = 3) -> str:
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 2000,
            "responseMimeType": "application/json",
        },
    }

    for attempt in range(max_retries):
        try:
            resp = requests.post(
                url,
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=60,
            )
            if resp.status_code == 429:
                wait = 2 ** (attempt + 1)  # 2s, 4s, 8s
                logger.warning(f"Gemini 429 rate limit. {wait}초 대기 후 재시도 ({attempt + 1}/{max_retries})")
                time.sleep(wait)
                continue
            resp.raise_for_status()
            data = resp.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except requests.exceptions.HTTPError as e:
            if resp.status_code == 429 and attempt < max_retries - 1:
                continue
            logger.error(f"Gemini API 호출 실패: {e}")
            return ""
        except Exception as e:
            logger.error(f"Gemini API 호출 실패: {e}")
            return ""
    logger.error("Gemini API 최대 재시도 초과")
    return ""


# ──────────────────────────────────────────────
# 키워드 기반 폴백 (API 없이 동작)
# ──────────────────────────────────────────────

UX_KEYWORDS = [
    "ux", "ui", "디자인", "인터페이스", "사용자 경험", "화면", "레이아웃",
    "네비게이션", "메뉴", "버튼", "다크모드", "dark mode", "redesign",
    "리디자인", "개편", "온보딩", "onboarding", "user experience",
]

FEATURE_KEYWORDS = [
    "new feature", "신기능", "새로운 기능", "출시", "launch", "release",
    "업데이트", "update", "지원", "추가",
]

PRICING_KEYWORDS = [
    "요금", "가격", "price", "pricing", "할인", "discount", "무료",
    "프로모션", "이벤트", "쿠폰", "coupon", "캠페인",
]


def _analyze_with_fallback(competitor_name: str, search_results: list[dict], page_contents: list[dict]) -> dict:
    """키워드 매칭 기반 분석 (LLM 없이)"""
    analysis = _empty_analysis(competitor_name)

    all_texts = []
    for r in search_results:
        all_texts.append({"text": f"{r['title']} {r['snippet']}", "url": r["url"], "title": r["title"]})
    for p in page_contents:
        all_texts.append({"text": p.get("content", "")[:2000], "url": p["url"], "title": p.get("title", "")})

    for item in all_texts:
        text_lower = item["text"].lower()

        if any(kw in text_lower for kw in UX_KEYWORDS):
            analysis["ux_changes"].append({
                "title": item["title"][:100],
                "description": item["text"][:300],
                "impact": "상세 확인 필요",
                "source_url": item["url"],
            })
        if any(kw in text_lower for kw in FEATURE_KEYWORDS):
            analysis["new_features"].append({
                "title": item["title"][:100],
                "description": item["text"][:300],
                "impact": "상세 확인 필요",
                "source_url": item["url"],
            })
        if any(kw in text_lower for kw in PRICING_KEYWORDS):
            analysis["pricing"].append({
                "title": item["title"][:100],
                "description": item["text"][:300],
                "impact": "상세 확인 필요",
                "source_url": item["url"],
            })

    if analysis["ux_changes"] or analysis["new_features"] or analysis["pricing"]:
        parts = []
        if analysis["ux_changes"]:
            parts.append(f"UX 관련 {len(analysis['ux_changes'])}건")
        if analysis["new_features"]:
            parts.append(f"기능 관련 {len(analysis['new_features'])}건")
        if analysis["pricing"]:
            parts.append(f"요금 관련 {len(analysis['pricing'])}건")
        analysis["summary"] = f"키워드 기반 탐지: {', '.join(parts)}. LLM 연동 시 더 정확한 분석 가능."
    else:
        analysis["summary"] = "이번 주 특이사항 없음"

    return analysis


def _fallback_suggestions(all_analyses: list[dict]) -> list[dict]:
    suggestions = []
    ux_comps = [a["name"] for a in all_analyses if a.get("ux_changes")]
    feat_comps = [a["name"] for a in all_analyses if a.get("new_features")]
    price_comps = [a["name"] for a in all_analyses if a.get("pricing")]

    if ux_comps:
        suggestions.append({
            "priority": "높음", "category": "UX",
            "action": f"UX 변경 감지된 경쟁사({', '.join(ux_comps)})의 변경 내용을 상세 검토하세요.",
            "reason": "UX 변경 키워드 탐지",
        })
    if feat_comps:
        suggestions.append({
            "priority": "중간", "category": "기능",
            "action": f"새 기능을 출시한 경쟁사({', '.join(feat_comps)})를 분석하여 로드맵에 반영을 검토하세요.",
            "reason": "신기능 키워드 탐지",
        })
    if price_comps:
        suggestions.append({
            "priority": "중간", "category": "요금",
            "action": f"요금 변경 감지된 경쟁사({', '.join(price_comps)})의 가격을 비교 분석하세요.",
            "reason": "요금 키워드 탐지",
        })
    if not suggestions:
        suggestions.append({
            "priority": "낮음", "category": "모니터링",
            "action": "이번 주 특별한 동향 없음. 정기 모니터링을 계속하세요.",
            "reason": "탐지된 변화 없음",
        })
    return suggestions


# ──────────────────────────────────────────────
# 유틸리티
# ──────────────────────────────────────────────

def _format_search_data(search_results: list[dict], page_contents: list[dict]) -> str:
    """검색 결과와 페이지 내용을 LLM 프롬프트용 텍스트로 포맷합니다."""
    parts = []

    for i, r in enumerate(search_results[:10], 1):
        parts.append(f"### 검색 결과 {i}")
        parts.append(f"- 제목: {r['title']}")
        parts.append(f"- URL: {r['url']}")
        parts.append(f"- 요약: {r['snippet']}")
        parts.append("")

    for p in page_contents[:5]:
        parts.append(f"### 페이지 본문 ({p['url']})")
        parts.append(p.get("content", "")[:3000])
        parts.append("")

    return "\n".join(parts)


def _parse_json_response(text: str) -> dict:
    """LLM 응답에서 JSON을 파싱합니다."""
    if not text:
        return {}
    try:
        # JSON 블록이 ```json ... ``` 으로 감싸진 경우 처리
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        return json.loads(text.strip())
    except (json.JSONDecodeError, IndexError) as e:
        logger.warning(f"JSON 파싱 실패: {e}")
        # 중괄호로 시작하는 부분만 추출 시도
        try:
            start = text.index("{")
            end = text.rindex("}") + 1
            return json.loads(text[start:end])
        except (ValueError, json.JSONDecodeError):
            logger.error("JSON 파싱 최종 실패")
            return {}


def _empty_analysis(competitor_name: str) -> dict:
    return {
        "name": competitor_name,
        "ux_changes": [],
        "new_features": [],
        "pricing": [],
        "other": [],
        "summary": "이번 주 특이사항 없음",
    }
