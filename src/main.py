"""유심사 경쟁사 분석 자동화 메인 스크립트"""

import argparse
import logging
import sys
import time
from pathlib import Path

# 프로젝트 루트 디렉토리 기준으로 경로 설정
PROJECT_ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app_monitor import fetch_all_app_info
from config_loader import get_all_competitors, load_config
from dashboard import generate_dashboard
from llm_analyzer import analyze_competitor, generate_executive_summary, generate_suggestions, get_active_backend
from pricing_monitor import collect_pricing, detect_pricing_changes, generate_comparison_table
from report_generator import generate_report, save_report
from site_snapshot import monitor_all_sites
from slack_notifier import send_report_to_slack
from trend_tracker import (
    load_history, load_previous_urls, load_trend_histories,
    save_history, compare_with_previous,
)
from web_searcher import fetch_pages_for_results, search_competitor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def run_analysis(config_path: str = None, skip_slack: bool = False) -> str:
    """경쟁사 분석을 실행하고 리포트를 생성합니다."""
    logger.info("=== 유심사 경쟁사 분석 시작 ===")

    # 1. 설정 로드
    if config_path is None:
        config_path = str(PROJECT_ROOT / "config.yaml")
    config = load_config(config_path)
    competitors = get_all_competitors(config)

    backend = get_active_backend()
    logger.info(f"분석 대상 경쟁사: {len(competitors)}개 | 분석 엔진: {backend}")

    # 2. 앱스토어 정보 수집
    logger.info("=== 앱스토어 정보 수집 ===")
    app_info = fetch_all_app_info(competitors)

    # 3. 경쟁사 웹사이트 스냅샷 및 변경 감지
    logger.info("=== 웹사이트 스냅샷 수집 ===")
    site_changes = monitor_all_sites(competitors)

    # 4. 히스토리 로드 (트렌드 비교 + 중복 URL 제거에 공통 사용)
    history_dir = str(PROJECT_ROOT / "data" / "history")
    previous_history = load_history(history_dir)
    previous_urls = load_previous_urls(previous_history)

    # 5. 경쟁사별 웹 검색 → 페이지 수집 → LLM 분석
    all_analyses = []
    errors = []
    for comp in competitors:
        logger.info(f"[{comp['name']}] 검색 중...")
        try:
            # 웹 검색 (이전 주 URL 제외)
            search_results = search_competitor(comp, previous_urls=previous_urls)
            logger.info(f"  검색 결과: {len(search_results)}건")

            # 상위 결과의 페이지 본문 수집
            page_contents = fetch_pages_for_results(search_results, max_pages=3)
            logger.info(f"  페이지 수집: {len(page_contents)}건")

            # LLM 분석 (또는 키워드 폴백)
            analysis = analyze_competitor(comp["name"], search_results, page_contents)
            analysis["region"] = comp["region"]

            # 앱스토어 정보 병합
            analysis["app_info"] = app_info.get(comp["name"], [])

            # 사이트 변경 정보 병합
            analysis["site_changes"] = site_changes.get(comp["name"], {})

            # 경쟁사 링크 정보 병합
            analysis["url"] = comp.get("url", "")
            analysis["app_store"] = comp.get("app_store", "")
            analysis["play_store"] = comp.get("play_store", "")

            all_analyses.append(analysis)
        except Exception as e:
            logger.error(f"[{comp['name']}] 분석 실패: {e}")
            errors.append({"name": comp["name"], "error": str(e)})

        # API rate limit 방지
        time.sleep(3)

    # 6. Executive Summary + 전략 제안 생성
    executive_summary = generate_executive_summary(all_analyses)
    suggestions = generate_suggestions(all_analyses)

    # 7. 트렌드 비교 (이전 주 대비)
    trend = compare_with_previous(all_analyses, previous_history)
    save_history(all_analyses, history_dir)

    # 8. 요금제 비교 수집 + 가격 변동 감지
    logger.info("=== 요금제 정보 수집 ===")
    pricing_data = collect_pricing(competitors)
    price_changes = detect_pricing_changes(pricing_data)
    pricing_table = generate_comparison_table(pricing_data, price_changes=price_changes)

    # 9. 리포트 생성
    report = generate_report(
        all_analyses, suggestions, backend,
        trend=trend, pricing_table=pricing_table,
        executive_summary=executive_summary,
    )
    reports_dir = str(PROJECT_ROOT / "reports")
    report_path = save_report(report, output_dir=reports_dir)
    logger.info(f"리포트 생성 완료: {report_path}")

    # 10. 대시보드 생성
    rating_history, release_history = load_trend_histories(history_dir)
    dashboard_path = generate_dashboard(
        all_analyses, suggestions, backend,
        trend=trend, output_dir=reports_dir,
        executive_summary=executive_summary, price_changes=price_changes,
        rating_history=rating_history, release_history=release_history,
    )
    logger.info(f"대시보드 생성 완료: {dashboard_path}")

    # 11. Slack 전송
    if not skip_slack:
        success = send_report_to_slack(
            all_analyses, suggestions, backend,
            trend=trend, errors=errors,
            executive_summary=executive_summary, price_changes=price_changes,
        )
        if success:
            logger.info("Slack 전송 성공")
        else:
            logger.warning("Slack 전송 실패 - 리포트 파일은 저장되었습니다.")

    logger.info("=== 경쟁사 분석 완료 ===")
    return report_path


def main():
    parser = argparse.ArgumentParser(description="유심사 경쟁사 분석 자동화")
    parser.add_argument(
        "--config", type=str, default=None, help="설정 파일 경로"
    )
    parser.add_argument(
        "--skip-slack", action="store_true", help="Slack 전송 건너뛰기"
    )
    args = parser.parse_args()

    try:
        report_path = run_analysis(
            config_path=args.config, skip_slack=args.skip_slack
        )
        print(f"리포트가 생성되었습니다: {report_path}")
    except Exception as e:
        logger.error(f"분석 실행 실패: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
