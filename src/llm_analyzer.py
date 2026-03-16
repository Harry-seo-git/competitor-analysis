"""LLM 기반 경쟁사 분석 모듈

지원 백엔드:
  1. Claude API (ANTHROPIC_API_KEY) - 분석 엔진
  2. 키워드 기반 폴백 - API 없이 동작
"""

import json
import logging
import os

import requests

logger = logging.getLogger(__name__)

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

ANALYSIS_PROMPT = """당신은 eSIM/로밍 서비스 '유심사'의 경쟁 전략 분석가입니다.
아래는 '{competitor_name}' 경쟁사에 대한 최근 웹 검색 결과와 페이지 내용입니다.

## 검색 결과
{search_data}

## 분석 요청

⚠️ 중요: '{competitor_name}'의 eSIM/로밍 서비스와 직접 관련된 정보만 분석하세요. 무관한 콘텐츠는 무시하세요.

위 정보를 바탕으로 **유심사 관점에서** 다음을 분석해주세요:

1. **UX/UI 변경사항**: 앱이나 웹사이트의 디자인, 사용자 경험 관련 변화
2. **새로운 기능**: 새로 출시되거나 업데이트된 기능
3. **요금/프로모션**: 가격 변경, 할인, 이벤트
4. **기타 주요 동향**: 지역 확대, 파트너십 등

각 항목에 대해:
- 변경 내용을 구체적으로 설명
- **유심사가 취해야 할 대응 액션** 1줄 제시 (단순 "주시" 대신 구체적 액션 권장)
- 해당 정보가 없으면 빈 배열로 반환
- 관련성이 불확실한 정보는 포함하지 마세요

반드시 아래 JSON 형식으로만 응답하세요:
{{
  "ux_changes": [{{"title": "변경 제목", "description": "구체적 설명", "impact": "유심사 권장 액션", "source_url": "출처 URL"}}],
  "new_features": [{{"title": "기능명", "description": "설명", "impact": "유심사 권장 액션", "source_url": "URL"}}],
  "pricing": [{{"title": "변경 내용", "description": "설명", "impact": "유심사 권장 액션", "source_url": "URL"}}],
  "other": [{{"title": "제목", "description": "설명", "impact": "유심사 권장 액션", "source_url": "URL"}}],
  "threat_score": {{
    "score": 1~10,
    "level": "높음/중간/낮음",
    "reason": "위협도 판단 근거 1줄",
    "signal_type": "시그널/노이즈"
  }},
  "summary": "이 경쟁사의 이번 주 핵심 동향과 유심사 대응 포인트 1-2줄"
}}

threat_score 기준 (시그널 vs 노이즈를 반드시 구분):
- **시그널** (실제 위협, 즉각 대응 필요):
  - 높음(7-10): 유심사와 직접 경쟁하는 가격 인하, 유심사에 없는 핵심 기능 출시, 대규모 UX 개편
  - 중간(4-6): 유심사도 보유한 기능의 개선, 지역적 프로모션, 부분 UI 변경
- **노이즈** (참고만, 즉각 대응 불필요):
  - 낮음(1-3): 경미한 UI 수정, 유심사와 무관한 시장의 변화, 일반적 마케팅 활동, 루머성 정보
"""

EXECUTIVE_SUMMARY_PROMPT = """당신은 '유심사'의 전략 컨설턴트입니다.
아래는 이번 주 경쟁사 분석 결과입니다.

{all_analyses_text}

위 분석을 바탕으로 경영진을 위한 핵심 요약을 작성해주세요.

반드시 아래 JSON 형식으로만 응답하세요:
{{
  "headline": "이번 주 경쟁 환경을 한 줄로 요약 (30자 이내)",
  "top_threats": [
    {{"competitor": "경쟁사명", "action": "경쟁사 동향 요약", "impact": "유심사에 미치는 영향", "urgency": "즉시대응/주시/참고"}}
  ],
  "opportunities": [
    {{"area": "기회 영역", "description": "구체적 기회 설명", "action": "유심사 권장 액션"}}
  ],
  "risk_level": "높음/보통/낮음",
  "risk_reason": "위험도 판단 근거 1줄"
}}

top_threats는 최대 3개, opportunities는 최대 2개만 선별해주세요.
정보가 부족하면 빈 배열로 반환하세요.
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
    else:
        logger.warning("ANTHROPIC_API_KEY 미설정. 키워드 기반 폴백으로 동작합니다.")
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
    else:
        return _analyze_with_fallback(competitor_name, search_results, page_contents)


def generate_executive_summary(all_analyses: list[dict]) -> dict:
    """전체 분석 결과를 경영진용 핵심 요약으로 생성합니다."""
    backend = get_active_backend()

    analyses_text = _format_analyses_text(all_analyses)

    if not analyses_text.strip() or all(a.get("summary", "") == "이번 주 특이사항 없음" for a in all_analyses):
        return {
            "headline": "이번 주 특별한 경쟁사 동향 없음",
            "top_threats": [],
            "opportunities": [],
            "risk_level": "낮음",
            "risk_reason": "경쟁사 활동이 감지되지 않았습니다.",
        }

    if backend != "claude":
        return _fallback_executive_summary(all_analyses)

    prompt = EXECUTIVE_SUMMARY_PROMPT.format(all_analyses_text=analyses_text)
    result = _call_claude(prompt)
    parsed = _parse_json_response(result)
    if parsed and "headline" in parsed:
        return parsed
    return _fallback_executive_summary(all_analyses)


def _fallback_executive_summary(all_analyses: list[dict]) -> dict:
    """LLM 없이 키워드 기반 Executive Summary를 생성합니다."""
    active = [a for a in all_analyses if a.get("ux_changes") or a.get("new_features") or a.get("pricing")]
    high_threats = [a for a in all_analyses if a.get("threat_score", {}).get("score", 0) >= 7]

    headline = f"경쟁사 {len(active)}곳에서 변화 감지" if active else "이번 주 특별한 동향 없음"

    threats = []
    for a in sorted(all_analyses, key=lambda x: x.get("threat_score", {}).get("score", 0), reverse=True)[:3]:
        if a.get("ux_changes") or a.get("new_features") or a.get("pricing"):
            threats.append({
                "competitor": a["name"],
                "action": a.get("summary", ""),
                "impact": a.get("threat_score", {}).get("reason", "상세 확인 필요"),
                "urgency": "즉시대응" if a.get("threat_score", {}).get("score", 0) >= 7 else "주시",
            })

    risk_level = "높음" if high_threats else ("보통" if active else "낮음")

    return {
        "headline": headline,
        "top_threats": threats,
        "opportunities": [],
        "risk_level": risk_level,
        "risk_reason": f"위협도 높은 경쟁사: {', '.join(a['name'] for a in high_threats)}" if high_threats else "큰 위협 없음",
    }


def generate_suggestions(all_analyses: list[dict]) -> list[dict]:
    """전체 분석 결과를 바탕으로 전략 제안을 생성합니다."""
    backend = get_active_backend()

    analyses_text = _format_analyses_text(all_analyses)

    if not analyses_text.strip() or all(a.get("summary", "") == "이번 주 특이사항 없음" for a in all_analyses):
        return [{"priority": "낮음", "category": "모니터링", "action": "이번 주 특별한 경쟁사 동향이 감지되지 않았습니다. 정기적인 모니터링을 계속하세요.", "reason": "탐지된 변화 없음"}]

    prompt = SUGGESTION_PROMPT.format(all_analyses_text=analyses_text)

    if backend == "claude":
        result = _call_claude(prompt)
    else:
        return _fallback_suggestions(all_analyses)

    parsed = _parse_json_response(result)
    suggestions = parsed.get("suggestions", _fallback_suggestions(all_analyses))
    if not isinstance(suggestions, list):
        return _fallback_suggestions(all_analyses)
    return suggestions


# ──────────────────────────────────────────────
# Claude API
# ──────────────────────────────────────────────

def _analyze_with_claude(prompt: str, competitor_name: str) -> dict:
    result = _call_claude(prompt)
    parsed = _parse_json_response(result)
    if parsed:
        parsed["name"] = competitor_name
        _normalize_analysis(parsed)
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
                "max_tokens": 2048,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=90,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["content"][0]["text"]
    except Exception as e:
        logger.error(f"Claude API 호출 실패: {e}")
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

def _format_analyses_text(all_analyses: list[dict]) -> str:
    """분석 결과를 LLM 프롬프트용 텍스트로 포맷합니다."""
    parts = []
    for a in all_analyses:
        lines = [f"\n### {a['name']}", f"요약: {a.get('summary', '정보 없음')}"]
        threat = a.get("threat_score", {})
        if threat.get("score"):
            lines.append(f"위협도: {threat.get('score')}/10 ({threat.get('level', '')}) - {threat.get('reason', '')}")
        for key, label in [("ux_changes", "UX"), ("new_features", "기능"), ("pricing", "요금")]:
            for item in a.get(key, []):
                if isinstance(item, dict):
                    lines.append(f"- [{label}] {item.get('title', '')}: {item.get('description', '')}")
                elif isinstance(item, str):
                    lines.append(f"- [{label}] {item}")
        parts.append("\n".join(lines))
    return "\n".join(parts)


def _normalize_analysis(analysis: dict) -> None:
    """LLM 응답의 각 리스트 항목이 dict 형태인지 보장합니다."""
    list_keys = ["ux_changes", "new_features", "pricing", "other"]
    for key in list_keys:
        items = analysis.get(key, [])
        if not isinstance(items, list):
            analysis[key] = []
            continue
        normalized = []
        for item in items:
            if isinstance(item, dict):
                normalized.append(item)
            elif isinstance(item, str):
                normalized.append({
                    "title": item[:100],
                    "description": item,
                    "impact": "",
                    "source_url": "",
                })
        analysis[key] = normalized


def _format_search_data(search_results: list[dict], page_contents: list[dict]) -> str:
    """검색 결과와 페이지 내용을 LLM 프롬프트용 텍스트로 포맷합니다."""
    parts = []

    for i, r in enumerate(search_results[:5], 1):
        parts.append(f"### 검색 결과 {i}")
        parts.append(f"- 제목: {r['title']}")
        parts.append(f"- URL: {r['url']}")
        parts.append(f"- 요약: {r['snippet']}")
        parts.append("")

    for p in page_contents[:3]:
        parts.append(f"### 페이지 본문 ({p['url']})")
        parts.append(p.get("content", "")[:2000])
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
        "threat_score": {"score": 1, "level": "낮음", "reason": "분석 데이터 없음"},
        "summary": "이번 주 특이사항 없음",
    }
