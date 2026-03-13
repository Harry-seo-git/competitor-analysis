"""경쟁사 분석 리포트 생성 모듈"""

import logging
from datetime import datetime

from jinja2 import Template

logger = logging.getLogger(__name__)

REPORT_TEMPLATE = """# 🔍 유심사 경쟁사 주간 분석 리포트

**분석 기간**: {{ start_date }} ~ {{ end_date }}
**생성일시**: {{ generated_at }}

---

## 📊 주간 요약

| 구분 | 경쟁사 수 | 탐지된 변화 |
|------|-----------|-------------|
| 국내 | {{ domestic_count }} | {{ domestic_changes }} |
| 해외 | {{ international_count }} | {{ international_changes }} |

---

## 🇰🇷 국내 경쟁사 분석

{% for comp in domestic_competitors %}
### {{ comp.name }}
{% if comp.findings %}
{% for finding in comp.findings %}
- **{{ finding.category }}**: {{ finding.summary }}
  - 출처: [{{ finding.source_title }}]({{ finding.source_url }})
{% endfor %}
{% else %}
- 이번 주 특이사항 없음
{% endif %}

{% endfor %}

---

## 🌏 해외 경쟁사 분석

{% for comp in international_competitors %}
### {{ comp.name }}
{% if comp.findings %}
{% for finding in comp.findings %}
- **{{ finding.category }}**: {{ finding.summary }}
  - Source: [{{ finding.source_title }}]({{ finding.source_url }})
{% endfor %}
{% else %}
- No notable changes this week
{% endif %}

{% endfor %}

---

## 🎨 UX/UI 변경사항 하이라이트

{% if ux_highlights %}
{% for highlight in ux_highlights %}
### {{ highlight.competitor }} - {{ highlight.title }}
{{ highlight.description }}
{% if highlight.source_url %}- 참고: [{{ highlight.source_title }}]({{ highlight.source_url }}){% endif %}

{% endfor %}
{% else %}
이번 주 주요 UX/UI 변경사항이 탐지되지 않았습니다.
{% endif %}

---

## 💡 유심사 대응 제안

{% for suggestion in suggestions %}
{{ loop.index }}. {{ suggestion }}
{% endfor %}

---

*이 리포트는 자동으로 생성되었습니다. 상세 내용은 원문 링크를 참고해주세요.*
"""

UX_KEYWORDS = [
    "ux", "ui", "디자인", "인터페이스", "사용자 경험", "화면", "레이아웃",
    "네비게이션", "메뉴", "버튼", "다크모드", "dark mode", "redesign",
    "리디자인", "개편", "업데이트", "update", "new feature", "신기능",
    "새로운 기능", "앱 업데이트", "app update", "user experience",
    "user interface", "design", "navigation", "onboarding", "온보딩",
]

CATEGORY_KEYWORDS = {
    "UX/UI 변경": ["ux", "ui", "디자인", "인터페이스", "redesign", "리디자인", "개편", "design", "layout"],
    "새로운 기능": ["new feature", "신기능", "새로운 기능", "출시", "launch", "release"],
    "요금제 변경": ["요금", "가격", "price", "plan", "pricing", "할인", "discount"],
    "지역 확대": ["국가", "지역", "country", "region", "coverage", "커버리지"],
    "앱 업데이트": ["앱 업데이트", "app update", "버전", "version", "패치", "patch"],
    "프로모션": ["프로모션", "이벤트", "promotion", "event", "캠페인", "campaign", "쿠폰", "coupon"],
}


def categorize_finding(title: str, snippet: str) -> str:
    """검색 결과를 카테고리로 분류합니다."""
    text = (title + " " + snippet).lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return category
    return "기타"


def is_ux_related(title: str, snippet: str) -> bool:
    """UX/UI 관련 내용인지 판별합니다."""
    text = (title + " " + snippet).lower()
    return any(kw in text for kw in UX_KEYWORDS)


def analyze_competitor_results(competitor: dict, search_results: list[dict]) -> dict:
    """경쟁사별 검색 결과를 분석합니다."""
    findings = []
    for result in search_results:
        category = categorize_finding(result["title"], result["snippet"])
        findings.append({
            "category": category,
            "summary": result["snippet"][:200] if result["snippet"] else result["title"],
            "source_title": result["title"],
            "source_url": result["url"],
            "is_ux_related": is_ux_related(result["title"], result["snippet"]),
        })

    return {
        "name": competitor["name"],
        "region": competitor["region"],
        "findings": findings,
    }


def extract_ux_highlights(all_analyses: list[dict]) -> list[dict]:
    """모든 분석 결과에서 UX/UI 관련 하이라이트를 추출합니다."""
    highlights = []
    for analysis in all_analyses:
        for finding in analysis.get("findings", []):
            if finding.get("is_ux_related"):
                highlights.append({
                    "competitor": analysis["name"],
                    "title": finding["category"],
                    "description": finding["summary"],
                    "source_title": finding["source_title"],
                    "source_url": finding["source_url"],
                })
    return highlights


def generate_suggestions(all_analyses: list[dict], ux_highlights: list[dict]) -> list[str]:
    """분석 결과를 기반으로 대응 제안을 생성합니다."""
    suggestions = []

    # UX 변경 감지 시
    if ux_highlights:
        competitors_with_ux = set(h["competitor"] for h in ux_highlights)
        suggestions.append(
            f"UX/UI 변경이 감지된 경쟁사({', '.join(competitors_with_ux)})의 "
            f"변경 내용을 상세 검토하고 유심사 서비스에 적용 가능한 개선점을 도출하세요."
        )

    # 새로운 기능 출시 감지 시
    new_features = []
    for analysis in all_analyses:
        for f in analysis.get("findings", []):
            if f["category"] == "새로운 기능":
                new_features.append(analysis["name"])
                break
    if new_features:
        suggestions.append(
            f"새로운 기능을 출시한 경쟁사({', '.join(new_features)})의 "
            f"기능을 분석하여 유심사 로드맵에 반영을 검토하세요."
        )

    # 요금제 변경 감지 시
    pricing_changes = []
    for analysis in all_analyses:
        for f in analysis.get("findings", []):
            if f["category"] == "요금제 변경":
                pricing_changes.append(analysis["name"])
                break
    if pricing_changes:
        suggestions.append(
            f"요금제 변경이 있는 경쟁사({', '.join(pricing_changes)})의 "
            f"가격 정책을 비교 분석하여 유심사 요금 경쟁력을 재검토하세요."
        )

    if not suggestions:
        suggestions.append("이번 주는 특별한 경쟁사 동향이 감지되지 않았습니다. 정기적인 모니터링을 계속하세요.")

    return suggestions


def generate_report(all_analyses: list[dict], config: dict) -> str:
    """최종 마크다운 리포트를 생성합니다."""
    now = datetime.now()
    start_date = now.strftime("%Y-%m-%d")
    end_date = now.strftime("%Y-%m-%d")

    domestic = [a for a in all_analyses if a.get("region") == "domestic"]
    international = [a for a in all_analyses if a.get("region") == "international"]

    domestic_changes = sum(len(a.get("findings", [])) for a in domestic)
    international_changes = sum(len(a.get("findings", [])) for a in international)

    ux_highlights = extract_ux_highlights(all_analyses)
    suggestions = generate_suggestions(all_analyses, ux_highlights)

    template = Template(REPORT_TEMPLATE)
    report = template.render(
        start_date=start_date,
        end_date=end_date,
        generated_at=now.strftime("%Y-%m-%d %H:%M:%S KST"),
        domestic_count=len(domestic),
        international_count=len(international),
        domestic_changes=domestic_changes,
        international_changes=international_changes,
        domestic_competitors=domestic,
        international_competitors=international,
        ux_highlights=ux_highlights,
        suggestions=suggestions,
    )

    return report


def save_report(report: str, output_dir: str = "reports") -> str:
    """리포트를 파일로 저장합니다."""
    from pathlib import Path

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    filename = f"competitor_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    filepath = output_path / filename
    filepath.write_text(report, encoding="utf-8")

    logger.info(f"리포트 저장 완료: {filepath}")
    return str(filepath)
