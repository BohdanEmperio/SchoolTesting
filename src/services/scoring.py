"""Small, deterministic helpers for configured answer scoring."""

import math
from typing import Any, Dict, Iterable, List


def score_selected_options(
    options: List[Dict[str, Any]], selected_ids: Iterable[str]
) -> float:
    """Sum the configured score for each selected option."""
    selected = [str(option_id) for option_id in selected_ids]
    if not selected:
        raise ValueError("At least one answer option must be selected.")
    if len(selected) != len(set(selected)):
        raise ValueError("An answer option cannot be selected more than once.")

    options_by_id = {
        str(option.get("id")): option
        for option in options
        if option.get("id") is not None
    }
    unknown_ids = [option_id for option_id in selected if option_id not in options_by_id]
    if unknown_ids:
        raise ValueError(f"Unknown answer option ID: {unknown_ids[0]}")

    try:
        scores = [
            float(options_by_id[option_id].get("value", 0))
            for option_id in selected
        ]
    except (TypeError, ValueError) as error:
        raise ValueError("Answer option scores must be numeric.") from error
    if any(not math.isfinite(score) or score < 0 for score in scores):
        raise ValueError("Answer option scores must be finite and non-negative.")
    return sum(scores)
