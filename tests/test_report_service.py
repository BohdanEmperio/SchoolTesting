from datetime import datetime

from docx import Document

from src.services.report_service import ReportService, _build_profile


def test_build_profile_classifies_risk_and_protective_scales():
    profile = _build_profile(
        {
            "test_mode": "yes_no",
            "answers": [
                {"number": 1, "question": "Question 1", "value": 1},
                {"number": 2, "question": "Question 2", "choice": "Нет"},
            ],
            "scales": [
                (
                    "1. Demonstration",
                    6,
                    None,
                    10,
                    "SCALE_1",
                    1,
                    "Demonstration. Description",
                    "1, 2",
                ),
                ("9. Protective", 10, None, 10, "SCALE_9", None, "", "1"),
            ],
        }
    )

    risk, protective = profile
    assert risk["short"] == "Demonstration"
    assert risk["level"] == "выражен"
    assert risk["confirmed"] == [1]
    assert risk["description"] == "Description"
    assert protective["protective"] is True
    assert protective["level"] == "сформирован"


def test_generate_choice_report_creates_readable_docx(tmp_path):
    output_path = tmp_path / "choice-report.docx"
    ReportService.generate_docx_report(
        {
            "student": (
                "STU-1",
                "Иванов",
                "Иван",
                "5Б",
                "Методика выбора",
                datetime(2026, 1, 15, 10, 30),
                "Иванович",
            ),
            "summary": (3, "Средний", "<b>Требует внимания</b>"),
            "test_mode": "choice",
            "answers": [
                {"number": 1, "question": "Вопрос", "choice": "Вариант А", "score": 3}
            ],
            "scales": [],
        },
        str(output_path),
    )

    document = Document(str(output_path))
    text = "\n".join(
        [paragraph.text for paragraph in document.paragraphs]
        + [cell.text for table in document.tables for row in table.rows for cell in row.cells]
    )
    assert "ПРОТОКОЛ ПСИХОЛОГИЧЕСКОГО ТЕСТИРОВАНИЯ" in text
    assert "Методика выбора" in text
    assert "Требует внимания" in text
    assert "Вариант А" in text
