-- ============================================
-- 19张缺失表迁移 SQL（仅表结构，不含数据）
-- 使用括号配对法精确提取
-- 可直接在服务器执行（PostgreSQL）
-- ============================================

-- =============================
-- Part 0: 创建扩展（uuid-ossp 用于 test_connection 表）
-- =============================
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =============================
-- Part 1: 创建序列 (SEQUENCE)
-- =============================
-- Sequence: alert_logs_id_seq
CREATE SEQUENCE "public"."alert_logs_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- Sequence: api_task_logs_id_seq
CREATE SEQUENCE "public"."api_task_logs_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- Sequence: dlq_messages_id_seq
CREATE SEQUENCE "public"."dlq_messages_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- Sequence: gemini_results_id_seq
CREATE SEQUENCE "public"."gemini_results_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 2147483647
START 1
CACHE 1;

-- Sequence: llm_audit_id_seq
CREATE SEQUENCE "public"."llm_audit_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- Sequence: monitoring_metrics_id_seq
CREATE SEQUENCE "public"."monitoring_metrics_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- Sequence: problem_results_id_seq
CREATE SEQUENCE "public"."problem_results_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- Sequence: problems_id_seq
CREATE SEQUENCE "public"."problems_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- Sequence: retry_queue_id_seq
CREATE SEQUENCE "public"."retry_queue_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- Sequence: rollback_logs_id_seq
CREATE SEQUENCE "public"."rollback_logs_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- Sequence: system_config_id_seq
CREATE SEQUENCE "public"."system_config_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 2147483647
START 1
CACHE 1;

-- Sequence: task_outbox_id_seq
CREATE SEQUENCE "public"."task_outbox_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- Sequence: users_id_seq
CREATE SEQUENCE "public"."users_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- 共 13 个序列

-- =============================
-- Part 2: 创建表 (CREATE TABLE)
-- =============================
-- Table: alert_logs
CREATE TABLE "public"."alert_logs" (
  "id" int8 NOT NULL DEFAULT nextval('alert_logs_id_seq'::regclass),
  "level" varchar(20) COLLATE "pg_catalog"."default" NOT NULL,
  "title" varchar(200) COLLATE "pg_catalog"."default" NOT NULL,
  "message" text COLLATE "pg_catalog"."default",
  "action" varchar(500) COLLATE "pg_catalog"."default",
  "channels" varchar(200) COLLATE "pg_catalog"."default",
  "sent_at" timestamp(6) DEFAULT CURRENT_TIMESTAMP,
  "ack_at" timestamp(6)
)
;

-- Table: api_task_logs
CREATE TABLE "public"."api_task_logs" (
  "id" int8 NOT NULL DEFAULT nextval('api_task_logs_id_seq'::regclass),
  "task_id" varchar(32) COLLATE "pg_catalog"."default" NOT NULL,
  "trace_id" varchar(64) COLLATE "pg_catalog"."default",
  "problem_id" int8 NOT NULL,
  "user_id" int8 NOT NULL,
  "mode" varchar(20) COLLATE "pg_catalog"."default" NOT NULL,
  "route_name" varchar(50) COLLATE "pg_catalog"."default",
  "status" varchar(20) COLLATE "pg_catalog"."default" NOT NULL DEFAULT 'PENDING'::character varying,
  "retry_count" int2 DEFAULT 0,
  "max_retries" int2 DEFAULT 3,
  "next_retry_at" timestamp(6),
  "image_url" varchar(500) COLLATE "pg_catalog"."default" NOT NULL,
  "ali_ocr_text" text COLLATE "pg_catalog"."default",
  "normalized_text" text COLLATE "pg_catalog"."default",
  "normalized_text_hash" varchar(64) COLLATE "pg_catalog"."default",
  "difficulty_flag" int2 DEFAULT 0,
  "request_json" text COLLATE "pg_catalog"."default",
  "vision_extract_json" jsonb,
  "solver_output_json" jsonb,
  "verifier_output_json" jsonb,
  "result_json" text COLLATE "pg_catalog"."default",
  "error_code" varchar(50) COLLATE "pg_catalog"."default",
  "last_error_code" varchar(50) COLLATE "pg_catalog"."default",
  "error_classification" varchar(50) COLLATE "pg_catalog"."default",
  "retry_history" jsonb,
  "error_msg" text COLLATE "pg_catalog"."default",
  "poll_count" int4 DEFAULT 0,
  "started_at" timestamp(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "finished_at" timestamp(6),
  "created_at" timestamp(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" timestamp(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "task_type" varchar(100) COLLATE "pg_catalog"."default",
  "processing_time_ms" int4 DEFAULT 0,
  "progress" int4 DEFAULT 0,
  "request_payload" text COLLATE "pg_catalog"."default",
  "response_payload" text COLLATE "pg_catalog"."default",
  "prompt_version" varchar(20) COLLATE "pg_catalog"."default" DEFAULT 'v2.0'::character varying,
  "route_version" varchar(20) COLLATE "pg_catalog"."default" DEFAULT 'v2.0'::character varying
)
;

-- Table: auth_user
CREATE TABLE "public"."auth_user" (
  "id" int4 NOT NULL GENERATED BY DEFAULT AS IDENTITY (
INCREMENT 1
MINVALUE  1
MAXVALUE 2147483647
START 1
CACHE 1
),
  "password" varchar(128) COLLATE "pg_catalog"."default" NOT NULL,
  "last_login" timestamptz(6),
  "is_superuser" bool NOT NULL,
  "username" varchar(150) COLLATE "pg_catalog"."default" NOT NULL,
  "first_name" varchar(150) COLLATE "pg_catalog"."default" NOT NULL,
  "last_name" varchar(150) COLLATE "pg_catalog"."default" NOT NULL,
  "email" varchar(254) COLLATE "pg_catalog"."default" NOT NULL,
  "is_staff" bool NOT NULL,
  "is_active" bool NOT NULL,
  "date_joined" timestamptz(6) NOT NULL
)
;

-- Table: auth_user_groups
CREATE TABLE "public"."auth_user_groups" (
  "id" int8 NOT NULL GENERATED BY DEFAULT AS IDENTITY (
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1
),
  "user_id" int4 NOT NULL,
  "group_id" int4 NOT NULL
)
;

-- Table: auth_user_user_permissions
CREATE TABLE "public"."auth_user_user_permissions" (
  "id" int8 NOT NULL GENERATED BY DEFAULT AS IDENTITY (
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1
),
  "user_id" int4 NOT NULL,
  "permission_id" int4 NOT NULL
)
;

-- Table: dlq_messages
CREATE TABLE "public"."dlq_messages" (
  "id" int8 NOT NULL DEFAULT nextval('dlq_messages_id_seq'::regclass),
  "task_id" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "request_key" varchar(64) COLLATE "pg_catalog"."default",
  "problem_id" int4,
  "user_id" varchar(50) COLLATE "pg_catalog"."default",
  "mode" varchar(20) COLLATE "pg_catalog"."default",
  "image_url" varchar(500) COLLATE "pg_catalog"."default",
  "ocr_text" text COLLATE "pg_catalog"."default",
  "error_code" varchar(50) COLLATE "pg_catalog"."default",
  "error_message" text COLLATE "pg_catalog"."default",
  "retry_count" int4 DEFAULT 5,
  "last_error_at" timestamp(6),
  "original_message" text COLLATE "pg_catalog"."default",
  "status" varchar(20) COLLATE "pg_catalog"."default" DEFAULT 'PENDING'::character varying,
  "handled_by" varchar(100) COLLATE "pg_catalog"."default",
  "resolution_note" text COLLATE "pg_catalog"."default",
  "entered_dlq_at" timestamp(6) DEFAULT CURRENT_TIMESTAMP,
  "handled_at" timestamp(6)
)
;

-- Table: gemini_results
CREATE TABLE "public"."gemini_results" (
  "id" int4 NOT NULL DEFAULT nextval('gemini_results_id_seq'::regclass),
  "task_id" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "task_type" varchar(10) COLLATE "pg_catalog"."default" NOT NULL,
  "user_id" int4,
  "image_urls" text COLLATE "pg_catalog"."default",
  "result_json" text COLLATE "pg_catalog"."default",
  "processing_time_ms" int4,
  "model_used" varchar(100) COLLATE "pg_catalog"."default",
  "prompt_version" varchar(50) COLLATE "pg_catalog"."default",
  "schema_version" varchar(50) COLLATE "pg_catalog"."default",
  "created_at" timestamp(6) DEFAULT CURRENT_TIMESTAMP,
  "updated_at" timestamp(6) DEFAULT CURRENT_TIMESTAMP
)
;

-- Table: llm_audit
CREATE TABLE "public"."llm_audit" (
  "id" int8 NOT NULL DEFAULT nextval('llm_audit_id_seq'::regclass),
  "task_id" varchar(50) COLLATE "pg_catalog"."default",
  "trace_id" varchar(100) COLLATE "pg_catalog"."default",
  "model_name" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "mode" varchar(20) COLLATE "pg_catalog"."default" NOT NULL,
  "prompt_hash" varchar(64) COLLATE "pg_catalog"."default",
  "input_tokens" int4,
  "output_tokens" int4,
  "total_tokens" int4,
  "gemini_request" text COLLATE "pg_catalog"."default",
  "gemini_response" text COLLATE "pg_catalog"."default",
  "status" varchar(20) COLLATE "pg_catalog"."default",
  "error_code" varchar(50) COLLATE "pg_catalog"."default",
  "error_message" text COLLATE "pg_catalog"."default",
  "processing_time_ms" int4,
  "retry_count" int4 DEFAULT 0,
  "user_id" varchar(50) COLLATE "pg_catalog"."default",
  "created_at" timestamp(6) DEFAULT CURRENT_TIMESTAMP
)
;

-- Table: monitoring_metrics
CREATE TABLE "public"."monitoring_metrics" (
  "id" int8 NOT NULL DEFAULT nextval('monitoring_metrics_id_seq'::regclass),
  "metric_name" varchar(100) COLLATE "pg_catalog"."default" NOT NULL,
  "metric_value" numeric(10,2) NOT NULL,
  "group_name" varchar(50) COLLATE "pg_catalog"."default",
  "time_window" varchar(20) COLLATE "pg_catalog"."default",
  "recorded_at" timestamp(6) DEFAULT CURRENT_TIMESTAMP
)
;

-- Table: problem_results
CREATE TABLE "public"."problem_results" (
  "id" int8 NOT NULL DEFAULT nextval('problem_results_id_seq'::regclass),
  "problem_id" int4 NOT NULL,
  "model_name" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "prompt_version" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "schema_version" varchar(20) COLLATE "pg_catalog"."default" NOT NULL DEFAULT 'v1'::character varying,
  "version_hash" varchar(64) COLLATE "pg_catalog"."default" NOT NULL,
  "normalized_text_hash" varchar(64) COLLATE "pg_catalog"."default",
  "mode" varchar(20) COLLATE "pg_catalog"."default" NOT NULL,
  "result_json" text COLLATE "pg_catalog"."default" NOT NULL,
  "processing_time_ms" int4,
  "token_usage" int4,
  "quality_score" int4,
  "is_cached" int2 DEFAULT 0,
  "created_at" timestamp(6) DEFAULT CURRENT_TIMESTAMP,
  "updated_at" timestamp(6) DEFAULT CURRENT_TIMESTAMP
)
;

-- Table: problems
CREATE TABLE "public"."problems" (
  "id" int8 NOT NULL DEFAULT nextval('problems_id_seq'::regclass),
  "user_id" int8 NOT NULL,
  "title" varchar(200) COLLATE "pg_catalog"."default",
  "content" text COLLATE "pg_catalog"."default",
  "pic1" varchar(255) COLLATE "pg_catalog"."default",
  "pic2" varchar(255) COLLATE "pg_catalog"."default",
  "pic3" varchar(255) COLLATE "pg_catalog"."default",
  "content_norm" text COLLATE "pg_catalog"."default",
  "content_md5" char(32) COLLATE "pg_catalog"."default",
  "original_image_url1" varchar(255) COLLATE "pg_catalog"."default",
  "original_image_url2" varchar(255) COLLATE "pg_catalog"."default",
  "original_image_url3" varchar(255) COLLATE "pg_catalog"."default",
  "corrected_image_url1" varchar(255) COLLATE "pg_catalog"."default",
  "corrected_image_url2" varchar(255) COLLATE "pg_catalog"."default",
  "corrected_image_url3" varchar(500) COLLATE "pg_catalog"."default",
  "subject" varchar(50) COLLATE "pg_catalog"."default" DEFAULT 'math'::character varying,
  "grade_level" varchar(20) COLLATE "pg_catalog"."default",
  "semester" varchar(20) COLLATE "pg_catalog"."default",
  "mode" varchar(1) COLLATE "pg_catalog"."default" DEFAULT 'A'::character varying,
  "difficulty" int2 DEFAULT 1,
  "processing_time_sec" int4,
  "topic_tags" jsonb,
  "ocr_confidence" numeric(5,2),
  "ocr_provider" varchar(50) COLLATE "pg_catalog"."default",
  "latex_content" text COLLATE "pg_catalog"."default",
  "status" int2 DEFAULT 1,
  "created_at" timestamp(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" timestamp(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "gemini_content" text COLLATE "pg_catalog"."default",
  "gemini_model_version" varchar(50) COLLATE "pg_catalog"."default",
  "gemini_request" text COLLATE "pg_catalog"."default",
  "gemini_response" text COLLATE "pg_catalog"."default"
)
;

-- Table: retry_queue
CREATE TABLE "public"."retry_queue" (
  "id" int8 NOT NULL DEFAULT nextval('retry_queue_id_seq'::regclass),
  "task_id" varchar(32) COLLATE "pg_catalog"."default" NOT NULL,
  "problem_id" int8 NOT NULL,
  "user_id" int8 NOT NULL,
  "mode" varchar(20) COLLATE "pg_catalog"."default" NOT NULL,
  "retry_count" int2 DEFAULT 1,
  "max_retries" int2 DEFAULT 3,
  "scheduled_at" timestamp(6) NOT NULL,
  "last_error_code" varchar(50) COLLATE "pg_catalog"."default",
  "error_classification" varchar(50) COLLATE "pg_catalog"."default",
  "status" varchar(20) COLLATE "pg_catalog"."default" DEFAULT 'PENDING'::character varying,
  "processed_at" timestamp(6),
  "created_at" timestamp(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" timestamp(6) NOT NULL DEFAULT CURRENT_TIMESTAMP
)
;

-- Table: rollback_logs
CREATE TABLE "public"."rollback_logs" (
  "id" int8 NOT NULL DEFAULT nextval('rollback_logs_id_seq'::regclass),
  "reason" varchar(100) COLLATE "pg_catalog"."default" NOT NULL,
  "from_percentage" int4,
  "to_percentage" int4,
  "metric_outbox_sent" numeric(5,2),
  "metric_completion_rate" numeric(5,2),
  "metric_dlq_count" int4,
  "status" varchar(20) COLLATE "pg_catalog"."default" DEFAULT 'SUCCESS'::character varying,
  "timestamp" timestamp(6) DEFAULT CURRENT_TIMESTAMP
)
;

-- Table: system_config
CREATE TABLE "public"."system_config" (
  "id" int4 NOT NULL DEFAULT nextval('system_config_id_seq'::regclass),
  "key" varchar(100) COLLATE "pg_catalog"."default" NOT NULL,
  "value" varchar(500) COLLATE "pg_catalog"."default" NOT NULL,
  "description" varchar(500) COLLATE "pg_catalog"."default",
  "updated_by" varchar(100) COLLATE "pg_catalog"."default",
  "updated_at" timestamp(6) DEFAULT CURRENT_TIMESTAMP
)
;

-- Table: task_outbox
CREATE TABLE "public"."task_outbox" (
  "id" int8 NOT NULL DEFAULT nextval('task_outbox_id_seq'::regclass),
  "task_id" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "trace_id" varchar(100) COLLATE "pg_catalog"."default" NOT NULL,
  "problem_id" int4 NOT NULL,
  "user_id" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "mode" varchar(20) COLLATE "pg_catalog"."default" NOT NULL,
  "image_url" varchar(500) COLLATE "pg_catalog"."default",
  "ocr_text" text COLLATE "pg_catalog"."default",
  "request_key" varchar(64) COLLATE "pg_catalog"."default" NOT NULL,
  "content_md5" varchar(32) COLLATE "pg_catalog"."default",
  "model_name" varchar(50) COLLATE "pg_catalog"."default",
  "prompt_version" varchar(50) COLLATE "pg_catalog"."default",
  "schema_version" varchar(20) COLLATE "pg_catalog"."default" DEFAULT 'v1'::character varying,
  "difficulty_flag" varchar(50) COLLATE "pg_catalog"."default",
  "status" varchar(20) COLLATE "pg_catalog"."default" DEFAULT 'NEW'::character varying,
  "retry_count" int4 DEFAULT 0,
  "last_error" varchar(500) COLLATE "pg_catalog"."default",
  "created_at" timestamp(6) DEFAULT CURRENT_TIMESTAMP,
  "updated_at" timestamp(6) DEFAULT CURRENT_TIMESTAMP,
  "sent_at" timestamp(6),
  "ack_at" timestamp(6)
)
;

-- Table: test_connection
CREATE TABLE "public"."test_connection" (
  "id" uuid NOT NULL DEFAULT uuid_generate_v4(),
  "name" varchar(100) COLLATE "pg_catalog"."default" NOT NULL,
  "created_at" timestamptz(6) DEFAULT now()
)
;

-- Table: tiku_teacher_favorite
CREATE TABLE "public"."tiku_teacher_favorite" (
  "id" int8 NOT NULL GENERATED BY DEFAULT AS IDENTITY (
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1
),
  "created_at" timestamptz(6) NOT NULL,
  "question_id" int8 NOT NULL,
  "user_id" int4,
  "teacher_id" int8
)
;

-- Table: tiku_teacher_profile
CREATE TABLE "public"."tiku_teacher_profile" (
  "id" int8 NOT NULL GENERATED BY DEFAULT AS IDENTITY (
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1
),
  "username" varchar(100) COLLATE "pg_catalog"."default" NOT NULL,
  "display_name" varchar(100) COLLATE "pg_catalog"."default" NOT NULL,
  "subject" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "stage" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "created_at" timestamptz(6) NOT NULL,
  "updated_at" timestamptz(6) NOT NULL
)
;

-- Table: users
CREATE TABLE "public"."users" (
  "id" int8 NOT NULL DEFAULT nextval('users_id_seq'::regclass),
  "openid" varchar(64) COLLATE "pg_catalog"."default" NOT NULL,
  "unionid" varchar(64) COLLATE "pg_catalog"."default",
  "nickname" varchar(100) COLLATE "pg_catalog"."default",
  "avatar_url" varchar(500) COLLATE "pg_catalog"."default",
  "gender" int2 DEFAULT 0,
  "country" varchar(50) COLLATE "pg_catalog"."default",
  "province" varchar(50) COLLATE "pg_catalog"."default",
  "city" varchar(50) COLLATE "pg_catalog"."default",
  "district" varchar(50) COLLATE "pg_catalog"."default",
  "subdistrict" varchar(50) COLLATE "pg_catalog"."default",
  "signup_location" varchar(200) COLLATE "pg_catalog"."default",
  "gps_position" varchar(100) COLLATE "pg_catalog"."default",
  "language" varchar(20) COLLATE "pg_catalog"."default" DEFAULT 'zh_CN'::character varying,
  "phone" varchar(20) COLLATE "pg_catalog"."default",
  "email" varchar(100) COLLATE "pg_catalog"."default",
  "grade" varchar(20) COLLATE "pg_catalog"."default",
  "school" varchar(100) COLLATE "pg_catalog"."default",
  "status" int2 DEFAULT 1,
  "last_login_at" timestamp(6),
  "created_at" timestamp(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "updated_at" timestamp(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "user_type" varchar(10) COLLATE "pg_catalog"."default" DEFAULT 'guest'::character varying,
  "guest_usage_count" int4 DEFAULT 0,
  "points" int4 DEFAULT 0,
  "total_questions" int4 DEFAULT 0
)
;

-- 共 19 张表
