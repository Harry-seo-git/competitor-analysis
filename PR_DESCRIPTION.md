# 경쟁사 분석 자동화 시스템 구축

## Summary

eSIM 경쟁사(holafly, nomad, 도시락esim, 도깨비, 어심이지, 플릿) 분석을 자동화하는 시스템을 구축했습니다. 웹 검색, LLM 분석, 가격 모니터링, 사이트 스냅샷, 트렌드 추적, 대시보드 생성, Slack 알림 기능을 포함합니다.

## 주요 변경 사항

### 신규 모듈
- **`src/pricing_monitor.py`** - 경쟁사 요금제 가격 모니터링 및 변동 추적
- **`src/site_snapshot.py`** - 경쟁사 웹사이트 스냅샷 캡처 및 변경 감지
- **`src/trend_tracker.py`** - 경쟁사 동향 및 트렌드 분석
- **`src/dashboard.py`** - HTML 대시보드 자동 생성
- **`src/app_monitor.py`** - 앱스토어/플레이스토어 모니터링

### 기존 모듈 개선
- **`src/main.py`** - 전체 파이프라인 통합 및 전주 리포트 중복 체크 기능
- **`src/llm_analyzer.py`** - Claude API 전용 전환 및 API 사용량 최적화
- **`src/web_searcher.py`** - 검색 결과 관련성 필터링 및 노이즈 제거 강화
- **`src/report_generator.py`** - 리포트 포맷 개선
- **`src/slack_notifier.py`** - 발송 시간 설정(월요일 9:30) 및 문의 안내 추가

### 인프라
- **`.github/workflows/competitor-analysis.yml`** - GitHub Actions 워크플로우 설정
- **`config.yaml`** - 경쟁사 목록 및 분석 설정

### 데이터/리포트
- `data/` - 분석 이력, 가격 데이터, 사이트 스냅샷 저장
- `reports/` - 주간 경쟁사 분석 리포트 및 HTML 대시보드

## 커밋 이력

| 커밋 | 설명 |
|------|------|
| `49a0d92` | feat: 경쟁사 분석 시스템 대규모 업그레이드 |
| `394b05f` | refactor: Claude API 전용으로 전환 및 API 사용량 최적화 |
| `ae5f5d9` | feat: 전주 리포트 중복 체크 기능 추가 |
| `4482a72` | fix: 예외 핸들러 안전성 및 타입 변환 오류 수정 |
| `5738f2d` | fix: 코드 리뷰 - html 모듈 섀도잉, XSS, 미사용 import 수정 |
| `3c3a16c` | fix: 검색 결과 관련성 필터링 및 403 에러 처리 개선 |
| `2081e0b` | fix: 검색 결과 노이즈 필터링 강화 |
| `a6f453b` | chore: 발송 시간 월요일 9시 30분으로 변경 |

## 변경 규모

- **34 files changed**
- **+6,026 insertions**, **-138 deletions**

## 테스트 방법

1. `config.yaml`에서 API 키 설정 확인
2. `python src/main.py` 실행하여 전체 파이프라인 동작 확인
3. `reports/` 디렉토리에서 생성된 리포트 및 대시보드 확인
4. Slack webhook 설정 후 알림 수신 확인
