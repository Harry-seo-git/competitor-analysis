"""유심사 경쟁사 분석 자동화 메인 스크립트"""

import argparse
import logging
import sys
from pathlib import Path

# 프로젝트 루트 디렉토리 기준으로 경로 설정
PROJECT_ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config_loader import get_all_competitors, load_config
from report_generator import (
    analyze_competitor_results,
    generate_report,
    save_report,
)
from slack_notifier import send_to_slack
from web_searcher import search_competitor

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
    logger.info(f"분석 대상 경쟁사: {len(competitors)}개")

    # 2. 경쟁사별 웹 검색 및 분석
    all_analyses = []
    for comp in competitors:
        logger.info(f"검색 중: {comp['name']} ({comp['region']})")
        search_results = search_competitor(comp)
        logger.info(f"  - {len(search_results)}개 검색 결과 수집")

        analysis = analyze_competitor_results(comp, search_results)
        analysis["region"] = comp["region"]
        all_analyses.append(analysis)

    # 3. 리포트 생성 (프로젝트 루트의 reports/ 디렉토리에 저장)
    report = generate_report(all_analyses, config)
    reports_dir = str(PROJECT_ROOT / "reports")
    report_path = save_report(report, output_dir=reports_dir)
    logger.info(f"리포트 생성 완료: {report_path}")

    # 4. Slack 전송
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
