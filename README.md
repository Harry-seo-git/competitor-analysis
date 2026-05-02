# 유심사 경쟁사 분석 자동화

eSIM/로밍 서비스 **유심사**의 국내·해외 경쟁사를 매주 자동 분석하여 Slack으로 리포트를 전송하는 시스템입니다.

## 파이프라인

```
웹 검색 → 페이지 수집 → LLM 분석 → 리포트/대시보드 생성 → Slack 알림
```

## 분석 대상

### 국내 (8개)
로밍도깨비 · 도시락eSIM · 플릿 · 이심이지 · 모비 · 말톡 · 핀다이렉트 · 커비이심

### 해외 (4개)
Saily · Holafly · Airalo · Nomad

## 분석 항목
- UX/UI 변경사항
- 새로운 기능 출시
- 요금제 변경
- 지원 국가/지역 확대
- 앱 업데이트 (App Store / Play Store)
- 프로모션 및 이벤트

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
  report_generator.py  # 마크다운 리포트 생성 (Jinja2)
  dashboard.py         # HTML 대시보드 생성
  slack_notifier.py    # Slack Block Kit 메시지 전송
  config_loader.py     # config.yaml 로더
config.yaml            # 경쟁사 목록, 키워드, 스케줄 설정
render.yaml            # Render Cron Job 배포 설정
data/                  # 히스토리, 요금제, 스냅샷 데이터
reports/               # 생성된 리포트(.md) 및 대시보드(.html)
```

## 배포

### Render Cron Job (운영)

매주 월요일 09:30 KST에 자동 실행됩니다. `render.yaml` 참조.

Render 대시보드에서 아래 환경 변수를 설정하세요:

| 환경 변수 | 필수 | 설명 |
|-----------|------|------|
| `SERPAPI_KEY` | ✅ | SerpAPI 키 |
| `ANTHROPIC_API_KEY` | ✅ | Claude API 키 |
| `SLACK_WEBHOOK_URL` | ✅ | Slack Incoming Webhook URL |

### GitHub Actions (수동 실행)

Actions 탭에서 워크플로우를 수동 실행할 수 있습니다. 사용 시 Repository Secrets에 동일한 키를 등록하세요.

## 로컬 실행

```bash
pip install -r requirements.txt

# .env 파일 설정 (.env.example 참조)

# Slack 전송 포함
python src/main.py

# Slack 전송 없이 리포트만 생성
python src/main.py --skip-slack
```

## 기술 스택

- **언어**: Python 3.11+
- **LLM**: Claude API (최신 Sonnet 모델 자동 감지)
- **검색**: SerpAPI / Google CSE / 스크래핑 폴백
- **배포**: Render Cron Job
- **알림**: Slack Webhook (Block Kit)
