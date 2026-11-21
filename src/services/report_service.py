#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
============================================================
School Psychology Testing App - Report Generation Service
============================================================
Компонент: Сервис формирования протоколов в формате DOCX.
Библиотеки: python-docx, matplotlib, Pillow.

Состав протокола методики «Да/Нет» со шкалами (ОСР):
  1. Индивидуальные данные
  2. Итоговые показатели
  3. Профиль по шкалам (таблица)
  4. Диаграммы: столбчатая (профиль шкал) и круговые
     (распределение ответов и вклад факторов риска)
  5. Анализ по каждой шкале (интерпретация)
  6. Список ответов на утверждения
  7. Заключение психолога (поля для заполнения)

Для методик с выбором вариантов (test_mode = "choice") сохраняется
прежний вид: итоговый балл, диаграмма и таблица ответов с рисунками.
============================================================
"""

import io
import logging
from typing import Any, Dict, List, Optional

import matplotlib

matplotlib.use("Agg")  # без окон: графики рисуются только в память
import matplotlib.pyplot as plt  # noqa: E402
from docx import Document  # noqa: E402
from docx.enum.text import WD_ALIGN_PARAGRAPH  # noqa: E402
from docx.shared import Inches, Pt, RGBColor  # noqa: E402

logger = logging.getLogger(__name__)

# Условные градации выраженности фактора (доля от максимума шкалы).
# В методике сказано только: «чем ближе значение к максимуму, тем сильнее выражен
# фактор». Порог 60% совпадает с порогом «Высокий» в calculate_osr_session.
LEVEL_HIGH = 0.60
LEVEL_MID = 0.30

COLOR_HIGH = "#e74c3c"
COLOR_MID = "#f1c40f"
COLOR_LOW = "#2ecc71"
COLOR_NONE = "#bdc3c7"
COLOR_PROTECT = "#3498db"
COLOR_MAX = "#ecf0f1"


# ------------------------------------------------------------------
# Вспомогательные функции
# ------------------------------------------------------------------

def _picture_for_docx(raw: bytes, max_side: int = 800) -> io.BytesIO:
    """
    Приводит изображение к виду, который гарантированно понимает python-docx.

    python-docx не распознаёт часть корректных JPEG (например, без заголовка
    JFIF/EXIF: байты FF D8 FF DB). Поэтому картинка пересохраняется через Pillow
    в стандартный JPEG и заодно уменьшается: отчёт не раздувается от фото 1280px.
    """
    from PIL import Image

    with Image.open(io.BytesIO(raw)) as img:
        img = img.convert("RGB")
        img.thumbnail((max_side, max_side))
        out = io.BytesIO()
        img.save(out, format="JPEG", quality=85)
    out.seek(0)
    return out


def _safe_decode(field: Any) -> str:
    """ФИО хранится в BYTEA: psycopg2 отдаёт memoryview/bytes."""
    if field is None:
        return ""
    try:
        if hasattr(field, "tobytes"):
            return field.tobytes().decode("utf-8")
        if isinstance(field, (bytes, bytearray)):
            return bytes(field).decode("utf-8")
        return str(field)
    except Exception:
        return str(field)


def _num(value: Any, digits: int = 1) -> str:
    """Единый формат чисел в протоколе: 3.2000 -> «3,2», 6 -> «6,0»."""
    try:
        return f"{float(value):.{digits}f}".replace(".", ",")
    except (TypeError, ValueError):
        return "—"


def _is_yes(answer: Dict[str, Any]) -> bool:
    value = answer.get("value")
    if value is not None:
        try:
            return float(value) == 1
        except (TypeError, ValueError):
            pass
    return str(answer.get("choice", "")).strip().lower() in ("да", "+", "yes")


def _short_name(scale_name: str) -> str:
    """'1. Демонстративность' -> 'Демонстративность'."""
    name = str(scale_name).strip()
    head, sep, tail = name.partition(". ")
    return tail if sep and head.isdigit() else name


def _strip_title(text: str, short_name: str) -> str:
    """Убирает из описания повтор названия шкалы в начале: 'Аффективность. ...'."""
    text = str(text or "").strip()
    prefix = short_name + "."
    if text.lower().startswith(prefix.lower()):
        return text[len(prefix):].strip()
    return text


def _set_cell(cell, text: str, bold: bool = False, size: Optional[int] = None,
              align=None, color: Optional[RGBColor] = None) -> None:
    cell.text = ""
    paragraph = cell.paragraphs[0]
    run = paragraph.add_run(text)
    run.bold = bold
    if size:
        run.font.size = Pt(size)
    if color is not None:
        run.font.color.rgb = color
    if align is not None:
        paragraph.alignment = align


def _set_widths(table, widths_in_inches: List[float]) -> None:
    """Фиксирует ширину колонок (Word иначе делит таблицу поровну)."""
    table.autofit = False
    for column, width in zip(table.columns, widths_in_inches):
        column.width = Inches(width)  # сетка таблицы (LibreOffice, Word Online)
    for row in table.rows:
        for cell, width in zip(row.cells, widths_in_inches):
            cell.width = Inches(width)  # ширина ячеек (настольный Word)


def _fig_to_stream(fig) -> io.BytesIO:
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", bbox_inches="tight", dpi=130)
    plt.close(fig)
    buffer.seek(0)
    return buffer


# ------------------------------------------------------------------
# Подготовка профиля шкал
# ------------------------------------------------------------------

def _build_profile(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Собирает по каждой шкале всё, что нужно для таблицы, графиков и анализа."""
    answers = data.get("answers", [])
    by_number: Dict[int, Dict[str, Any]] = {}
    for index, answer in enumerate(answers, start=1):
        if not isinstance(answer, dict):
            continue
        number = answer.get("number") or index
        by_number[int(number)] = answer

    is_yes_no = data.get("test_mode", "yes_no") != "choice"
    profile = []
    for row in data.get("scales", []):
        name = str(row[0])
        score = float(row[1] or 0)
        max_score = float(row[3] or 0)
        code = str(row[4]) if len(row) > 4 and row[4] else ""
        coef = float(row[5]) if len(row) > 5 and row[5] is not None else None
        description = str(row[6]) if len(row) > 6 and row[6] else ""
        mapping_raw = str(row[7]) if len(row) > 7 and row[7] else ""
        numbers = [int(x) for x in mapping_raw.split(",") if x.strip().isdigit()]

        short = _short_name(name)
        protective = is_yes_no and (
            code == "SCALE_9" or "антисуицид" in short.lower()
        )
        confirmed = [n for n in numbers if n in by_number and _is_yes(by_number[n])]
        share = score / max_score if max_score > 0 else 0.0

        if protective:
            if share >= 0.99:
                level, color = "сформирован", COLOR_PROTECT
            elif share > 0:
                level, color = "сформирован частично", COLOR_MID
            else:
                level, color = "не выявлен", COLOR_HIGH
        else:
            if score <= 0:
                level, color = "не выявлен", COLOR_NONE
            elif share >= LEVEL_HIGH:
                level, color = "выражен", COLOR_HIGH
            elif share >= LEVEL_MID:
                level, color = "умеренно выражен", COLOR_MID
            else:
                level, color = "слабо выражен", COLOR_LOW

        profile.append(
            {
                "name": name,
                "short": short,
                "code": code,
                "score": score,
                "max": max_score,
                "share": share,
                "coef": coef,
                "numbers": numbers,
                "confirmed": confirmed,
                "protective": protective,
                "level": level,
                "color": color,
                "description": _strip_title(description, short),
            }
        )
    return profile


# ------------------------------------------------------------------
# Диаграммы
# ------------------------------------------------------------------

def _bar_chart(profile: List[Dict[str, Any]], title: str) -> io.BytesIO:
    """Столбчатая диаграмма: балл шкалы на фоне её максимума."""
    fig, ax = plt.subplots(figsize=(10, 5.6))
    names = [p["short"] for p in profile]
    x = range(len(profile))
    ax.bar(x, [p["max"] for p in profile], color=COLOR_MAX, edgecolor="#95a5a6",
           linewidth=0.8, label="Максимум шкалы")
    bars = ax.bar(x, [p["score"] for p in profile], width=0.6,
                  color=[p["color"] for p in profile], edgecolor="#555", linewidth=0.8)
    for bar, p in zip(bars, profile):
        ax.text(bar.get_x() + bar.get_width() / 2, p["score"] + 0.1,
                f"{_num(p['score'])}\n({p['share'] * 100:.0f}%)",
                ha="center", va="bottom", fontsize=8)
    ax.set_xticks(list(x))
    ax.set_xticklabels(names, rotation=30, ha="right", fontsize=9)
    ax.set_ylabel("Баллы (с учётом коэффициентов)")
    ax.set_title(title, fontsize=12, pad=14)
    ax.grid(axis="y", linestyle="--", alpha=0.5)
    ax.set_axisbelow(True)

    from matplotlib.patches import Patch
    legend = [Patch(facecolor=COLOR_MAX, edgecolor="#95a5a6", label="максимум шкалы"),
              Patch(facecolor=COLOR_HIGH, label="выражен (≥60%)"),
              Patch(facecolor=COLOR_MID, label="умеренно (30–59%)"),
              Patch(facecolor=COLOR_LOW, label="слабо (<30%)")]
    if any(p["protective"] for p in profile):
        legend.append(Patch(facecolor=COLOR_PROTECT, label="защитный фактор сформирован"))
    ax.legend(handles=legend, fontsize=8, loc="upper left", bbox_to_anchor=(1.01, 1))
    return _fig_to_stream(fig)


def _pie_charts(profile: List[Dict[str, Any]], yes_count: int, total: int) -> io.BytesIO:
    """Две круговые диаграммы: ответы «Да/Нет» и вклад факторов риска в индекс."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 5))

    no_count = max(total - yes_count, 0)
    ax1.pie([yes_count, no_count],
            labels=[f"«Да» — {yes_count}", f"«Нет» — {no_count}"],
            colors=["#e67e22", "#95a5a6"], autopct="%1.0f%%", startangle=90,
            wedgeprops={"edgecolor": "white"})
    ax1.set_title(f"Распределение ответов (всего {total})", fontsize=11)

    risk = [p for p in profile if not p["protective"] and p["score"] > 0]
    if risk:
        ax2.pie([p["score"] for p in risk],
                labels=[f"{p['short']}\n{_num(p['score'])}" for p in risk],
                colors=[plt.cm.tab20(i) for i in range(len(risk))],
                autopct="%1.0f%%", startangle=90, textprops={"fontsize": 8},
                wedgeprops={"edgecolor": "white"})
        ax2.set_title("Вклад факторов риска в индекс", fontsize=11)
    else:
        ax2.text(0.5, 0.5, "Факторы риска\nне выявлены", ha="center", va="center",
                 fontsize=13)
        ax2.axis("off")
    return _fig_to_stream(fig)


# ------------------------------------------------------------------
# Сервис
# ------------------------------------------------------------------

class ReportService:
    """Сервис формирования печатных протоколов для школьного психолога."""

    @staticmethod
    def generate_docx_report(data: dict, output_path: str):
        """Формирует протокол обследования и сохраняет его по output_path."""
        try:
            doc = Document()
            style = doc.styles["Normal"]
            style.font.name = "Calibri"
            style.font.size = Pt(11)
            for section in doc.sections:
                section.left_margin = section.right_margin = Inches(0.8)
                section.top_margin = section.bottom_margin = Inches(0.7)

            title = doc.add_heading("ПРОТОКОЛ ПСИХОЛОГИЧЕСКОГО ТЕСТИРОВАНИЯ", 0)
            title.alignment = WD_ALIGN_PARAGRAPH.CENTER

            ReportService._add_personal_block(doc, data)

            profile = _build_profile(data)
            is_choice = data.get("test_mode") == "choice"

            if profile and not is_choice:
                ReportService._add_scale_report(doc, data, profile)
            else:
                ReportService._add_simple_report(doc, data, profile)

            ReportService._add_conclusion_block(doc)
            doc.save(output_path)
            logger.info(f"💾 Файл успешно сформирован: {output_path}")

        except Exception as global_err:
            logger.error(
                f"❌ Критический сбой при формировании DOCX отчета: "
                f"{type(global_err).__name__} {global_err}"
            )
            raise global_err

    # ---------------------------- блоки ----------------------------

    @staticmethod
    def _add_personal_block(doc, data: dict) -> None:
        s = data["student"]
        last_name = _safe_decode(s[1])
        first_name = _safe_decode(s[2])
        middle_name = _safe_decode(s[6]) if len(s) > 6 else ""
        full_fio = f"{last_name} {first_name} {middle_name}".strip()

        doc.add_heading("Индивидуальные данные", level=1)
        info = doc.add_paragraph()
        date_val = s[5].strftime("%d.%m.%Y %H:%M") if s[5] else "Не зафиксирована"
        info.add_run("Дата обследования: ").bold = True
        info.add_run(f"{date_val}\n")
        info.add_run("Учащийся: ").bold = True
        info.add_run(f"{full_fio} (код {s[0]}, класс: {s[3] if s[3] else '—'})\n")
        info.add_run("Методика: ").bold = True
        info.add_run(str(s[4]))

    @staticmethod
    def _add_scale_report(doc, data: dict, profile: List[Dict[str, Any]]) -> None:
        answers = [a for a in data.get("answers", []) if isinstance(a, dict)]
        total = len(answers)
        yes_count = sum(1 for a in answers if _is_yes(a))
        summary = data.get("summary") or (0, "—", "")

        risk = [p for p in profile if not p["protective"]]
        protect = [p for p in profile if p["protective"]]
        index_value = sum(p["score"] for p in risk)
        index_max = sum(p["max"] for p in risk)

        # 1. Итоговые показатели
        doc.add_heading("1. Итоговые показатели", level=1)
        res = doc.add_paragraph()
        res.add_run("Индекс суицидального риска (сумма шкал 1–8): ").bold = True
        res.add_run(f"{_num(index_value)} из {_num(index_max)}\n")
        if protect:
            p9 = protect[0]
            res.add_run("Антисуицидальный фактор: ").bold = True
            res.add_run(f"{_num(p9['score'])} из {_num(p9['max'])} — {p9['level']}\n")
        res.add_run("Уровень риска: ").bold = True
        level_run = res.add_run(str(summary[1]))
        level_run.bold = True
        if "Высокий" in str(summary[1]):
            level_run.font.color.rgb = RGBColor(0xC0, 0x39, 0x2B)
        res.add_run(f"\nОтветов «Да»: {yes_count} из {total}")

        # 2. Профиль по шкалам
        doc.add_heading("2. Профиль по шкалам", level=1)
        headers = ["№", "Шкала", "Утверждения", "Подтверждено «Да»",
                   "Коэф.", "Балл", "Макс.", "% от макс.", "Выраженность"]
        table = doc.add_table(rows=1, cols=len(headers))
        table.style = "Table Grid"
        for cell, text in zip(table.rows[0].cells, headers):
            _set_cell(cell, text, bold=True, size=9)
        for index, p in enumerate(profile, start=1):
            cells = table.add_row().cells
            values = [
                str(index), p["short"],
                ", ".join(map(str, p["numbers"])) or "—",
                (", ".join(map(str, p["confirmed"])) or "—")
                + f"  ({len(p['confirmed'])}/{len(p['numbers'])})",
                _num(p["coef"]) if p["coef"] is not None else "—",
                _num(p["score"]), _num(p["max"]),
                f"{p['share'] * 100:.0f}%", p["level"],
            ]
            for cell, text in zip(cells, values):
                _set_cell(cell, text, size=9)
        _set_widths(table, [0.3, 1.35, 0.95, 1.1, 0.45, 0.45, 0.45, 0.55, 0.9])

        # 3. Диаграммы
        doc.add_heading("3. Графический профиль", level=1)
        try:
            doc.add_picture(
                _bar_chart(profile, "Профиль факторов суицидального риска"),
                width=Inches(6.5),
            )
            doc.add_paragraph(
                "Серый столбик — максимально возможное значение шкалы, цветной — "
                "результат учащегося. Для антисуицидального фактора, наоборот, "
                "высокое значение благоприятно."
            ).runs[0].italic = True
        except Exception as chart_err:
            logger.error(f"Bar chart error: {chart_err}")
            doc.add_paragraph("[Столбчатая диаграмма недоступна]")
        try:
            doc.add_picture(_pie_charts(profile, yes_count, total), width=Inches(6.5))
        except Exception as chart_err:
            logger.error(f"Pie chart error: {chart_err}")
            doc.add_paragraph("[Круговые диаграммы недоступны]")

        # 4. Анализ по шкалам
        doc.add_page_break()
        doc.add_heading("4. Анализ по шкалам", level=1)
        question_text = {
            int(a.get("number") or i): str(a.get("question", ""))
            for i, a in enumerate(answers, start=1)
        }
        for index, p in enumerate(profile, start=1):
            doc.add_heading(
                f"{index}. {p['short']} — {_num(p['score'])} из {_num(p['max'])} "
                f"({p['share'] * 100:.0f}%), {p['level']}",
                level=2,
            )
            if p["description"]:
                desc = doc.add_paragraph()
                desc.add_run("Содержание шкалы (по методике): ").bold = True
                desc.add_run(p["description"]).italic = True

            if p["confirmed"]:
                doc.add_paragraph().add_run(
                    f"Учащийся согласился с утверждениями ({len(p['confirmed'])} "
                    f"из {len(p['numbers'])}):"
                ).bold = True
                for n in p["confirmed"]:
                    doc.add_paragraph(f"№{n}. {question_text.get(n, '')}",
                                      style="List Bullet")
            else:
                doc.add_paragraph(
                    "Ни одно утверждение шкалы не подтверждено учащимся."
                )

            doc.add_paragraph().add_run(
                "Вывод: " + ReportService._scale_conclusion(p)
            ).bold = True

        # Сводный вывод
        doc.add_heading("Сводка по профилю", level=2)
        expressed = [p["short"] for p in risk if p["level"] == "выражен"]
        moderate = [p["short"] for p in risk if p["level"] == "умеренно выражен"]
        lines = [
            "Выраженные факторы риска: " + (", ".join(expressed) or "не выявлены") + ".",
            "Умеренно выраженные: " + (", ".join(moderate) or "не выявлены") + ".",
        ]
        if protect:
            lines.append(f"Антисуицидальный фактор: {protect[0]['level']}.")
        for line in lines:
            doc.add_paragraph(line, style="List Bullet")
        note = doc.add_paragraph(
            "Примечание. Градации выраженности (менее 30%, 30–59%, 60% и более от "
            "максимума шкалы) введены в программе для удобства чтения. В методике "
            "указано лишь, что чем ближе значение фактора к максимально возможной "
            "величине, тем более он выражен. Результаты опросника являются "
            "скрининговыми и не являются диагнозом."
        )
        note.runs[0].italic = True
        note.runs[0].font.size = Pt(9)

        # 5. Ответы
        doc.add_page_break()
        doc.add_heading("5. Ответы на утверждения", level=1)
        scales_of: Dict[int, List[str]] = {}
        for index, p in enumerate(profile, start=1):
            for n in p["numbers"]:
                scales_of.setdefault(n, []).append(str(index))
        table = doc.add_table(rows=1, cols=4)
        table.style = "Table Grid"
        for cell, text in zip(table.rows[0].cells, ["№", "Утверждение", "Ответ", "Шкалы"]):
            _set_cell(cell, text, bold=True, size=9)
        for index, a in enumerate(answers, start=1):
            number = int(a.get("number") or index)
            yes = _is_yes(a)
            cells = table.add_row().cells
            _set_cell(cells[0], str(number), size=9)
            _set_cell(cells[1], str(a.get("question", "")), size=9)
            _set_cell(cells[2], "Да" if yes else "Нет", bold=yes, size=9,
                      align=WD_ALIGN_PARAGRAPH.CENTER)
            _set_cell(cells[3], ", ".join(scales_of.get(number, [])) or "—", size=9,
                      align=WD_ALIGN_PARAGRAPH.CENTER)
        _set_widths(table, [0.4, 4.4, 0.7, 1.0])

    @staticmethod
    def _scale_conclusion(p: Dict[str, Any]) -> str:
        if p["protective"]:
            if p["level"] == "сформирован":
                return ("антисуицидальный фактор сформирован: защитные установки "
                        "(ответственность за близких, значимые привязанности) "
                        "подтверждены и снижают общий риск.")
            if p["level"] == "сформирован частично":
                return ("антисуицидальный фактор сформирован частично: защитные "
                        "установки подтверждены не полностью.")
            return ("антисуицидальный фактор не выявлен: защитные установки по "
                    "опроснику не подтверждены. При наличии выраженных факторов "
                    "риска это требует особого внимания.")
        if p["level"] == "не выявлен":
            return "фактор не выявлен."
        if p["level"] == "слабо выражен":
            return "фактор выражен слабо, значение далеко от максимального."
        if p["level"] == "умеренно выражен":
            return ("фактор выражен умеренно: отдельные признаки присутствуют; "
                    "рекомендуется учитывать их в беседе с учащимся.")
        return ("фактор выражен: значение близко к максимальному. Рекомендуется "
                "углублённое обследование и индивидуальная беседа.")

    @staticmethod
    def _add_simple_report(doc, data: dict, profile: List[Dict[str, Any]]) -> None:
        """Методики с выбором вариантов и методики без шкал."""
        summary = data.get("summary") or (0, "—", "")
        doc.add_heading("1. Результаты", level=1)
        res = doc.add_paragraph()
        res.add_run("Итоговый балл: ").bold = True
        res.add_run(f"{summary[0]}\n")
        res.add_run("Результат: ").bold = True
        res.add_run(str(summary[1]))
        conclusion = str(summary[2] or "").replace("<br>", "\n").replace("<br/>", "\n")
        for tag in ("<b>", "</b>", "<i>", "</i>"):
            conclusion = conclusion.replace(tag, "")
        if conclusion:
            doc.add_paragraph(conclusion)

        doc.add_heading("2. Графический профиль", level=1)
        try:
            doc.add_picture(ReportService.create_chart(data, profile), width=Inches(6.0))
        except Exception as chart_err:
            logger.error(f"Chart inclusion error: {chart_err}")
            doc.add_paragraph("[Графический профиль недоступен]")

        doc.add_page_break()
        doc.add_heading("3. Ответы по заданиям", level=1)
        table = doc.add_table(rows=1, cols=3)
        table.style = "Table Grid"
        for cell, text in zip(table.rows[0].cells,
                              ["Задание / вопрос", "Выбранный ответ", "Баллы"]):
            _set_cell(cell, text, bold=True)
        for answer in data.get("answers", []):
            row_cells = table.add_row().cells
            if not isinstance(answer, dict):
                question_text, response = answer
                row_cells[0].text = str(question_text)
                row_cells[1].text = str(response)
                continue
            row_cells[0].text = str(answer.get("question", ""))
            row_cells[1].text = str(answer.get("choice", ""))
            row_cells[2].text = (
                _num(answer["score"]) if answer.get("score") is not None else ""
            )
            for image in answer.get("images", []):
                try:
                    stream = _picture_for_docx(bytes(image["data"]))
                    row_cells[1].paragraphs[0].add_run().add_picture(
                        stream, width=Inches(1.4)
                    )
                    stream.close()
                except Exception as img_err:
                    logger.error(
                        f"Не удалось вставить изображение {image.get('file_name', '')}: "
                        f"{type(img_err).__name__} {img_err}"
                    )
                    row_cells[1].add_paragraph(
                        f"[изображение {image.get('file_name', '')} недоступно]"
                    )

    @staticmethod
    def _add_conclusion_block(doc) -> None:
        doc.add_heading("Заключение педагога-психолога", level=1)
        for _ in range(4):
            doc.add_paragraph("_" * 90)
        doc.add_paragraph("\nПедагог-психолог: ____________________ / ____________________")
        doc.add_paragraph("Дата: «____» ______________ 20___ г.")

    @staticmethod
    def create_chart(data: dict, profile: Optional[List[Dict[str, Any]]] = None) -> io.BytesIO:
        """Диаграмма для методик без шкал «Да/Нет»: профиль шкал или итоговый балл."""
        profile = profile if profile is not None else _build_profile(data)
        if profile:
            return _bar_chart(profile, "Профиль результатов по шкалам")
        fig, ax = plt.subplots(figsize=(6, 4))
        score = float((data.get("summary") or (0,))[0] or 0)
        ax.bar(["Набранный балл"], [score], color="#4c78a8")
        ax.set_ylabel("Баллы")
        ax.set_title("Итоговый балл по выбранным вариантам")
        return _fig_to_stream(fig)
