# 유심사 경쟁사 분석 자동화

매주 월요일 오전 10시(KST)에 유심사의 국내/해외 경쟁사를 자동으로 분석하고, Slack 채널로 리포트를 전송합니다.

## 분석 대상

### 국내 경쟁사
로밍도깨비, 도시락eSIM, flit eSIM, 핀다이렉트, 말톡, 이심이지

### 해외 경쟁사
Saily, aloSIM, Holafly, Airalo, Nomad

## 분석 항목
- **UX/UI 변경사항** (우선 부각)
- 새로운 기능 출시
- 요금제 변경
- 지원 국가/지역 확대
- 앱 업데이트
- 프로모션 및 이벤트

## 설정 방법

### 1. GitHub Secrets 등록

Repository Settings → Secrets and variables → Actions에서 아래 시크릿을 등록하세요:

| Secret 이름 | 필수 | 설명 |
|-------------|------|------|
| `SLACK_WEBHOOK_URL` | ✅ | Slack Incoming Webhook URL |
| `SERPAPI_KEY` | 택1 | SerpAPI 키 (권장) |
| `GOOGLE_API_KEY` | 택1 | Google Custom Search API 키 |
| `GOOGLE_CSE_ID` | 택1 | Google Custom Search Engine ID |

> 검색 API는 SerpAPI 또는 Google CSE 중 하나만 설정하면 됩니다. 둘 다 없으면 기본 스크래핑으로 동작합니다.

### 2. Slack Webhook 설정

1. [Slack API](https://api.slack.com/apps)에서 앱 생성
2. Incoming Webhooks 활성화
3. 원하는 채널에 Webhook 추가
4. 생성된 Webhook URL을 `SLACK_WEBHOOK_URL` 시크릿에 등록

### 3. 수동 실행

GitHub Actions 탭에서 "유심사 경쟁사 주간 분석" 워크플로우를 선택하고 "Run workflow"를 클릭하면 즉시 실행할 수 있습니다.

## 로컬 실행

```bash
pip install -r requirements.txt

# Slack 전송 포함
SERPAPI_KEY=your_key SLACK_WEBHOOK_URL=your_url python src/main.py

# Slack 전송 없이 리포트만 생성
python src/main.py --skip-slack
```

## 프로젝트 구조

```
├── .github/workflows/
│   └── competitor-analysis.yml   # GitHub Actions 스케줄러
├── src/
│   ├── main.py                   # 메인 실행 스크립트
│   ├── config_loader.py          # 설정 파일 로더
│   ├── web_searcher.py           # 웹 검색 모듈
│   ├── report_generator.py       # 리포트 생성 모듈
│   └── slack_notifier.py         # Slack 전송 모듈
├── reports/                      # 생성된 리포트 저장
├── config.yaml                   # 경쟁사 및 분석 설정
└── requirements.txt              # Python 의존성
```
