import pytest

from src.services.scoring import score_selected_options


def test_multiple_selection_scores_are_summed():
    options = [
        {"id": "a", "value": 1.25},
        {"id": "b", "value": 2},
        {"id": "c", "value": 7},
    ]

    assert score_selected_options(options, ["a", "b"]) == 3.25


def test_selection_score_rejects_missing_or_duplicate_options():
    options = [{"id": "a", "value": 1}]

    with pytest.raises(ValueError, match="At least one"):
        score_selected_options(options, [])
    with pytest.raises(ValueError, match="more than once"):
        score_selected_options(options, ["a", "a"])
    with pytest.raises(ValueError, match="Unknown answer option"):
        score_selected_options(options, ["missing"])


def test_selection_score_rejects_non_numeric_values():
    with pytest.raises(ValueError, match="must be numeric"):
        score_selected_options([{"id": "a", "value": "invalid"}], ["a"])
