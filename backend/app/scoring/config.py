"""Loads and validates weights.json — the single source of truth for the
scoring model. Fails loudly (at import time) if the config is internally
inconsistent, rather than silently producing a scoring model that doesn't
actually sum to 100.
"""
from __future__ import annotations

import functools
import json
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parent / "weights.json"


class WeightsConfigError(Exception):
    pass


@functools.lru_cache(maxsize=1)
def load_weights_config(path: Path | None = None) -> dict:
    config_path = path or CONFIG_PATH
    with config_path.open(encoding="utf-8") as f:
        config = json.load(f)

    _validate(config)
    return config


def _validate(config: dict) -> None:
    factors = config["factors"]
    categories = config["categories"]

    total_weight = sum(f["weight_points"] for f in factors.values())
    if abs(total_weight - 100.0) > 1e-6:
        raise WeightsConfigError(f"Factor weights must sum to 100, got {total_weight}")

    for category_name, category in categories.items():
        category_factor_weight = sum(factors[name]["weight_points"] for name in category["factors"])
        if abs(category_factor_weight - category["weight_pct"]) > 1e-6:
            raise WeightsConfigError(
                f"Category {category_name!r} declares weight_pct={category['weight_pct']} but its "
                f"factors sum to {category_factor_weight}"
            )

    category_pct_total = sum(c["weight_pct"] for c in categories.values())
    if abs(category_pct_total - 100.0) > 1e-6:
        raise WeightsConfigError(f"Category weight_pct values must sum to 100, got {category_pct_total}")

    all_category_factors = {name for c in categories.values() for name in c["factors"]}
    if all_category_factors != set(factors.keys()):
        raise WeightsConfigError("Every factor must belong to exactly one category")


def category_for_factor(factor_name: str, config: dict | None = None) -> str:
    config = config or load_weights_config()
    for category_name, category in config["categories"].items():
        if factor_name in category["factors"]:
            return category_name
    raise WeightsConfigError(f"Factor {factor_name!r} not assigned to any category")
