\encoding UTF8
\set ON_ERROR_STOP on

-- ============================================================================
-- repair_osr_key.sql
-- Восстанавливает привязку вопросов к шкалам ОСР (question_scale_mapping)
-- после пересохранения методики в редакторе, и пересчитывает результаты,
-- посчитанные с пустым ключом.
--
-- Источник ключа: последняя неактивная версия шкал, у которой привязки есть.
-- Связь старой и новой версии: одинаковый scale_code (SCALE_1..SCALE_9)
-- и одинаковый номер вопроса (order_index).
-- Всё в одной транзакции; при любой проверке, не прошедшей успешно, база не меняется.
-- ============================================================================

BEGIN;

CREATE TEMP TABLE osr_key ON COMMIT DROP AS
WITH t AS (
    SELECT id FROM psychology.psychological_tests WHERE test_code = 'AI_PDF_7D9D'
),
src_version AS (           -- момент создания последней версии шкал с непустым ключом
    SELECT max(s.created_at) AS ts
    FROM psychology.test_scales s
    WHERE s.test_id = (SELECT id FROM t)
      AND NOT s.is_active
      AND EXISTS (SELECT 1 FROM psychology.question_scale_mapping m WHERE m.scale_id = s.id)
)
SELECT DISTINCT s.scale_code, q.order_index
FROM psychology.test_scales s
JOIN psychology.question_scale_mapping m ON m.scale_id = s.id
JOIN psychology.test_questions q ON q.id = m.question_id
WHERE s.test_id = (SELECT id FROM t)
  AND NOT s.is_active
  AND s.created_at = (SELECT ts FROM src_version);

DO $$
DECLARE n int;
BEGIN
    SELECT count(*) INTO n FROM osr_key;
    IF n <> 40 THEN
        RAISE EXCEPTION 'Ожидалось 40 привязок в старой версии ключа, найдено %. Ничего не изменено.', n;
    END IF;
END $$;

-- Привязываем активные шкалы к активным вопросам по тому же ключу
INSERT INTO psychology.question_scale_mapping (question_id, scale_id, weight)
SELECT q.id, s.id, 1.0
FROM osr_key k
JOIN psychology.test_scales s
     ON s.scale_code = k.scale_code AND s.is_active
    AND s.test_id = (SELECT id FROM psychology.psychological_tests WHERE test_code = 'AI_PDF_7D9D')
JOIN psychology.test_questions q
     ON q.order_index = k.order_index AND q.is_active
    AND q.test_id = s.test_id
ON CONFLICT (question_id, scale_id) DO NOTHING;

DO $$
DECLARE n int;
BEGIN
    SELECT count(*) INTO n
    FROM psychology.question_scale_mapping m
    JOIN psychology.test_scales s ON s.id = m.scale_id AND s.is_active
    JOIN psychology.test_questions q ON q.id = m.question_id AND q.is_active
    WHERE s.test_id = (SELECT id FROM psychology.psychological_tests WHERE test_code = 'AI_PDF_7D9D');
    IF n <> 40 THEN
        RAISE EXCEPTION 'После восстановления у активной версии % привязок вместо 40. Ничего не изменено.', n;
    END IF;
END $$;

-- Пересчитываем сессии, которые прошли по активной версии вопросов
-- (именно их посчитали с пустым ключом)
SELECT psychology.calculate_osr_session(sess.id)
FROM psychology.test_sessions sess
WHERE sess.status = 'completed'
  AND sess.test_id = (SELECT id FROM psychology.psychological_tests WHERE test_code = 'AI_PDF_7D9D')
  AND EXISTS (
      SELECT 1 FROM psychology.answers a
      JOIN psychology.test_questions q ON q.id = a.question_id AND q.is_active
      WHERE a.session_id = sess.id
  );

COMMIT;

-- Контроль 1: по сколько вопросов у каждой активной шкалы (ожидается 5,6,5,5,6,3,2,6,2)
SELECT s.scale_code, s.scale_name,
       string_agg(q.order_index::text, ',' ORDER BY q.order_index) AS "номера вопросов"
FROM psychology.test_scales s
JOIN psychology.question_scale_mapping m ON m.scale_id = s.id
JOIN psychology.test_questions q ON q.id = m.question_id AND q.is_active
WHERE s.is_active
  AND s.test_id = (SELECT id FROM psychology.psychological_tests WHERE test_code = 'AI_PDF_7D9D')
GROUP BY s.scale_code, s.scale_name
ORDER BY s.scale_code;

-- Контроль 2: пересчитанные результаты
SELECT sess.id AS session_id, r.overall_risk_score, r.overall_risk_level, r.summary
FROM psychology.test_results r
JOIN psychology.test_sessions sess ON sess.id = r.session_id
JOIN psychology.answers a ON a.session_id = sess.id
JOIN psychology.test_questions q ON q.id = a.question_id AND q.is_active
WHERE sess.test_id = (SELECT id FROM psychology.psychological_tests WHERE test_code = 'AI_PDF_7D9D')
GROUP BY sess.id, r.overall_risk_score, r.overall_risk_level, r.summary;
