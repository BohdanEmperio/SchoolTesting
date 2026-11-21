\encoding UTF8
\set ON_ERROR_STOP on

-- ============================================================================
-- 006_protect_results.sql
-- Применять ПОСЛЕ 005_visual_methodology.sql.
-- Всё выполняется в одной транзакции: при любой ошибке база не меняется.
--
-- Что делает:
--   1. Проверяет, что миграция 005 уже применена.
--   2. Запрещает каскадное удаление результатов при удалении ученика,
--      методики, вопроса или шкалы (CASCADE -> RESTRICT).
--   3. Удаляет индексы, которые дублируют уникальные ограничения.
--   4. Приводит названия классов к виду "7А" (цифра + буква из поля letter).
--   5. Пересчитывает psychological_tests.questions_count.
-- ============================================================================

BEGIN;

-- 1. Проверка: миграция 005 должна быть применена ----------------------------
DO $$
BEGIN
    IF to_regclass('psychology.test_question_media') IS NULL THEN
        RAISE EXCEPTION 'Сначала примените 005_visual_methodology.sql: нет таблицы test_question_media';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'psychology'
          AND table_name = 'test_sessions'
          AND column_name = 'methodology_config'
    ) THEN
        RAISE EXCEPTION 'Сначала примените 005_visual_methodology.sql: нет колонки test_sessions.methodology_config';
    END IF;
END $$;

-- 2. Защита результатов от каскадного удаления ------------------------------
-- Удаление ученика больше не уничтожает его сессии, ответы и протоколы.
ALTER TABLE psychology.test_sessions
    DROP CONSTRAINT IF EXISTS test_sessions_student_id_fkey,
    ADD  CONSTRAINT test_sessions_student_id_fkey
         FOREIGN KEY (student_id) REFERENCES psychology.students(id) ON DELETE RESTRICT;

-- Удаление методики больше не уничтожает сессии по ней.
ALTER TABLE psychology.test_sessions
    DROP CONSTRAINT IF EXISTS test_sessions_test_id_fkey,
    ADD  CONSTRAINT test_sessions_test_id_fkey
         FOREIGN KEY (test_id) REFERENCES psychology.psychological_tests(id) ON DELETE RESTRICT;

-- Удаление вопроса больше не стирает ответы на него.
ALTER TABLE psychology.answers
    DROP CONSTRAINT IF EXISTS answers_question_id_fkey,
    ADD  CONSTRAINT answers_question_id_fkey
         FOREIGN KEY (question_id) REFERENCES psychology.test_questions(id) ON DELETE RESTRICT;

-- Удаление шкалы больше не стирает рассчитанные баллы по ней.
ALTER TABLE psychology.scale_results
    DROP CONSTRAINT IF EXISTS scale_results_scale_id_fkey,
    ADD  CONSTRAINT scale_results_scale_id_fkey
         FOREIGN KEY (scale_id) REFERENCES psychology.test_scales(id) ON DELETE RESTRICT;

-- Связи сессия -> ответы/результаты/протоколы остаются CASCADE:
-- если сессию удалили сознательно, её содержимое удаляется вместе с ней.

-- 3. Лишние индексы (их работу уже выполняют уникальные ограничения) --------
DROP INDEX IF EXISTS psychology.idx_students_code;       -- = students_student_code_key
DROP INDEX IF EXISTS psychology.idx_qsm_question;        -- = question_scale_mapping_question_id_scale_id_key
DROP INDEX IF EXISTS psychology.idx_answers_session_id;  -- = uq_session_question

-- 4. Названия классов: "7a" (латиница) -> "7А" ------------------------------
UPDATE psychology.classes
SET class_name = grade_level::text || upper(letter)
WHERE letter IS NOT NULL
  AND class_name IS DISTINCT FROM grade_level::text || upper(letter);

-- 5. Актуальное число активных вопросов ------------------------------------
UPDATE psychology.psychological_tests t
SET questions_count = (
    SELECT count(*) FROM psychology.test_questions q
    WHERE q.test_id = t.id AND q.is_active = TRUE
)
WHERE questions_count IS DISTINCT FROM (
    SELECT count(*) FROM psychology.test_questions q
    WHERE q.test_id = t.id AND q.is_active = TRUE
);

COMMIT;

-- Контроль: правила удаления внешних ключей (r = RESTRICT, c = CASCADE, n = SET NULL)
SELECT conrelid::regclass AS "таблица", conname AS "ограничение", confdeltype AS "при удалении"
FROM pg_constraint
WHERE contype = 'f' AND connamespace = 'psychology'::regnamespace
ORDER BY 1, 2;
