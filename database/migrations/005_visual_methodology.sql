\encoding UTF8

BEGIN;

ALTER TABLE psychology.test_questions
    DROP CONSTRAINT IF EXISTS uq_test_question_order;

CREATE UNIQUE INDEX IF NOT EXISTS uq_test_question_active_order
    ON psychology.test_questions (test_id, order_index)
    WHERE is_active = TRUE;

CREATE TABLE IF NOT EXISTS psychology.test_question_media (
    id uuid DEFAULT gen_random_uuid() NOT NULL PRIMARY KEY,
    question_id uuid NOT NULL
        REFERENCES psychology.test_questions(id) ON DELETE CASCADE,
    media_key character varying(100) NOT NULL,
    media_role character varying(20) NOT NULL
        CHECK (media_role IN ('prompt', 'option')),
    option_id character varying(100),
    file_name text NOT NULL,
    mime_type character varying(100) NOT NULL
        CHECK (mime_type IN ('image/png', 'image/jpeg')),
    file_data bytea NOT NULL
        CHECK (octet_length(file_data) > 0),
    created_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    CONSTRAINT uq_test_question_media_key UNIQUE (question_id, media_key),
    CONSTRAINT check_test_question_media_role_option CHECK (
        (media_role = 'prompt' AND option_id IS NULL)
        OR (media_role = 'option' AND option_id IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_test_question_media_question_id
    ON psychology.test_question_media (question_id);

GRANT ALL ON TABLE psychology.test_question_media TO school_psych_app;

ALTER TABLE psychology.test_sessions
    ADD COLUMN IF NOT EXISTS methodology_config jsonb NOT NULL DEFAULT '{}'::jsonb;

UPDATE psychology.test_sessions s
SET methodology_config = COALESCE(t.config, '{}'::jsonb)
    || jsonb_build_object(
        'test_mode',
        COALESCE(t.config->>'test_mode', 'yes_no')
    )
FROM psychology.psychological_tests t
WHERE t.id = s.test_id
  AND NOT (s.methodology_config ? 'test_mode');

CREATE OR REPLACE FUNCTION psychology.calculate_osr_session(p_session_id uuid)
RETURNS void
LANGUAGE plpgsql
AS $$
DECLARE
    v_total_risk_score NUMERIC := 0;
    v_anti_suicide_score NUMERIC := 0;
    v_overall_level VARCHAR(50) := 'Низкий';
    v_student_code VARCHAR(50);
    rec RECORD;
BEGIN
    DELETE FROM psychology.scale_results WHERE session_id = p_session_id;

    FOR rec IN
        SELECT
            s.id AS scale_id,
            s.scale_code,
            s.scale_name,
            s.coefficient,
            s.max_score,
            COALESCE(SUM(
                CASE
                    WHEN (a.answer_data->>'value')::numeric = 1 THEN qsm.weight
                    ELSE 0
                END
            ), 0) * s.coefficient AS calculated_raw_score
        FROM psychology.test_scales s
        JOIN psychology.question_scale_mapping qsm ON qsm.scale_id = s.id
        JOIN psychology.test_questions q ON q.id = qsm.question_id
        LEFT JOIN psychology.answers a
            ON a.question_id = q.id AND a.session_id = p_session_id
        WHERE s.test_id = (
            SELECT test_id
            FROM psychology.test_sessions
            WHERE id = p_session_id
        )
          AND s.is_active = TRUE
          AND q.is_active = TRUE
        GROUP BY s.id, s.scale_code, s.scale_name, s.coefficient, s.max_score
    LOOP
        INSERT INTO psychology.scale_results (
            session_id, scale_id, raw_score, risk_level, interpretation
        )
        VALUES (
            p_session_id,
            rec.scale_id,
            rec.calculated_raw_score,
            CASE
                WHEN rec.scale_code = 'SCALE_9' THEN
                    CASE
                        WHEN rec.calculated_raw_score >= 3.2 THEN 'Высокая защита'
                        ELSE 'Слабая защита'
                    END
                ELSE
                    CASE
                        WHEN rec.calculated_raw_score >= (rec.max_score * 0.6)
                            THEN 'Высокий'
                        ELSE 'Норма'
                    END
            END,
            'Расчетный балл: ' || rec.calculated_raw_score || ' из ' || rec.max_score
        );

        IF rec.scale_code = 'SCALE_9' THEN
            v_anti_suicide_score := rec.calculated_raw_score;
        ELSE
            v_total_risk_score := v_total_risk_score + rec.calculated_raw_score;
        END IF;
    END LOOP;

    IF v_total_risk_score >= 25.0 AND v_anti_suicide_score < 3.2 THEN
        v_overall_level := 'Высокий (Критический)';
    ELSIF v_total_risk_score >= 15.0 THEN
        v_overall_level := 'Средний (Внимание)';
    ELSE
        v_overall_level := 'Низкий';
    END IF;

    INSERT INTO psychology.test_results (
        session_id, overall_risk_level, overall_risk_score, summary
    )
    VALUES (
        p_session_id,
        v_overall_level,
        ROUND(v_total_risk_score),
        'Индекс суицидального риска: ' || ROUND(v_total_risk_score, 1)
        || '. Антисуицидальный барьер: ' || v_anti_suicide_score
    )
    ON CONFLICT (session_id) DO UPDATE
    SET overall_risk_level = EXCLUDED.overall_risk_level,
        overall_risk_score = EXCLUDED.overall_risk_score,
        summary = EXCLUDED.summary;

    IF v_overall_level = 'Высокий (Критический)' THEN
        SELECT s.student_code INTO v_student_code
        FROM psychology.students s
        JOIN psychology.test_sessions ts ON ts.student_id = s.id
        WHERE ts.id = p_session_id;

        INSERT INTO psychology.notifications (
            user_id, title, message, notification_type
        )
        SELECT
            u.id,
            '🔴 КРИТИЧЕСКИЙ СУИЦИДАЛЬНЫЙ РИСК',
            'Учащийся с кодом [' || v_student_code
            || '] набрал критический балл при слабой защите. Требуется очная беседа.',
            'error'::psychology.notification_type
        FROM psychology.users u
        WHERE u.role IN ('psychologist', 'admin')
          AND u.is_active = TRUE
          AND NOT EXISTS (
              SELECT 1
              FROM psychology.notifications n
              WHERE n.user_id = u.id
                AND n.title = '🔴 КРИТИЧЕСКИЙ СУИЦИДАЛЬНЫЙ РИСК'
                AND n.created_at > CURRENT_TIMESTAMP - interval '10 minutes'
          );
    END IF;
END;
$$;

GRANT ALL ON FUNCTION psychology.calculate_osr_session(uuid) TO school_psych_app;

COMMIT;
