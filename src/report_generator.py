"""경쟁사 분석 리포트 생성 모듈 (LLM 분석 결과 기반)"""

import logging
from datetime import datetime, timedelta

from jinja2 import Template

logger = logging.getLogger(__name__)

REPORT_TEMPLATE = """# 유심사 경쟁사 주간 분석 리포트

**분석 기간**: {{ start_date }} ~ {{ end_date }}
**생성일시**: {{ generated_at }}
**분석 엔진**: {{ backend }}

---

## 주간 요약

| 구분 | 경쟁사 수 | UX 변경 | 신기능 | 요금 변동 |
|------|-----------|---------|--------|-----------|
| 국내 | {{ domestic_count }} | {{ domestic_ux }} | {{ domestic_feat }} | {{ domestic_price }} |
| 해외 | {{ international_count }} | {{ intl_ux }} | {{ intl_feat }} | {{ intl_price }} |

---

## 전주 대비 트렌드

{% if trend and trend.has_previous %}
| 경쟁사 | 이번 주 | 지난 주 | 변화 |
|--------|---------|---------|------|
{% for name, t in trend.competitors.items() %}| {{ name }} | {{ t.current_total }}건 | {{ t.previous_total }}건 | {{ '+' if t.diff > 0 }}{{ t.diff }} |
{% endfor %}

> {{ trend.summary }}
{% else %}
첫 번째 분석입니다. 다음 주부터 트렌드가 표시됩니다.
{% endif %}

---

## 앱 업데이트 현황

{% for comp in all_analyses %}{% if comp.app_info %}
### {{ comp.name }}
| 플랫폼 | 버전 | 평점 | 업데이트일 |
|--------|------|------|-----------|
{% for app in comp.app_info %}| {{ app.platform }} | {{ app.version }} | {{ '%.1f'|format(app.rating) }} ({{ app.rating_count }}) | {{ app.updated[:10] }} |
{% endfor %}
{% if comp.app_info[0].release_notes %}
> 릴리즈 노트: {{ comp.app_info[0].release_notes[:200] }}
{% endif %}
{% endif %}{% endfor %}

---

## UX/UI 변경사항 하이라이트

{% if all_ux_changes %}
{% for item in all_ux_changes %}
### {{ item.competitor }} — {{ item.title }}
{{ item.description }}
{% if item.impact %}- **유심사 시사점**: {{ item.impact }}{% endif %}
{% if item.source_url %}- 출처: {{ item.source_url }}{% endif %}

{% endfor %}
{% else %}
이번 주 주요 UX/UI 변경사항이 탐지되지 않았습니다.
{% endif %}

---

## 국내 경쟁사 상세 분석

{% for comp in domestic_competitors %}
### {{ comp.name }}
> {{ comp.summary }}

{% if comp.ux_changes %}
**UX/UI 변경**
{% for c in comp.ux_changes %}- {{ c.title }}: {{ c.description }}{% if c.source_url %} ([출처]({{ c.source_url }})){% endif %}
{% endfor %}
{% endif %}
{% if comp.new_features %}
**새로운 기능**
{% for f in comp.new_features %}- {{ f.title }}: {{ f.description }}{% if f.source_url %} ([출처]({{ f.source_url }})){% endif %}
{% endfor %}
{% endif %}
{% if comp.pricing %}
**요금/프로모션**
{% for p in comp.pricing %}- {{ p.title }}: {{ p.description }}{% if p.source_url %} ([출처]({{ p.source_url }})){% endif %}
{% endfor %}
{% endif %}
{% if not comp.ux_changes and not comp.new_features and not comp.pricing %}
- 이번 주 특이사항 없음
{% endif %}

{% endfor %}

---

## 해외 경쟁사 상세 분석

{% for comp in international_competitors %}
### {{ comp.name }}
> {{ comp.summary }}

{% if comp.ux_changes %}
**UX/UI Changes**
{% for c in comp.ux_changes %}- {{ c.title }}: {{ c.description }}{% if c.source_url %} ([Source]({{ c.source_url }})){% endif %}
{% endfor %}
{% endif %}
{% if comp.new_features %}
**New Features**
{% for f in comp.new_features %}- {{ f.title }}: {{ f.description }}{% if f.source_url %} ([Source]({{ f.source_url }})){% endif %}
{% endfor %}
{% endif %}
{% if comp.pricing %}
**Pricing/Promotions**
{% for p in comp.pricing %}- {{ p.title }}: {{ p.description }}{% if p.source_url %} ([Source]({{ p.source_url }})){% endif %}
{% endfor %}
{% endif %}
{% if not comp.ux_changes and not comp.new_features and not comp.pricing %}
- No notable changes this week
{% endif %}

{% endfor %}

---

## 유심사 전략 제안

{% if suggestions %}
| 우선순위 | 분류 | 제안 | 근거 |
|----------|------|------|------|
{% for s in suggestions %}| {{ s.priority }} | {{ s.category }} | {{ s.action }} | {{ s.reason }} |
{% endfor %}
{% else %}
이번 주는 특별한 전략 제안 사항이 없습니다.
{% endif %}

---

{% if pricing_table %}
{{ pricing_table }}

---

{% endif %}
*⚠️ 본 리포트는 AI 기반 자동 분석 결과로, 부정확하거나 누락된 정보가 포함될 수 있습니다. 주요 내용은 원문 링크를 통해 반드시 확인해 주세요.*
"""


def generate_report(all_analyses: list[dict], suggestions: list[dict], backend: str, trend: dict = None, pricing_table: str = "") -> str:
    """LLM 분석 결과를 기반으로 최종 마크다운 리포트를 생성합니다."""
    now = datetime.now()
    week_ago = now - timedelta(days=7)

    domestic = [a for a in all_analyses if a.get("region") == "domestic"]
    international = [a for a in all_analyses if a.get("region") == "international"]

    # UX 하이라이트 수집
    all_ux_changes = []
    for a in all_analyses:
        for change in a.get("ux_changes", []):
            entry = {**change, "competitor": a["name"]}
            all_ux_changes.append(entry)

    # 카테고리별 카운트
    def count_items(comps, key):
        return sum(len(c.get(key, [])) for c in comps)

    backend_labels = {
        "claude": "Claude API (Anthropic)",
        "gemini": "Google Gemini (무료)",
        "fallback": "키워드 기반 (LLM 미사용)",
    }

    template = Template(REPORT_TEMPLATE)
    report = template.render(
        start_date=week_ago.strftime("%Y-%m-%d"),
        end_date=now.strftime("%Y-%m-%d"),
        generated_at=now.strftime("%Y-%m-%d %H:%M:%S KST"),
        backend=backend_labels.get(backend, backend),
        domestic_count=len(domestic),
        international_count=len(international),
        domestic_ux=count_items(domestic, "ux_changes"),
        domestic_feat=count_items(domestic, "new_features"),
        domestic_price=count_items(domestic, "pricing"),
        intl_ux=count_items(international, "ux_changes"),
        intl_feat=count_items(international, "new_features"),
        intl_price=count_items(international, "pricing"),
        all_ux_changes=all_ux_changes,
        all_analyses=all_analyses,
        domestic_competitors=domestic,
        international_competitors=international,
        suggestions=suggestions,
        trend=trend or {},
        pricing_table=pricing_table,
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
