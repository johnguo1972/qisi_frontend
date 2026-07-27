-- ============================================
-- appdb 数据库备份（表结构 + 数据）
-- 备份时间: 2026-07-23 19:11:59.456601
-- 表数量: 40
-- ============================================


-- ----------------------------
-- Table: ai_guidance_session
-- ----------------------------
CREATE TABLE "ai_guidance_session" (    "id" bigint NOT NULL,
    "question_id" integer NOT NULL,
    "mode_type" varchar(10) NOT NULL,
    "session_status" varchar(20) NOT NULL,
    "invalid_input_count" integer NOT NULL,
    "script_source" varchar(20) NOT NULL,
    "content_log_json" jsonb NOT NULL,
    "created_at" timestamptz NOT NULL,
    "updated_at" timestamptz NOT NULL,
    "student_user_id_id" bigint NOT NULL);

ALTER TABLE "ai_guidance_session" ADD PRIMARY KEY ("id");


-- ----------------------------
-- Table: answer_attempt
-- ----------------------------
CREATE TABLE "answer_attempt" (    "id" bigint NOT NULL,
    "question_id" integer NOT NULL,
    "attempt_no" integer NOT NULL,
    "answer_content" jsonb NOT NULL,
    "is_correct" boolean NOT NULL,
    "score" numeric(5,2) NOT NULL,
    "submit_source" varchar(20) NOT NULL,
    "submitted_at" timestamptz NOT NULL,
    "level_id" bigint,
    "mission_id" bigint,
    "student_user_id_id" bigint NOT NULL,
    "is_subjective_pending" boolean NOT NULL);

ALTER TABLE "answer_attempt" ADD PRIMARY KEY ("id");


-- ----------------------------
-- Table: auth_group
-- ----------------------------
CREATE TABLE "auth_group" (    "id" integer NOT NULL,
    "name" varchar(150) NOT NULL);

ALTER TABLE "auth_group" ADD PRIMARY KEY ("id");


-- ----------------------------
-- Table: auth_group_permissions
-- ----------------------------
CREATE TABLE "auth_group_permissions" (    "id" bigint NOT NULL,
    "group_id" integer NOT NULL,
    "permission_id" integer NOT NULL);

ALTER TABLE "auth_group_permissions" ADD PRIMARY KEY ("id");


-- ----------------------------
-- Table: auth_permission
-- ----------------------------
CREATE TABLE "auth_permission" (    "id" integer NOT NULL,
    "name" varchar(255) NOT NULL,
    "content_type_id" integer NOT NULL,
    "codename" varchar(100) NOT NULL);

ALTER TABLE "auth_permission" ADD PRIMARY KEY ("id");


-- ----------------------------
-- Table: class
-- ----------------------------
CREATE TABLE "class" (    "id" bigint NOT NULL,
    "class_no" varchar(20) NOT NULL,
    "class_name" varchar(200) NOT NULL,
    "description" text,
    "max_students" integer NOT NULL,
    "invite_code" varchar(8) NOT NULL,
    "allow_invite_join" boolean NOT NULL,
    "status" varchar(20) NOT NULL,
    "created_at" timestamptz NOT NULL,
    "updated_at" timestamptz NOT NULL,
    "creator_teacher_id" bigint,
    "institution_id" bigint NOT NULL);

ALTER TABLE "class" ADD PRIMARY KEY ("id");


-- ----------------------------
-- Table: class_join_request
-- ----------------------------
CREATE TABLE "class_join_request" (    "id" bigint NOT NULL,
    "applicant_name" varchar(100) NOT NULL,
    "applicant_phone" varchar(20),
    "request_type" varchar(20) NOT NULL,
    "status" varchar(20) NOT NULL,
    "message" text,
    "handled_at" timestamptz,
    "created_at" timestamptz NOT NULL,
    "applicant_id" bigint NOT NULL,
    "class_id" bigint NOT NULL,
    "handled_by_id" bigint);

ALTER TABLE "class_join_request" ADD PRIMARY KEY ("id");


-- ----------------------------
-- Table: class_student
-- ----------------------------
CREATE TABLE "class_student" (    "id" bigint NOT NULL,
    "join_type" varchar(20) NOT NULL,
    "status" varchar(20) NOT NULL,
    "joined_at" timestamptz NOT NULL,
    "class_id" bigint NOT NULL,
    "student_id" bigint NOT NULL);

ALTER TABLE "class_student" ADD PRIMARY KEY ("id");


-- ----------------------------
-- Table: class_teacher
-- ----------------------------
CREATE TABLE "class_teacher" (    "id" bigint NOT NULL,
    "role" varchar(20) NOT NULL,
    "class_id" bigint NOT NULL,
    "teacher_id" bigint NOT NULL);

ALTER TABLE "class_teacher" ADD PRIMARY KEY ("id");


-- ----------------------------
-- Table: course
-- ----------------------------
CREATE TABLE "course" (    "id" bigint NOT NULL,
    "name" varchar(200) NOT NULL,
    "description" text,
    "subject" varchar(50) NOT NULL,
    "grade_level" varchar(50) NOT NULL,
    "cover_image" varchar(500),
    "is_deleted" boolean NOT NULL,
    "created_at" timestamptz NOT NULL,
    "updated_at" timestamptz NOT NULL,
    "teacher_id" bigint NOT NULL);

ALTER TABLE "course" ADD PRIMARY KEY ("id");


-- ----------------------------
-- Table: course_material
-- ----------------------------
CREATE TABLE "course_material" (    "id" bigint NOT NULL,
    "name" varchar(255) NOT NULL,
    "file_path" varchar(500) NOT NULL,
    "file_type" varchar(20) NOT NULL,
    "file_size" bigint NOT NULL,
    "mime_type" varchar(100) NOT NULL,
    "is_deleted" boolean NOT NULL,
    "created_at" timestamptz NOT NULL,
    "course_id" bigint NOT NULL,
    "uploaded_by_id" bigint);

ALTER TABLE "course_material" ADD PRIMARY KEY ("id");


-- ----------------------------
-- Table: course_question_link
-- ----------------------------
CREATE TABLE "course_question_link" (    "id" bigint NOT NULL,
    "source" varchar(30) NOT NULL,
    "source_course_name" varchar(200),
    "is_deleted" boolean NOT NULL,
    "created_at" timestamptz NOT NULL,
    "course_id" bigint NOT NULL,
    "question_id" bigint NOT NULL,
    "tree_node_id" bigint);

ALTER TABLE "course_question_link" ADD PRIMARY KEY ("id");


-- ----------------------------
-- Table: course_tree
-- ----------------------------
CREATE TABLE "course_tree" (    "id" bigint NOT NULL,
    "name" varchar(200) NOT NULL,
    "sort_order" integer NOT NULL,
    "created_at" timestamptz NOT NULL,
    "course_id" bigint NOT NULL,
    "parent_id" bigint);

ALTER TABLE "course_tree" ADD PRIMARY KEY ("id");


-- ----------------------------
-- Table: course_variant_task
-- ----------------------------
CREATE TABLE "course_variant_task" (    "id" bigint NOT NULL,
    "variant_mode" varchar(30) NOT NULL,
    "status" varchar(20) NOT NULL,
    "generator_result" jsonb,
    "verifier_result" jsonb,
    "generated_question" jsonb,
    "error_message" text,
    "created_at" timestamptz NOT NULL,
    "completed_at" timestamptz,
    "original_question_id" bigint NOT NULL);

ALTER TABLE "course_variant_task" ADD PRIMARY KEY ("id");


-- ----------------------------
-- Table: django_admin_log
-- ----------------------------
CREATE TABLE "django_admin_log" (    "id" integer NOT NULL,
    "action_time" timestamptz NOT NULL,
    "object_id" text,
    "object_repr" varchar(200) NOT NULL,
    "action_flag" smallint NOT NULL,
    "change_message" text NOT NULL,
    "content_type_id" integer,
    "user_id" bigint NOT NULL);

ALTER TABLE "django_admin_log" ADD PRIMARY KEY ("id");


-- ----------------------------
-- Table: django_content_type
-- ----------------------------
CREATE TABLE "django_content_type" (    "id" integer NOT NULL,
    "app_label" varchar(100) NOT NULL,
    "model" varchar(100) NOT NULL);

ALTER TABLE "django_content_type" ADD PRIMARY KEY ("id");


-- ----------------------------
-- Table: django_migrations
-- ----------------------------
CREATE TABLE "django_migrations" (    "id" bigint NOT NULL,
    "app" varchar(255) NOT NULL,
    "name" varchar(255) NOT NULL,
    "applied" timestamptz NOT NULL);

ALTER TABLE "django_migrations" ADD PRIMARY KEY ("id");


-- ----------------------------
-- Table: django_session
-- ----------------------------
CREATE TABLE "django_session" (    "session_key" varchar(40) NOT NULL,
    "session_data" text NOT NULL,
    "expire_date" timestamptz NOT NULL);

ALTER TABLE "django_session" ADD PRIMARY KEY ("session_key");


-- ----------------------------
-- Table: institution
-- ----------------------------
CREATE TABLE "institution" (    "id" bigint NOT NULL,
    "institution_name" varchar(200) NOT NULL,
    "contact_name" varchar(100),
    "contact_phone" varchar(20),
    "contact_email" varchar(200),
    "address" varchar(500),
    "status" varchar(20) NOT NULL,
    "created_at" timestamptz NOT NULL,
    "updated_at" timestamptz NOT NULL,
    "created_by_id" bigint);

ALTER TABLE "institution" ADD PRIMARY KEY ("id");


-- ----------------------------
-- Table: institution_member
-- ----------------------------
CREATE TABLE "institution_member" (    "id" bigint NOT NULL,
    "role" varchar(20) NOT NULL,
    "status" varchar(20) NOT NULL,
    "joined_at" timestamptz NOT NULL,
    "institution_id" bigint NOT NULL,
    "user_id" bigint NOT NULL);

ALTER TABLE "institution_member" ADD PRIMARY KEY ("id");


-- ----------------------------
-- Table: knowledge_points
-- ----------------------------
CREATE TABLE "knowledge_points" (    "id" bigint NOT NULL DEFAULT nextval('knowledge_points_id_seq'::regclass),
    "subject" varchar(50) NOT NULL,
    "stage" varchar(20) NOT NULL,
    "grade_index" smallint NOT NULL,
    "grade_name" varchar(20) NOT NULL,
    "term" varchar(10) NOT NULL,
    "chapter" varchar(255) NOT NULL,
    "module" varchar(255) NOT NULL,
    "node_type" varchar(20) NOT NULL,
    "content" text NOT NULL,
    "created_at" timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP);

ALTER TABLE "knowledge_points" ADD PRIMARY KEY ("id");


-- ----------------------------
-- Table: learning_mission
-- ----------------------------
CREATE TABLE "learning_mission" (    "id" bigint NOT NULL,
    "mission_no" varchar(32) NOT NULL,
    "mission_name" varchar(120) NOT NULL,
    "goal_text" varchar(255) NOT NULL,
    "start_at" timestamptz,
    "end_at" timestamptz,
    "status" varchar(20) NOT NULL,
    "default_mode_policy" varchar(50),
    "created_at" timestamptz NOT NULL,
    "updated_at" timestamptz NOT NULL,
    "creator_teacher_id_id" bigint NOT NULL,
    "class_id" bigint);

ALTER TABLE "learning_mission" ADD PRIMARY KEY ("id");


-- ----------------------------
-- Table: mastery_record
-- ----------------------------
CREATE TABLE "mastery_record" (    "id" bigint NOT NULL,
    "mastery_type" varchar(20) NOT NULL,
    "target_code" varchar(64) NOT NULL,
    "mastery_status" varchar(20) NOT NULL,
    "mastery_score" numeric(5,2) NOT NULL,
    "next_review_at" timestamptz,
    "updated_at" timestamptz NOT NULL,
    "student_user_id_id" bigint NOT NULL);

ALTER TABLE "mastery_record" ADD PRIMARY KEY ("id");


-- ----------------------------
-- Table: mission_level
-- ----------------------------
CREATE TABLE "mission_level" (    "id" bigint NOT NULL,
    "level_no" integer NOT NULL,
    "level_name" varchar(100) NOT NULL,
    "level_type" varchar(30) NOT NULL,
    "pass_rule_json" jsonb NOT NULL,
    "mode_policy" varchar(50),
    "hint_strength" varchar(20) NOT NULL,
    "mission_id" bigint NOT NULL);

ALTER TABLE "mission_level" ADD PRIMARY KEY ("id");


-- ----------------------------
-- Table: mission_question_rel
-- ----------------------------
CREATE TABLE "mission_question_rel" (    "id" bigint NOT NULL,
    "question_id" integer NOT NULL,
    "sort_no" integer NOT NULL,
    "is_required" boolean NOT NULL,
    "source_type" varchar(20) NOT NULL,
    "level_id" bigint NOT NULL,
    "mission_id" bigint NOT NULL);

ALTER TABLE "mission_question_rel" ADD PRIMARY KEY ("id");


-- ----------------------------
-- Table: student_level_progress
-- ----------------------------
CREATE TABLE "student_level_progress" (    "id" bigint NOT NULL,
    "status" varchar(20) NOT NULL,
    "pass_score" numeric(5,2) NOT NULL,
    "attempt_count" integer NOT NULL,
    "passed_at" timestamptz,
    "level_id" bigint NOT NULL,
    "student_user_id_id" bigint NOT NULL);

ALTER TABLE "student_level_progress" ADD PRIMARY KEY ("id");


-- ----------------------------
-- Table: student_mission_progress
-- ----------------------------
CREATE TABLE "student_mission_progress" (    "id" bigint NOT NULL,
    "progress_status" varchar(20) NOT NULL,
    "progress_percent" numeric(5,2) NOT NULL,
    "last_action_at" timestamptz NOT NULL,
    "current_level_id" bigint,
    "mission_id" bigint NOT NULL,
    "student_user_id_id" bigint NOT NULL);

ALTER TABLE "student_mission_progress" ADD PRIMARY KEY ("id");


-- ----------------------------
-- Table: student_parent_bind
-- ----------------------------
CREATE TABLE "student_parent_bind" (    "id" bigint NOT NULL,
    "relation_type" varchar(20) NOT NULL,
    "bind_status" varchar(20) NOT NULL,
    "bound_at" timestamptz NOT NULL,
    "parent_user_id_id" bigint NOT NULL,
    "student_user_id_id" bigint NOT NULL);

ALTER TABLE "student_parent_bind" ADD PRIMARY KEY ("id");


-- ----------------------------
-- Table: tiku_ai_parse_result
-- ----------------------------
CREATE TABLE "tiku_ai_parse_result" (    "id" bigint NOT NULL,
    "model_name" varchar(100) NOT NULL,
    "prompt_version" varchar(50),
    "request_json" jsonb,
    "response_json" jsonb,
    "raw_response" text,
    "is_valid_json" boolean NOT NULL,
    "error_message" text,
    "latency_ms" integer,
    "created_at" timestamptz NOT NULL,
    "paper_id" bigint NOT NULL,
    "page_id" bigint);

ALTER TABLE "tiku_ai_parse_result" ADD PRIMARY KEY ("id");


-- ----------------------------
-- Table: tiku_exam_page
-- ----------------------------
CREATE TABLE "tiku_exam_page" (    "id" bigint NOT NULL,
    "page_no" integer NOT NULL,
    "image_path" varchar(500) NOT NULL,
    "width" integer,
    "height" integer,
    "ocr_text" text,
    "layout_json" jsonb,
    "parse_status" varchar(50) NOT NULL,
    "ai_confidence" numeric(5,4),
    "created_at" timestamptz NOT NULL,
    "updated_at" timestamptz NOT NULL,
    "paper_id" bigint NOT NULL);

ALTER TABLE "tiku_exam_page" ADD PRIMARY KEY ("id");


-- ----------------------------
-- Table: tiku_exam_paper
-- ----------------------------
CREATE TABLE "tiku_exam_paper" (    "id" bigint NOT NULL,
    "title" varchar(255) NOT NULL,
    "subject" varchar(50) NOT NULL,
    "stage" varchar(50),
    "grade" varchar(50),
    "paper_type" varchar(50),
    "has_solution" boolean NOT NULL,
    "source_file_path" varchar(500) NOT NULL,
    "pdf_file_path" varchar(500),
    "total_pages" integer NOT NULL,
    "total_questions" integer NOT NULL,
    "status" varchar(50) NOT NULL,
    "error_message" text,
    "created_at" timestamptz NOT NULL,
    "updated_at" timestamptz NOT NULL,
    "paper_code" varchar(20),
    "region" varchar(100),
    "is_deleted" boolean NOT NULL,
    "uploaded_by_id" bigint);

ALTER TABLE "tiku_exam_paper" ADD PRIMARY KEY ("id");


-- ----------------------------
-- Table: tiku_exam_question
-- ----------------------------
CREATE TABLE "tiku_exam_question" (    "id" bigint NOT NULL,
    "question_no" varchar(50) NOT NULL,
    "section_title" varchar(255),
    "question_type" varchar(50) NOT NULL,
    "subject" varchar(50),
    "stem" text NOT NULL,
    "stem_html" text,
    "answer" text,
    "analysis" text,
    "solution" text,
    "comment" text,
    "raw_explanation" text,
    "raw_text" text,
    "knowledge_points" jsonb,
    "difficulty" numeric(4,2),
    "page_start" integer,
    "page_end" integer,
    "bbox" jsonb,
    "region_json" jsonb,
    "sort_order" integer NOT NULL,
    "confidence" numeric(5,4),
    "formula_need_review" boolean NOT NULL,
    "need_review" boolean NOT NULL,
    "review_status" varchar(50) NOT NULL,
    "parse_status" varchar(50) NOT NULL,
    "created_at" timestamptz NOT NULL,
    "updated_at" timestamptz NOT NULL,
    "original_question_id" bigint,
    "paper_id" bigint NOT NULL,
    "parent_question_id" bigint,
    "system_id" varchar(10),
    "paper_question_no" varchar(50),
    "ai_answer_a" jsonb,
    "ai_answer_b" jsonb,
    "ai_answer_c" jsonb,
    "ai_knowledge_enrichment" jsonb,
    "ai_probe_result" jsonb,
    "ai_vision_extract" jsonb,
    "ai_verifier_result" jsonb,
    "ai_processed_at" timestamptz,
    "ai_processing_status" varchar(20) NOT NULL);

ALTER TABLE "tiku_exam_question" ADD PRIMARY KEY ("id");


-- ----------------------------
-- Table: tiku_favorite
-- ----------------------------
CREATE TABLE "tiku_favorite" (    "id" bigint NOT NULL,
    "user_id" bigint NOT NULL,
    "question_id" integer NOT NULL,
    "created_at" timestamptz NOT NULL);

ALTER TABLE "tiku_favorite" ADD PRIMARY KEY ("id");


-- ----------------------------
-- Table: tiku_paper_code_counter
-- ----------------------------
CREATE TABLE "tiku_paper_code_counter" (    "id" bigint NOT NULL,
    "letter" varchar(1) NOT NULL,
    "grade_char" varchar(1) NOT NULL,
    "next_seq" integer NOT NULL);

ALTER TABLE "tiku_paper_code_counter" ADD PRIMARY KEY ("id");


-- ----------------------------
-- Table: tiku_parse_task
-- ----------------------------
CREATE TABLE "tiku_parse_task" (    "id" bigint NOT NULL,
    "task_type" varchar(50) NOT NULL,
    "status" varchar(50) NOT NULL,
    "progress" integer NOT NULL,
    "current_step" varchar(255),
    "error_message" text,
    "retry_count" integer NOT NULL,
    "celery_task_id" varchar(255),
    "started_at" timestamptz,
    "finished_at" timestamptz,
    "created_at" timestamptz NOT NULL,
    "updated_at" timestamptz NOT NULL,
    "paper_id" bigint NOT NULL,
    "question_id" bigint);

ALTER TABLE "tiku_parse_task" ADD PRIMARY KEY ("id");


-- ----------------------------
-- Table: tiku_question_id_counter
-- ----------------------------
CREATE TABLE "tiku_question_id_counter" (    "id" bigint NOT NULL,
    "subject" varchar(50) NOT NULL,
    "next_seq" integer NOT NULL);

ALTER TABLE "tiku_question_id_counter" ADD PRIMARY KEY ("id");


-- ----------------------------
-- Table: tiku_question_image
-- ----------------------------
CREATE TABLE "tiku_question_image" (    "id" bigint NOT NULL,
    "image_type" varchar(50) NOT NULL,
    "file_path" varchar(500) NOT NULL,
    "source_page_image_path" varchar(500),
    "bbox" jsonb,
    "expanded_bbox" jsonb,
    "description" varchar(500),
    "sort_order" integer NOT NULL,
    "created_at" timestamptz NOT NULL,
    "page_id" bigint,
    "paper_id" bigint NOT NULL,
    "question_id" bigint NOT NULL);

ALTER TABLE "tiku_question_image" ADD PRIMARY KEY ("id");


-- ----------------------------
-- Table: tiku_question_option
-- ----------------------------
CREATE TABLE "tiku_question_option" (    "id" bigint NOT NULL,
    "option_label" varchar(10) NOT NULL,
    "content" text NOT NULL,
    "content_html" text,
    "bbox" jsonb,
    "sort_order" integer NOT NULL,
    "created_at" timestamptz NOT NULL,
    "updated_at" timestamptz NOT NULL,
    "question_id" bigint NOT NULL);

ALTER TABLE "tiku_question_option" ADD PRIMARY KEY ("id");


-- ----------------------------
-- Table: user_account
-- ----------------------------
CREATE TABLE "user_account" (    "id" bigint NOT NULL,
    "role_type" varchar(20) NOT NULL,
    "login_name" varchar(64),
    "mobile" varchar(20) NOT NULL,
    "display_name" varchar(64) NOT NULL,
    "avatar_url" varchar(255),
    "status" varchar(20) NOT NULL,
    "created_at" timestamptz NOT NULL,
    "updated_at" timestamptz NOT NULL,
    "last_login" timestamptz,
    "password" varchar(128) NOT NULL,
    "subject" varchar(20),
    "stages" jsonb,
    "grade_level" varchar(20));

ALTER TABLE "user_account" ADD PRIMARY KEY ("id");


-- ----------------------------
-- Table: wrong_book_item
-- ----------------------------
CREATE TABLE "wrong_book_item" (    "id" bigint NOT NULL,
    "question_id" integer NOT NULL,
    "first_wrong_at" timestamptz NOT NULL,
    "latest_wrong_at" timestamptz NOT NULL,
    "wrong_reason_type" varchar(30),
    "status" varchar(20) NOT NULL,
    "retry_count" integer NOT NULL,
    "variant_done_count" integer NOT NULL,
    "student_user_id_id" bigint NOT NULL);

ALTER TABLE "wrong_book_item" ADD PRIMARY KEY ("id");


-- ============ 数据记录数统计 ============
-- ai_guidance_session: 0 records
-- answer_attempt: 0 records
-- auth_group: 0 records
-- auth_group_permissions: 0 records
-- auth_permission: 152 records
-- class: 0 records
-- class_join_request: 0 records
-- class_student: 0 records
-- class_teacher: 0 records
-- course: 0 records
-- course_material: 0 records
-- course_question_link: 0 records
-- course_tree: 0 records
-- course_variant_task: 0 records
-- django_admin_log: 0 records
-- django_content_type: 38 records
-- django_migrations: 48 records
-- django_session: 0 records
-- institution: 0 records
-- institution_member: 0 records
-- knowledge_points: 0 records
-- learning_mission: 0 records
-- mastery_record: 0 records
-- mission_level: 0 records
-- mission_question_rel: 0 records
-- student_level_progress: 0 records
-- student_mission_progress: 0 records
-- student_parent_bind: 0 records
-- tiku_ai_parse_result: 0 records
-- tiku_exam_page: 0 records
-- tiku_exam_paper: 0 records
-- tiku_exam_question: 0 records
-- tiku_favorite: 0 records
-- tiku_paper_code_counter: 0 records
-- tiku_parse_task: 0 records
-- tiku_question_id_counter: 0 records
-- tiku_question_image: 0 records
-- tiku_question_option: 0 records
-- user_account: 0 records
-- wrong_book_item: 0 records
-- 总记录数: 238
