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

  <!-- Executive Summary -->
  __EXECUTIVE_SUMMARY__

  <!-- 요약 통계 -->
  <div class="stat-grid">
    <div class="stat"><div class="value">__TOTAL_COMPETITORS__</div><div class="label">분석 경쟁사</div></div>
    <div class="stat"><div class="value">__TOTAL_UX__</div><div class="label">UX 변경</div></div>
    <div class="stat"><div class="value">__TOTAL_FEATURES__</div><div class="label">신기능</div></div>
    <div class="stat"><div class="value">__TOTAL_PRICING__</div><div class="label">요금 변동</div></div>
  </div>

  <!-- 필터 -->
  <div class="filter-bar">
    <button class="filter-btn active" onclick="filterRegion('all', this)">전체</button>
    <button class="filter-btn" onclick="filterRegion('domestic', this)">🇰🇷 국내</button>
    <button class="filter-btn" onclick="filterRegion('international', this)">🌏 해외</button>
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

  <!-- 앱 평점 추이 -->
  __RATING_TREND_SECTION__

  <!-- 기능 출시 속도 -->
  __RELEASE_VELOCITY_SECTION__

  <!-- 가격 변동 -->
  __PRICE_CHANGES_SECTION__

  <!-- 전략 제안 -->
  <div class="section">
    <div class="section-title">💡 전략 제안</div>
    <div class="card">
      __SUGGESTIONS_TABLE__
    </div>
  </div>

  <div class="footer">
    ⚠️ 본 리포트는 AI 기반 자동 분석 결과로, 부정확하거나 누락된 정보가 포함될 수 있습니다.<br>
    주요 내용은 원문 링크를 통해 반드시 확인해 주세요.<br>
    💬 리포트 관련 문의: @harry
  </div>
</div>

<script>
function filterRegion(region, btn) {
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
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
    signal_type = threat.get("signal_type", "")
    signal_badge = ""
    if signal_type == "노이즈":
        signal_badge = ' <span class="badge badge-stable">노이즈</span>'
    elif signal_type == "시그널":
        signal_badge = ' <span class="badge badge-up">시그널</span>'
    threat_html = f'<span class="badge {threat_class}">위협도 {threat_score}/10</span>{signal_badge}' if threat_score else ""

    # 링크
    links = []
    if comp.get("url"):
        links.append(f'<a class="link" href="{html.escape(comp["url"])}" target="_blank">웹</a>')
    if comp.get("app_store"):
        links.append(f'<a class="link" href="{html.escape(comp["app_store"])}" target="_blank">iOS</a>')
    if comp.get("play_store"):
        links.append(f'<a class="link" href="{html.escape(comp["play_store"])}" target="_blank">Android</a>')
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
                    {html.escape(app.get("platform",""))} 리뷰 감성 (평균 ⭐{sentiment.get("avg_rating", 0)})
                    <div class="sentiment-bar">
                        <div class="sentiment-pos" style="width:{pos_pct}%"></div>
                        <div class="sentiment-neu" style="width:{neu_pct}%"></div>
                        <div class="sentiment-neg" style="width:{neg_pct}%"></div>
                    </div>
                </div>'''

    region_emoji = "🇰🇷" if region == "domestic" else "🌏"

    return f'''
    <div class="card comp-card" data-region="{html.escape(region)}">
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
            version_info += f'<div class="tag">{html.escape(vc)}</div>'

        rows += f'''<tr>
            <td><strong>{html.escape(name)}</strong></td>
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
            url = html.escape(app.get("url", ""))
            version = html.escape(app.get("version", "N/A"))
            updated = html.escape(app.get("updated", "")[:10])
            name = html.escape(a.get("name", ""))

            rows += f'''<tr>
                <td><strong>{name}</strong></td>
                <td>{platform_emoji} {html.escape(app.get("platform", ""))}</td>
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
        priority = html.escape(s.get("priority", ""))
        badge_class = {"높음": "badge-high", "중간": "badge-mid", "낮음": "badge-low"}.get(s.get("priority", ""), "badge-stable")
        rows += f'''<tr>
            <td><span class="badge {badge_class}">{priority}</span></td>
            <td>{html.escape(s.get("category", ""))}</td>
            <td>{html.escape(s.get("action", ""))}</td>
            <td style="color:#94a3b8">{html.escape(s.get("reason", ""))}</td>
        </tr>'''

    return f'''<table>
        <tr><th>우선순위</th><th>분류</th><th>제안</th><th>근거</th></tr>
        {rows}
    </table>'''


def _build_executive_summary(exec_summary: dict) -> str:
    """Executive Summary HTML을 생성합니다."""
    if not exec_summary or not exec_summary.get("headline"):
        return ""

    risk_level = exec_summary.get("risk_level", "낮음")
    risk_class = {"높음": "badge-high", "보통": "badge-mid", "낮음": "badge-low"}.get(risk_level, "badge-stable")

    threats_html = ""
    for t in exec_summary.get("top_threats", []):
        urgency = html.escape(t.get("urgency", ""))
        urgency_class = "badge-high" if urgency == "즉시대응" else ("badge-mid" if urgency == "주시" else "badge-low")
        threats_html += f'''<tr>
            <td><strong>{html.escape(t.get("competitor", ""))}</strong></td>
            <td>{html.escape(t.get("action", ""))}</td>
            <td>{html.escape(t.get("impact", ""))}</td>
            <td><span class="badge {urgency_class}">{urgency}</span></td>
        </tr>'''

    opps_html = ""
    for o in exec_summary.get("opportunities", []):
        opps_html += f'''<tr>
            <td><strong>{html.escape(o.get("area", ""))}</strong></td>
            <td>{html.escape(o.get("description", ""))}</td>
            <td style="color:#38bdf8">{html.escape(o.get("action", ""))}</td>
        </tr>'''

    threats_table = f'''<table>
        <tr><th>경쟁사</th><th>동향</th><th>유심사 영향</th><th>긴급도</th></tr>
        {threats_html}
    </table>''' if threats_html else ""

    opps_table = f'''<h3 style="margin-top:16px">💡 기회 포착</h3>
    <table>
        <tr><th>영역</th><th>설명</th><th>권장 액션</th></tr>
        {opps_html}
    </table>''' if opps_html else ""

    return f'''
    <div class="section">
      <div class="section-title">🎯 Executive Summary</div>
      <div class="card">
        <h2 style="margin-bottom:12px">{html.escape(exec_summary.get("headline", ""))}</h2>
        <div style="margin-bottom:16px">
          경쟁 위험도: <span class="badge {risk_class}">{html.escape(risk_level)}</span>
          <span style="color:#94a3b8;margin-left:8px">{html.escape(exec_summary.get("risk_reason", ""))}</span>
        </div>
        {threats_table}
        {opps_table}
      </div>
    </div>'''


def _build_rating_trend_section(rating_history: dict[str, list[dict]]) -> str:
    """앱 평점 추이 테이블 HTML을 생성합니다."""
    if not rating_history:
        return ""

    # 날짜 목록 수집
    all_dates = set()
    for entries in rating_history.values():
        for e in entries:
            all_dates.add(e["date"])
    dates = sorted(all_dates)[-8:]  # 최근 8주

    if len(dates) < 2:
        return ""

    date_headers = "".join(f"<th>{d[5:]}</th>" for d in dates)  # MM-DD 형식

    rows = ""
    for name, entries in sorted(rating_history.items()):
        date_map = {e["date"]: e for e in entries}
        cells = ""
        prev_rating = None
        for d in dates:
            entry = date_map.get(d, {})
            ios = entry.get("iOS", 0)
            android = entry.get("Android", 0)
            rating = ios or android
            if rating:
                # 변동 표시
                if prev_rating and rating != prev_rating:
                    diff = rating - prev_rating
                    color = "#22c55e" if diff > 0 else "#ef4444"
                    arrow = "↑" if diff > 0 else "↓"
                    cells += f'<td style="color:{color}">{rating:.1f} {arrow}</td>'
                else:
                    cells += f"<td>{rating:.1f}</td>"
                prev_rating = rating
            else:
                cells += "<td style='color:#475569'>-</td>"

        rows += f"<tr><td><strong>{html.escape(name)}</strong></td>{cells}</tr>"

    return f'''
    <div class="section">
      <div class="section-title">📈 앱 평점 추이 (주간)</div>
      <div class="card">
        <table>
          <tr><th>경쟁사</th>{date_headers}</tr>
          {rows}
        </table>
      </div>
    </div>'''


def _build_release_velocity_section(release_history: dict[str, list[dict]]) -> str:
    """기능 출시 속도 비교 테이블 HTML을 생성합니다."""
    if not release_history:
        return ""

    # 경쟁사별 통계 계산
    stats = []
    for name, entries in release_history.items():
        total_releases = sum(e.get("total", 0) for e in entries)
        weeks = len(entries) or 1
        avg_per_week = total_releases / weeks
        total_ux = sum(e.get("ux_changes", 0) for e in entries)
        total_feat = sum(e.get("new_features", 0) for e in entries)
        total_pricing = sum(e.get("pricing", 0) for e in entries)

        # 최근 4주 vs 이전 4주 비교
        recent = entries[-4:] if len(entries) >= 4 else entries
        older = entries[-8:-4] if len(entries) >= 8 else []
        recent_total = sum(e.get("total", 0) for e in recent)
        older_total = sum(e.get("total", 0) for e in older) if older else recent_total

        if older_total > 0:
            momentum = ((recent_total - older_total) / older_total) * 100
        else:
            momentum = 0

        stats.append({
            "name": name,
            "total": total_releases,
            "avg": avg_per_week,
            "ux": total_ux,
            "feat": total_feat,
            "pricing": total_pricing,
            "weeks": weeks,
            "momentum": momentum,
        })

    # 활동량 기준 정렬
    stats.sort(key=lambda x: x["total"], reverse=True)

    rows = ""
    for s in stats:
        momentum = s["momentum"]
        if momentum > 20:
            mom_badge = '<span class="badge badge-up">가속 ↑</span>'
        elif momentum < -20:
            mom_badge = '<span class="badge badge-down">감속 ↓</span>'
        else:
            mom_badge = '<span class="badge badge-stable">유지 →</span>'

        rows += f'''<tr>
            <td><strong>{html.escape(s["name"])}</strong></td>
            <td>{s["total"]}건 / {s["weeks"]}주</td>
            <td>{s["avg"]:.1f}건/주</td>
            <td>{s["ux"]}</td>
            <td>{s["feat"]}</td>
            <td>{s["pricing"]}</td>
            <td>{mom_badge}</td>
        </tr>'''

    return f'''
    <div class="section">
      <div class="section-title">🚀 기능 출시 속도 비교</div>
      <div class="card">
        <table>
          <tr><th>경쟁사</th><th>총 활동</th><th>주간 평균</th><th>UX</th><th>기능</th><th>요금</th><th>모멘텀</th></tr>
          {rows}
        </table>
        <div style="color:#64748b;font-size:11px;margin-top:8px">
          모멘텀: 최근 4주 vs 이전 4주 활동량 비교 (±20% 이상 변동 시 표시)
        </div>
      </div>
    </div>'''


def _build_price_changes_section(price_changes: list[dict]) -> str:
    """가격 변동 섹션 HTML을 생성합니다."""
    if not price_changes:
        return ""

    rows = ""
    for c in price_changes:
        rows += f'''<tr>
            <td><strong>{html.escape(c.get("competitor", ""))}</strong></td>
            <td>{html.escape(c.get("destination", ""))}</td>
            <td>{html.escape(c.get("data", ""))} / {html.escape(c.get("duration", ""))}</td>
            <td style="text-decoration:line-through;color:#64748b">{html.escape(str(c.get("previous_price", "")))} {html.escape(c.get("currency", ""))}</td>
            <td style="color:#fbbf24;font-weight:600">{html.escape(str(c.get("current_price", "")))} {html.escape(c.get("currency", ""))}</td>
        </tr>'''

    return f'''
    <div class="section">
      <div class="section-title">⚡ 가격 변동 감지</div>
      <div class="card">
        <table>
          <tr><th>서비스</th><th>여행지</th><th>요금제</th><th>이전 가격</th><th>현재 가격</th></tr>
          {rows}
        </table>
      </div>
    </div>'''


def generate_dashboard(
    analyses: list[dict],
    suggestions: list[dict],
    backend: str,
    trend: dict = None,
    output_dir: str = "reports",
    executive_summary: dict = None,
    price_changes: list[dict] = None,
    rating_history: dict = None,
    release_history: dict = None,
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
    html_output = DASHBOARD_TEMPLATE
    html_output = html_output.replace("__GENERATED_AT__", now.strftime("%Y-%m-%d %H:%M"))
    html_output = html_output.replace("__BACKEND__", backend_labels.get(backend, backend))
    html_output = html_output.replace("__TOTAL_COMPETITORS__", str(len(analyses)))
    html_output = html_output.replace("__TOTAL_UX__", str(total_ux))
    html_output = html_output.replace("__TOTAL_FEATURES__", str(total_feat))
    html_output = html_output.replace("__TOTAL_PRICING__", str(total_price))
    html_output = html_output.replace("__COMPETITOR_CARDS__", cards_html)
    html_output = html_output.replace("__TREND_TABLE__", _build_trend_table(trend or {}))
    html_output = html_output.replace("__APP_TABLE__", _build_app_table(analyses))
    html_output = html_output.replace("__SUGGESTIONS_TABLE__", _build_suggestions_table(suggestions))
    html_output = html_output.replace("__EXECUTIVE_SUMMARY__", _build_executive_summary(executive_summary or {}))
    html_output = html_output.replace("__PRICE_CHANGES_SECTION__", _build_price_changes_section(price_changes or []))
    html_output = html_output.replace("__RATING_TREND_SECTION__", _build_rating_trend_section(rating_history or {}))
    html_output = html_output.replace("__RELEASE_VELOCITY_SECTION__", _build_release_velocity_section(release_history or {}))

    # 저장
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    filename = f"dashboard_{now.strftime('%Y%m%d_%H%M%S')}.html"
    filepath = output_path / filename
    filepath.write_text(html_output, encoding="utf-8")

    logger.info(f"대시보드 생성 완료: {filepath}")
    return str(filepath)
