#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
============================================================
School Psychology Testing App - Report Generation Service
============================================================
Компонент: Сервис формирования отчетности в формате DOCX.
Библиотеки: python-docx, matplotlib (для графиков).
Senior Level: Чистая логика, обработка байтов, клин-код.
============================================================
"""

import io
import logging

import matplotlib.pyplot as plt
from docx import Document
from docx.shared import Inches

# Настройка логгера
logger = logging.getLogger(__name__)


class ReportService:
    """Сервис формирования печатных протоколов для школьного психолога."""

    @staticmethod
    def generate_docx_report(data: dict, output_path: str):
        """
        🚀 Генерация профессионального протокола обследования (Senior V10.0).
        data: содержит 'student', 'summary', 'answers'.
        Реализована поддержка расшифровки ФИО и очистки HTML-тегов.
        """
        try:
            doc = Document()

            # --- Вспомогательная функция для безопасного декодирования ФИО ---
            def safe_decode(field):
                if field is None:
                    return ""
                try:
                    # Если данные пришли из БД как memoryview/bytes
                    return field.tobytes().decode("utf-8") if hasattr(field, "tobytes") else str(field)
                except Exception:
                    return str(field)

            # --- ЗАГОЛОВОК ДОКУМЕНТА ---
            title = doc.add_heading('ПРОТОКОЛ ПСИХОЛОГИЧЕСКОГО ТЕСТИРОВАНИЯ', 0)
            title.alignment = 1  # Центрирование

            # --- БЛОК 1: ИНФОРМАЦИЯ ОБ ИСПЫТУЕМОМ ---
            # Индексы согласно методу get_detailed_report_data:
            # 0: code, 1: last, 2: first, 3: class, 4: test, 5: date, 6: middle
            s = data['student']
            
            # Декодируем ФИО
            last_name = safe_decode(s[1])
            first_name = safe_decode(s[2])
            middle_name = safe_decode(s[6]) if len(s) > 6 else ""
            full_fio = f"{last_name} {first_name} {middle_name}".strip()

            doc.add_heading('Индивидуальные данные', level=1)
            info_p = doc.add_paragraph()
            
            # Дата обследования
            date_val = s[5].strftime('%d.%m.%Y %H:%M') if s[5] else "Не зафиксирована"
            info_p.add_run("Дата обследования: ").bold = True
            info_p.add_run(f"{date_val}\n")
            
            # Данные ученика
            info_p.add_run("Учащийся: ").bold = True
            info_p.add_run(f"{full_fio} (Класс: {s[3] if s[3] else '---'})\n")
            
            # Название теста
            info_p.add_run("Используемая методика: ").bold = True
            info_p.add_run(str(s[4]))

            doc.add_paragraph("-" * 55)

            # --- БЛОК 2: РЕЗУЛЬТАТЫ И ИНТЕРПРЕТАЦИЯ ---
            # summary: [0: score, 1: level_risk, 2: full_text]
            sum_data = data['summary']
            doc.add_heading('1. Результаты и интерпретация', level=1)
            
            res_p = doc.add_paragraph()
            res_p.add_run("Интегральный балл: ").bold = True
            res_p.add_run(f"{sum_data[0]}\n")
            
            res_p.add_run("Категория состояния (Уровень риска): ").bold = True
            res_p.add_run(f"{sum_data[1]}")
            
            # Очистка и вставка подробного заключения
            # Убираем HTML-теги, которые используются в GUI для оформления (<b>, <i>, <br>)
            conclusion_text = str(sum_data[2]).replace('<b>', '').replace('</b>', '')
            conclusion_text = conclusion_text.replace('<i>', '').replace('</i>', '')
            conclusion_text = conclusion_text.replace('<br>', '\n').replace('<br/>', '\n')
            
            doc.add_paragraph(conclusion_text)

            # --- БЛОК 3: ГРАФИЧЕСКИЙ ПРОФИЛЬ ---
            # Генерация графика через метод create_chart
            doc.add_heading('2. Визуализация показателей (Графический профиль)', level=1)
            try:
                # Генерируем картинку в памяти
                img_stream = ReportService.create_chart(data)
                doc.add_picture(img_stream, width=Inches(6.0))
                img_stream.close()
            except Exception as chart_err:
                logger.error(f"Chart inclusion error: {chart_err}")
                doc.add_paragraph("[Графический профиль недоступен для данной сессии]")

            # --- БЛОК 4: ТАБЛИЦА ОТВЕТОВ ---
            doc.add_page_break() # Начинаем новую страницу для детальных ответов
            doc.add_heading('3. Детализация ответов по заданиям', level=1)
            doc.add_paragraph("Ниже приведены выборы учащегося по каждому пункту методики.")
            
            table = doc.add_table(rows=1, cols=3)
            table.style = 'Table Grid'
            
            # Настройка шапки таблицы
            hdr_cells = table.rows[0].cells
            hdr_cells[0].text = 'Задание / вопрос'
            hdr_cells[1].text = 'Выбранный ответ'
            hdr_cells[2].text = 'Баллы'

            # Наполнение таблицы из данных answers
            for answer in data['answers']:
                row_cells = table.add_row().cells
                if isinstance(answer, dict):
                    row_cells[0].text = str(answer.get("question", ""))
                    row_cells[1].text = str(answer.get("choice", ""))
                    row_cells[2].text = (
                        str(answer["score"]) if answer.get("score") is not None else ""
                    )
                    for image in answer.get("images", []):
                        image_stream = io.BytesIO(bytes(image["data"]))
                        row_cells[1].paragraphs[0].add_run().add_picture(
                            image_stream, width=Inches(1.4)
                        )
                        image_stream.close()
                else:
                    question_text, response = answer
                    row_cells[0].text = str(question_text)
                    row_cells[1].text = str(response)
                    row_cells[2].text = ""

            # --- СОХРАНЕНИЕ ---
            doc.save(output_path)
            logger.info(f"💾 Файл успешно сформирован: {output_path}")

        except Exception as global_err:
            logger.error(f"❌ Критический сбой при формировании DOCX отчета: {global_err}")
            # Пробрасываем ошибку выше для отображения QMessageBox в GUI
            raise global_err
    
    
    @staticmethod
    def create_chart(data: dict) -> io.BytesIO:
        """
        📊 Создание детального профиля рисков.
        Вместо одного круга строит гистограмму по всем 9 факторам методики.
        """
 
        # 1. Очистка и настройка размера
        plt.clf()
        plt.switch_backend('Agg') # Гарантирует работу в фоновом режиме без открытия окон
        plt.figure(figsize=(10, 6))

        # 2. Подготовка данных из Блока 'scales', который мы добавили в DatabaseService
        # d[0] - название, d[1] - балл, d[2] - категория (Низкий/Средний/Высокий)
        scales = data.get('scales', [])
        is_choice_method = data.get("test_mode") == "choice"
        
        if not scales:
            if is_choice_method:
                score = float(data['summary'][0])
                plt.bar(["Набранный балл"], [score], color="#4c78a8")
                plt.ylabel("Баллы")
                plt.title("Итоговый балл по выбранным вариантам")
            else:
                # Резервный график для методик без детальных шкал.
                labels = ['Набранный балл', 'Запас']
                score = float(data['summary'][0])
                plt.pie([score, max(0, 35 - score)], labels=labels, autopct='%1.1f%%', colors=['#ff6b6b', '#1dd1a1'])
                plt.title("Общий показатель риска")
        else:
            # Строим профессиональную гистограмму профиля
            names = [s[0].split('. ')[-1] for s in scales] # Убираем цифру "1. " из названия для краткости
            scores = [float(s[1]) for s in scales]
            risks = [str(s[2]) for s in scales]
            
            # Цветовая кодировка каждого столбика
            colors = []
            for risk in risks:
                if is_choice_method:
                    colors.append("#4c78a8")
                elif "Высокий" in risk: 
                    colors.append('#e74c3c') # Красный
                elif "Средний" in risk: 
                    colors.append('#f1c40f') # Желтый
                else: 
                    colors.append('#2ecc71') # Зеленый

            # Рисуем столбики
            bars = plt.bar(names, scores, color=colors, edgecolor='#555', linewidth=1)
            
            # Настройка осей и подписей
            plt.xticks(rotation=30, ha='right', fontsize=9)
            plt.ylabel('Баллы (с учетом коэффициентов)', fontsize=10)
            chart_title = (
                "Профиль результатов по шкалам"
                if is_choice_method
                else "Профилактический профиль факторов суицидального риска"
            )
            plt.title(chart_title, fontsize=12, pad=20)
            plt.grid(axis='y', linestyle='--', alpha=0.6)
            
            # Добавляем значения баллов над каждым столбиком
            for bar in bars:
                height = bar.get_height()
                plt.text(bar.get_x() + bar.get_width()/2., height + 0.1, f'{height}', ha='center', va='bottom', fontsize=8)

        # 3. Сохранение в байтовый поток
        img_buffer = io.BytesIO()
        plt.savefig(img_buffer, format='png', bbox_inches='tight', dpi=120)
        img_buffer.seek(0)
        plt.close()
        
        return img_buffer