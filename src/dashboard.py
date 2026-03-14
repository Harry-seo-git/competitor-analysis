"""웹 대시보드 생성 모듈

분석 결과를 인터랙티브한 HTML 대시보드로 생성합니다.
외부 의존성 없이 순수 HTML/CSS/JS로 구현됩니다.
"""

import html
import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

DASHBOARD_TEMPLATE = """<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>유심사 경쟁사 분석 대시보드</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0f172a; color: #e2e8f0; }
.container { max-width: 1400px; margin: 0 auto; padding: 20px; }
.header { text-align: center; padding: 30px 0; border-bottom: 1px solid #1e293b; margin-bottom: 30px; }
.header h1 { font-size: 28px; color: #f1f5f9; margin-bottom: 8px; }
.header .subtitle { color: #94a3b8; font-size: 14px; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 20px; margin-bottom: 30px; }
.card { background: #1e293b; border-radius: 12px; padding: 24px; border: 1px solid #334155; }
.card h2 { font-size: 18px; color: #f8fafc; margin-bottom: 16px; display: flex; align-items: center; gap: 8px; }
.card h3 { font-size: 15px; color: #cbd5e1; margin: 12px 0 8px; }
.stat-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 30px; }
.stat { background: #1e293b; border-radius: 12px; padding: 20px; text-align: center; border: 1px solid #334155; }
.stat .value { font-size: 32px; font-weight: 700; color: #38bdf8; }
.stat .label { font-size: 12px; color: #94a3b8; margin-top: 4px; }
.badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }
.badge-high { background: #991b1b; color: #fca5a5; }
.badge-mid { background: #854d0e; color: #fde047; }
.badge-low { background: #166534; color: #86efac; }
.badge-up { background: #065f46; color: #6ee7b7; }
.badge-down { background: #991b1b; color: #fca5a5; }
.badge-stable { background: #334155; color: #94a3b8; }
table { width: 100%; border-collapse: collapse; margin-top: 12px; }
th { background: #0f172a; color: #94a3b8; font-size: 12px; text-transform: uppercase; padding: 10px 12px; text-align: left; }
td { padding: 10px 12px; border-top: 1px solid #334155; font-size: 13px; }
tr:hover td { background: #334155; }
.link { color: #38bdf8; text-decoration: none; }
.link:hover { text-decoration: underline; }
.rating { color: #fbbf24; }
.tag { display: inline-block; padding: 2px 6px; background: #334155; border-radius: 3px; font-size: 11px; margin: 2px; }
.filter-bar { display: flex; gap: 8px; margin-bottom: 20px; flex-wrap: wrap; }
.filter-btn { padding: 6px 14px; border-radius: 6px; border: 1px solid #475569; background: transparent; color: #cbd5e1; cursor: pointer; font-size: 13px; }
.filter-btn.active { background: #38bdf8; color: #0f172a; border-color: #38bdf8; }
.section { margin-bottom: 30px; }
.section-title { font-size: 20px; color: #f1f5f9; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 1px solid #1e293b; }
.empty { color: #64748b; font-style: italic; padding: 20px; text-align: center; }
.sentiment-bar { display: flex; height: 8px; border-radius: 4px; overflow: hidden; margin: 8px 0; }
.sentiment-pos { background: #22c55e; }
.sentiment-neu { background: #eab308; }
.sentiment-neg { background: #ef4444; }
.footer { text-align: center; padding: 30px 0; color: #475569; font-size: 12px; border-top: 1px solid #1e293b; margin-top: 30px; }
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>📊 유심사 경쟁사 분석 대시보드</h1>
    <div class="subtitle">분석일: __GENERATED_AT__ | 엔진: __BACKEND__</div>
  </div>

  <!-- 요약 통계 -->
  <div class="stat-grid">
    <div class="stat"><div class="value">__TOTAL_COMPETITORS__</div><div class="label">분석 경쟁사</div></div>
    <div class="stat"><div class="value">__TOTAL_UX__</div><div class="label">UX 변경</div></div>
    <div class="stat"><div class="value">__TOTAL_FEATURES__</div><div class="label">신기능</div></div>
    <div class="stat"><div class="value">__TOTAL_PRICING__</div><div class="label">요금 변동</div></div>
  </div>

  <!-- 필터 -->
  <div class="filter-bar">
    <button class="filter-btn active" onclick="filterRegion('all')">전체</button>
    <button class="filter-btn" onclick="filterRegion('domestic')">🇰🇷 국내</button>
    <button class="filter-btn" onclick="filterRegion('international')">🌏 해외</button>
  </div>

  <!-- 경쟁사 카드 -->
  <div class="grid" id="competitor-grid">
    __COMPETITOR_CARDS__
  </div>

  <!-- 트렌드 -->
  <div class="section">
    <div class="section-title">📈 전주 대비 트렌드</div>
    <div class="card">
      __TREND_TABLE__
    </div>
  </div>

  <!-- 앱 현황 -->
  <div class="section">
    <div class="section-title">📱 앱 업데이트 현황</div>
    <div class="card">
      __APP_TABLE__
    </div>
  </div>

  <!-- 전략 제안 -->
  <div class="section">
    <div class="section-title">💡 전략 제안</div>
    <div class="card">
      __SUGGESTIONS_TABLE__
    </div>
  </div>

  <div class="footer">
    ⚠️ 본 리포트는 AI 기반 자동 분석 결과로, 부정확하거나 누락된 정보가 포함될 수 있습니다.<br>
    주요 내용은 원문 링크를 통해 반드시 확인해 주세요.
  </div>
</div>

<script>
function filterRegion(region) {
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  event.target.classList.add('active');
  document.querySelectorAll('.comp-card').forEach(card => {
    card.style.display = (region === 'all' || card.dataset.region === region) ? '' : 'none';
  });
}
</script>
</body>
</html>"""


def _build_competitor_card(comp: dict) -> str:
    """경쟁사 카드 HTML을 생성합니다."""
    name = html.escape(comp.get("name", ""))
    region = comp.get("region", "")
    summary = html.escape(comp.get("summary", "특이사항 없음"))

    # 위협도 배지
    threat = comp.get("threat_score", {})
    threat_level = threat.get("level", "")
    threat_score = threat.get("score", "")
    threat_class = {"높음": "badge-high", "중간": "badge-mid", "낮음": "badge-low"}.get(threat_level, "badge-stable")
    threat_html = f'<span class="badge {threat_class}">위협도 {threat_score}/10</span>' if threat_score else ""

    # 링크
    links = []
    if comp.get("url"):
        links.append(f'<a class="link" href="{comp["url"]}" target="_blank">웹</a>')
    if comp.get("app_store"):
        links.append(f'<a class="link" href="{comp["app_store"]}" target="_blank">iOS</a>')
    if comp.get("play_store"):
        links.append(f'<a class="link" href="{comp["play_store"]}" target="_blank">Android</a>')
    links_html = " · ".join(links)

    # 변경사항 목록
    changes_html = ""
    categories = [
        ("ux_changes", "🎨 UX/UI"),
        ("new_features", "🆕 신기능"),
        ("pricing", "💰 요금"),
        ("other", "📌 기타"),
    ]
    for key, label in categories:
        items = comp.get(key, [])
        if not items:
            continue
        changes_html += f'<h3>{label} ({len(items)})</h3>'
        for item in items[:3]:
            if isinstance(item, dict):
                title = html.escape(item.get("title", "")[:80])
                changes_html += f'<div class="tag">{title}</div> '

    if not changes_html:
        changes_html = '<div class="empty">이번 주 변경사항 없음</div>'

    # 리뷰 감성
    sentiment_html = ""
    for app in comp.get("app_info", []):
        sentiment = app.get("review_sentiment", {})
        if sentiment:
            total = sentiment.get("positive", 0) + sentiment.get("neutral", 0) + sentiment.get("negative", 0)
            if total > 0:
                pos_pct = sentiment["positive"] / total * 100
                neu_pct = sentiment["neutral"] / total * 100
                neg_pct = sentiment["negative"] / total * 100
                sentiment_html += f'''
                <div style="font-size:12px;color:#94a3b8;margin-top:8px;">
                    {app.get("platform","")} 리뷰 감성 (평균 ⭐{sentiment.get("avg_rating", 0)})
                    <div class="sentiment-bar">
                        <div class="sentiment-pos" style="width:{pos_pct}%"></div>
                        <div class="sentiment-neu" style="width:{neu_pct}%"></div>
                        <div class="sentiment-neg" style="width:{neg_pct}%"></div>
                    </div>
                </div>'''

    region_emoji = "🇰🇷" if region == "domestic" else "🌏"

    return f'''
    <div class="card comp-card" data-region="{region}">
      <h2>{region_emoji} {name} {threat_html}</h2>
      <div style="color:#94a3b8;font-size:13px;margin-bottom:12px;">{summary}</div>
      <div style="margin-bottom:12px;">{links_html}</div>
      {changes_html}
      {sentiment_html}
    </div>'''


def _build_trend_table(trend: dict) -> str:
    if not trend or not trend.get("has_previous"):
        return '<div class="empty">첫 번째 분석입니다. 다음 주부터 트렌드가 표시됩니다.</div>'

    rows = ""
    for name, t in trend.get("competitors", {}).items():
        diff = t.get("diff", 0)
        direction = t.get("direction", "stable")
        badge_class = {"up": "badge-up", "down": "badge-down", "stable": "badge-stable"}[direction]
        arrow = {"up": "↑", "down": "↓", "stable": "→"}[direction]
        diff_text = f"+{diff}" if diff > 0 else str(diff)

        version_info = ""
        for vc in t.get("version_changes", []):
            version_info += f'<div class="tag">{vc}</div>'

        rows += f'''<tr>
            <td><strong>{name}</strong></td>
            <td>{t.get("current_total", 0)}건</td>
            <td>{t.get("previous_total", 0)}건</td>
            <td><span class="badge {badge_class}">{arrow} {diff_text}</span></td>
            <td>{version_info}</td>
        </tr>'''

    return f'''<table>
        <tr><th>경쟁사</th><th>이번 주</th><th>지난 주</th><th>변화</th><th>앱 버전</th></tr>
        {rows}
    </table>'''


def _build_app_table(analyses: list[dict]) -> str:
    rows = ""
    for a in analyses:
        for app in a.get("app_info", []):
            platform_emoji = "🍎" if app.get("platform") == "iOS" else "🤖"
            rating = app.get("rating", 0)
            rating_str = f'<span class="rating">{"★" * int(rating)}{"☆" * (5 - int(rating))}</span> {rating:.1f}' if rating else "-"
            url = app.get("url", "")
            version = app.get("version", "N/A")
            updated = app.get("updated", "")[:10]

            rows += f'''<tr>
                <td><strong>{a["name"]}</strong></td>
                <td>{platform_emoji} {app.get("platform", "")}</td>
                <td>{version}</td>
                <td>{rating_str} ({app.get("rating_count", 0):,})</td>
                <td>{updated}</td>
                <td><a class="link" href="{url}" target="_blank">링크</a></td>
            </tr>'''

    if not rows:
        return '<div class="empty">앱 정보 없음</div>'

    return f'''<table>
        <tr><th>경쟁사</th><th>플랫폼</th><th>버전</th><th>평점</th><th>업데이트</th><th></th></tr>
        {rows}
    </table>'''


def _build_suggestions_table(suggestions: list[dict]) -> str:
    if not suggestions:
        return '<div class="empty">전략 제안 없음</div>'

    rows = ""
    for s in suggestions:
        priority = s.get("priority", "")
        badge_class = {"높음": "badge-high", "중간": "badge-mid", "낮음": "badge-low"}.get(priority, "badge-stable")
        rows += f'''<tr>
            <td><span class="badge {badge_class}">{priority}</span></td>
            <td>{s.get("category", "")}</td>
            <td>{s.get("action", "")}</td>
            <td style="color:#94a3b8">{s.get("reason", "")}</td>
        </tr>'''

    return f'''<table>
        <tr><th>우선순위</th><th>분류</th><th>제안</th><th>근거</th></tr>
        {rows}
    </table>'''


def generate_dashboard(
    analyses: list[dict],
    suggestions: list[dict],
    backend: str,
    trend: dict = None,
    output_dir: str = "reports",
) -> str:
    """HTML 대시보드를 생성합니다."""
    now = datetime.now()

    # 통계
    total_ux = sum(len(a.get("ux_changes", [])) for a in analyses)
    total_feat = sum(len(a.get("new_features", [])) for a in analyses)
    total_price = sum(len(a.get("pricing", [])) for a in analyses)

    backend_labels = {"claude": "Claude API", "fallback": "키워드 기반"}

    # 카드 생성
    cards_html = "\n".join(_build_competitor_card(a) for a in analyses)

    # 대시보드 HTML 조립
    html = DASHBOARD_TEMPLATE
    html = html.replace("__GENERATED_AT__", now.strftime("%Y-%m-%d %H:%M"))
    html = html.replace("__BACKEND__", backend_labels.get(backend, backend))
    html = html.replace("__TOTAL_COMPETITORS__", str(len(analyses)))
    html = html.replace("__TOTAL_UX__", str(total_ux))
    html = html.replace("__TOTAL_FEATURES__", str(total_feat))
    html = html.replace("__TOTAL_PRICING__", str(total_price))
    html = html.replace("__COMPETITOR_CARDS__", cards_html)
    html = html.replace("__TREND_TABLE__", _build_trend_table(trend or {}))
    html = html.replace("__APP_TABLE__", _build_app_table(analyses))
    html = html.replace("__SUGGESTIONS_TABLE__", _build_suggestions_table(suggestions))

    # 저장
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    filename = f"dashboard_{now.strftime('%Y%m%d_%H%M%S')}.html"
    filepath = output_path / filename
    filepath.write_text(html, encoding="utf-8")

    logger.info(f"대시보드 생성 완료: {filepath}")
    return str(filepath)
