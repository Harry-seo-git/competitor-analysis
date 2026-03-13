"""유심사 경쟁사 분석 자동화 메인 스크립트"""

import argparse
import logging
import sys
from pathlib import Path

# 프로젝트 루트 디렉토리 기준으로 경로 설정
PROJECT_ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config_loader import get_all_competitors, load_config
from llm_analyzer import analyze_competitor, generate_suggestions, get_active_backend
from report_generator import generate_report, save_report
from slack_notifier import send_to_slack
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

    # 2. 경쟁사별 웹 검색 → 페이지 수집 → LLM 분석
    all_analyses = []
    for comp in competitors:
        logger.info(f"[{comp['name']}] 검색 중...")

        # 웹 검색
        search_results = search_competitor(comp)
        logger.info(f"  검색 결과: {len(search_results)}건")

        # 상위 결과의 페이지 본문 수집
        page_contents = fetch_pages_for_results(search_results, max_pages=3)
        logger.info(f"  페이지 수집: {len(page_contents)}건")

        # LLM 분석 (또는 키워드 폴백)
        analysis = analyze_competitor(comp["name"], search_results, page_contents)
        analysis["region"] = comp["region"]
        all_analyses.append(analysis)

    # 3. 전략 제안 생성
    suggestions = generate_suggestions(all_analyses)

    # 4. 리포트 생성
    report = generate_report(all_analyses, suggestions, backend)
    reports_dir = str(PROJECT_ROOT / "reports")
    report_path = save_report(report, output_dir=reports_dir)
    logger.info(f"리포트 생성 완료: {report_path}")

    # 5. Slack 전송
    if not skip_slack:
        success = send_to_slack(report)
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
