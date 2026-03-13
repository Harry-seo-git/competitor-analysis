"""설정 파일 로더"""

import os
from pathlib import Path

import yaml


def load_config(config_path: str = None) -> dict:
    """config.yaml 파일을 로드합니다."""
    if config_path is None:
        config_path = Path(__file__).parent.parent / "config.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_all_competitors(config: dict) -> list[dict]:
    """국내/해외 경쟁사 목록을 통합하여 반환합니다."""
    competitors = []
    for comp in config["competitors"].get("domestic", []):
        comp["region"] = "domestic"
        competitors.append(comp)
    for comp in config["competitors"].get("international", []):
        comp["region"] = "international"
        competitors.append(comp)
    return competitors
