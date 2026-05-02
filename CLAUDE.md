# 프로젝트: 유심사 경쟁사 분석 자동화 시스템

## 개요
eSIM/로밍 서비스 "유심사"의 경쟁사를 주간 자동 분석하는 Python 시스템.
웹 검색 → 페이지 수집 → LLM 분석 → 리포트/대시보드 생성 → Slack 알림 파이프라인.

## 기술 스택
- Python (requests, beautifulsoup4, pyyaml, jinja2)
- LLM: Claude API (분석 엔진)
- 검색: SerpAPI / Google CSE / 스크래핑 폴백
- 배포: Render Cron Job (매주 월요일 09:30 KST)
- 알림: Slack Webhook

## 프로젝트 구조
```
src/
  main.py              # 메인 파이프라인 오케스트레이션
  web_searcher.py      # 웹 검색 및 페이지 본문 수집
  llm_analyzer.py      # Claude API 기반 경쟁사 분석
  pricing_monitor.py   # 요금제 가격 모니터링
  site_snapshot.py     # 웹사이트 스냅샷 및 변경 감지
  app_monitor.py       # 앱스토어/플레이스토어 모니터링
  trend_tracker.py     # 이전 주 대비 트렌드 비교, 히스토리 관리
  report_generator.py  # 마크다운 리포트 생성 (Jinja2 템플릿)
  dashboard.py         # HTML 대시보드 생성
  slack_notifier.py    # Slack Block Kit 메시지 전송
  config_loader.py     # config.yaml 로더
config.yaml            # 경쟁사 목록, 키워드, 스케줄 설정
data/history/          # 주간 분석 히스토리 JSON (최근 12주 보관)
data/pricing/          # 요금제 데이터
data/snapshots/        # 사이트 스냅샷
reports/               # 생성된 리포트(.md) 및 대시보드(.html)
```

## 경쟁사 목록
- 국내: 로밍도깨비, 도시락eSIM, 플릿, 이심이지, 모비, 말톡, 핀다이렉트, 커비이심
- 해외: Saily, Holafly, Airalo, Nomad

## 실행
```bash
# 수동 실행
python src/main.py --skip-slack

# Slack 포함 실행
python src/main.py
```

## 주요 설계 결정
- `load_history()`는 한 번만 호출하여 트렌드 비교와 URL 중복 체크에 공통 사용 (이중 파싱 방지)
- `_SKIP_DOMAINS`는 frozenset + urlparse 도메인 파싱으로 O(1) 조회
- dashboard.py에서 html.escape()로 XSS 방지
- 403 HTTP 에러는 별도 처리하여 봇 차단 사이트를 경고 레벨로 로깅

## 코드 컨벤션
- 한국어 로그 메시지 및 주석
- 커밋 메시지: 한국어, conventional commit prefix 사용 (feat:, fix:, refactor:, chore:)
- 리포트 문의: @harry
