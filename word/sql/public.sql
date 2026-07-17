/*
 Navicat Premium Dump SQL

 Source Server         : localhost-pg
 Source Server Type    : PostgreSQL
 Source Server Version : 170010 (170010)
 Source Host           : localhost:5432
 Source Catalog        : qisi_ai_tutor
 Source Schema         : public

 Target Server Type    : PostgreSQL
 Target Server Version : 170010 (170010)
 File Encoding         : 65001

 Date: 17/07/2026 09:58:46
*/


-- ----------------------------
-- Sequence structure for ai_guidance_session_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."ai_guidance_session_id_seq";
CREATE SEQUENCE "public"."ai_guidance_session_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for ai_parse_result_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."ai_parse_result_id_seq";
CREATE SEQUENCE "public"."ai_parse_result_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for alert_logs_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."alert_logs_id_seq";
CREATE SEQUENCE "public"."alert_logs_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for answer_attempt_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."answer_attempt_id_seq";
CREATE SEQUENCE "public"."answer_attempt_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for api_task_logs_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."api_task_logs_id_seq";
CREATE SEQUENCE "public"."api_task_logs_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for auth_group_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."auth_group_id_seq";
CREATE SEQUENCE "public"."auth_group_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 2147483647
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for auth_group_permissions_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."auth_group_permissions_id_seq";
CREATE SEQUENCE "public"."auth_group_permissions_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for auth_permission_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."auth_permission_id_seq";
CREATE SEQUENCE "public"."auth_permission_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 2147483647
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for auth_user_groups_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."auth_user_groups_id_seq";
CREATE SEQUENCE "public"."auth_user_groups_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for auth_user_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."auth_user_id_seq";
CREATE SEQUENCE "public"."auth_user_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 2147483647
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for auth_user_user_permissions_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."auth_user_user_permissions_id_seq";
CREATE SEQUENCE "public"."auth_user_user_permissions_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for class_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."class_id_seq";
CREATE SEQUENCE "public"."class_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for class_join_request_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."class_join_request_id_seq";
CREATE SEQUENCE "public"."class_join_request_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for class_student_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."class_student_id_seq";
CREATE SEQUENCE "public"."class_student_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for class_teacher_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."class_teacher_id_seq";
CREATE SEQUENCE "public"."class_teacher_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for course_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."course_id_seq";
CREATE SEQUENCE "public"."course_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for course_material_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."course_material_id_seq";
CREATE SEQUENCE "public"."course_material_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for course_question_link_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."course_question_link_id_seq";
CREATE SEQUENCE "public"."course_question_link_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for course_tree_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."course_tree_id_seq";
CREATE SEQUENCE "public"."course_tree_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for course_variant_task_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."course_variant_task_id_seq";
CREATE SEQUENCE "public"."course_variant_task_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for django_admin_log_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."django_admin_log_id_seq";
CREATE SEQUENCE "public"."django_admin_log_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 2147483647
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for django_content_type_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."django_content_type_id_seq";
CREATE SEQUENCE "public"."django_content_type_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 2147483647
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for django_migrations_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."django_migrations_id_seq";
CREATE SEQUENCE "public"."django_migrations_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for dlq_messages_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."dlq_messages_id_seq";
CREATE SEQUENCE "public"."dlq_messages_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for exam_page_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."exam_page_id_seq";
CREATE SEQUENCE "public"."exam_page_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for exam_question_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."exam_question_id_seq";
CREATE SEQUENCE "public"."exam_question_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for gemini_results_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."gemini_results_id_seq";
CREATE SEQUENCE "public"."gemini_results_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 2147483647
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for institution_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."institution_id_seq";
CREATE SEQUENCE "public"."institution_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for institution_member_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."institution_member_id_seq";
CREATE SEQUENCE "public"."institution_member_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for learning_mission_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."learning_mission_id_seq";
CREATE SEQUENCE "public"."learning_mission_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for llm_audit_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."llm_audit_id_seq";
CREATE SEQUENCE "public"."llm_audit_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for mastery_record_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."mastery_record_id_seq";
CREATE SEQUENCE "public"."mastery_record_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for mission_level_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."mission_level_id_seq";
CREATE SEQUENCE "public"."mission_level_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for mission_question_rel_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."mission_question_rel_id_seq";
CREATE SEQUENCE "public"."mission_question_rel_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for monitoring_metrics_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."monitoring_metrics_id_seq";
CREATE SEQUENCE "public"."monitoring_metrics_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for problem_results_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."problem_results_id_seq";
CREATE SEQUENCE "public"."problem_results_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for problems_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."problems_id_seq";
CREATE SEQUENCE "public"."problems_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for question_image_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."question_image_id_seq";
CREATE SEQUENCE "public"."question_image_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for question_option_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."question_option_id_seq";
CREATE SEQUENCE "public"."question_option_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for retry_queue_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."retry_queue_id_seq";
CREATE SEQUENCE "public"."retry_queue_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for rollback_logs_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."rollback_logs_id_seq";
CREATE SEQUENCE "public"."rollback_logs_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for student_level_progress_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."student_level_progress_id_seq";
CREATE SEQUENCE "public"."student_level_progress_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for student_mission_progress_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."student_mission_progress_id_seq";
CREATE SEQUENCE "public"."student_mission_progress_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for student_parent_bind_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."student_parent_bind_id_seq";
CREATE SEQUENCE "public"."student_parent_bind_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for system_config_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."system_config_id_seq";
CREATE SEQUENCE "public"."system_config_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 2147483647
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for task_outbox_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."task_outbox_id_seq";
CREATE SEQUENCE "public"."task_outbox_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for tiku_exam_paper_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."tiku_exam_paper_id_seq";
CREATE SEQUENCE "public"."tiku_exam_paper_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for tiku_favorite_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."tiku_favorite_id_seq";
CREATE SEQUENCE "public"."tiku_favorite_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for tiku_paper_code_counter_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."tiku_paper_code_counter_id_seq";
CREATE SEQUENCE "public"."tiku_paper_code_counter_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for tiku_parse_task_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."tiku_parse_task_id_seq";
CREATE SEQUENCE "public"."tiku_parse_task_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for tiku_question_id_counter_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."tiku_question_id_counter_id_seq";
CREATE SEQUENCE "public"."tiku_question_id_counter_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for tiku_teacher_favorite_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."tiku_teacher_favorite_id_seq";
CREATE SEQUENCE "public"."tiku_teacher_favorite_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for tiku_teacher_profile_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."tiku_teacher_profile_id_seq";
CREATE SEQUENCE "public"."tiku_teacher_profile_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for user_account_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."user_account_id_seq";
CREATE SEQUENCE "public"."user_account_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for users_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."users_id_seq";
CREATE SEQUENCE "public"."users_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Sequence structure for wrong_book_item_id_seq
-- ----------------------------
DROP SEQUENCE IF EXISTS "public"."wrong_book_item_id_seq";
CREATE SEQUENCE "public"."wrong_book_item_id_seq" 
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1;

-- ----------------------------
-- Table structure for ai_guidance_session
-- ----------------------------
DROP TABLE IF EXISTS "public"."ai_guidance_session";
CREATE TABLE "public"."ai_guidance_session" (
  "id" int8 NOT NULL GENERATED BY DEFAULT AS IDENTITY (
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1
),
  "question_id" int4 NOT NULL,
  "mode_type" varchar(10) COLLATE "pg_catalog"."default" NOT NULL,
  "session_status" varchar(20) COLLATE "pg_catalog"."default" NOT NULL,
  "invalid_input_count" int4 NOT NULL,
  "script_source" varchar(20) COLLATE "pg_catalog"."default" NOT NULL,
  "content_log_json" jsonb NOT NULL,
  "created_at" timestamptz(6) NOT NULL,
  "updated_at" timestamptz(6) NOT NULL,
  "student_user_id_id" int8 NOT NULL
)
;

-- ----------------------------
-- Table structure for alert_logs
-- ----------------------------
DROP TABLE IF EXISTS "public"."alert_logs";
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

-- ----------------------------
-- Table structure for answer_attempt
-- ----------------------------
DROP TABLE IF EXISTS "public"."answer_attempt";
CREATE TABLE "public"."answer_attempt" (
  "id" int8 NOT NULL GENERATED BY DEFAULT AS IDENTITY (
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1
),
  "question_id" int4 NOT NULL,
  "attempt_no" int4 NOT NULL,
  "answer_content" jsonb NOT NULL,
  "is_correct" bool NOT NULL,
  "score" numeric(5,2) NOT NULL,
  "submit_source" varchar(20) COLLATE "pg_catalog"."default" NOT NULL,
  "submitted_at" timestamptz(6) NOT NULL,
  "level_id" int8,
  "mission_id" int8,
  "student_user_id_id" int8 NOT NULL,
  "is_subjective_pending" bool NOT NULL
)
;

-- ----------------------------
-- Table structure for api_task_logs
-- ----------------------------
DROP TABLE IF EXISTS "public"."api_task_logs";
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

-- ----------------------------
-- Table structure for auth_group
-- ----------------------------
DROP TABLE IF EXISTS "public"."auth_group";
CREATE TABLE "public"."auth_group" (
  "id" int4 NOT NULL GENERATED BY DEFAULT AS IDENTITY (
INCREMENT 1
MINVALUE  1
MAXVALUE 2147483647
START 1
CACHE 1
),
  "name" varchar(150) COLLATE "pg_catalog"."default" NOT NULL
)
;

-- ----------------------------
-- Table structure for auth_group_permissions
-- ----------------------------
DROP TABLE IF EXISTS "public"."auth_group_permissions";
CREATE TABLE "public"."auth_group_permissions" (
  "id" int8 NOT NULL GENERATED BY DEFAULT AS IDENTITY (
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1
),
  "group_id" int4 NOT NULL,
  "permission_id" int4 NOT NULL
)
;

-- ----------------------------
-- Table structure for auth_permission
-- ----------------------------
DROP TABLE IF EXISTS "public"."auth_permission";
CREATE TABLE "public"."auth_permission" (
  "id" int4 NOT NULL GENERATED BY DEFAULT AS IDENTITY (
INCREMENT 1
MINVALUE  1
MAXVALUE 2147483647
START 1
CACHE 1
),
  "name" varchar(255) COLLATE "pg_catalog"."default" NOT NULL,
  "content_type_id" int4 NOT NULL,
  "codename" varchar(100) COLLATE "pg_catalog"."default" NOT NULL
)
;

-- ----------------------------
-- Table structure for auth_user
-- ----------------------------
DROP TABLE IF EXISTS "public"."auth_user";
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

-- ----------------------------
-- Table structure for auth_user_groups
-- ----------------------------
DROP TABLE IF EXISTS "public"."auth_user_groups";
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

-- ----------------------------
-- Table structure for auth_user_user_permissions
-- ----------------------------
DROP TABLE IF EXISTS "public"."auth_user_user_permissions";
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

-- ----------------------------
-- Table structure for class
-- ----------------------------
DROP TABLE IF EXISTS "public"."class";
CREATE TABLE "public"."class" (
  "id" int8 NOT NULL GENERATED BY DEFAULT AS IDENTITY (
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1
),
  "class_no" varchar(20) COLLATE "pg_catalog"."default" NOT NULL,
  "class_name" varchar(200) COLLATE "pg_catalog"."default" NOT NULL,
  "description" text COLLATE "pg_catalog"."default",
  "max_students" int4 NOT NULL,
  "invite_code" varchar(8) COLLATE "pg_catalog"."default" NOT NULL,
  "allow_invite_join" bool NOT NULL,
  "status" varchar(20) COLLATE "pg_catalog"."default" NOT NULL,
  "created_at" timestamptz(6) NOT NULL,
  "updated_at" timestamptz(6) NOT NULL,
  "creator_teacher_id" int8,
  "institution_id" int8 NOT NULL
)
;

-- ----------------------------
-- Table structure for class_join_request
-- ----------------------------
DROP TABLE IF EXISTS "public"."class_join_request";
CREATE TABLE "public"."class_join_request" (
  "id" int8 NOT NULL GENERATED BY DEFAULT AS IDENTITY (
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1
),
  "applicant_name" varchar(100) COLLATE "pg_catalog"."default" NOT NULL,
  "applicant_phone" varchar(20) COLLATE "pg_catalog"."default",
  "request_type" varchar(20) COLLATE "pg_catalog"."default" NOT NULL,
  "status" varchar(20) COLLATE "pg_catalog"."default" NOT NULL,
  "message" text COLLATE "pg_catalog"."default",
  "handled_at" timestamptz(6),
  "created_at" timestamptz(6) NOT NULL,
  "applicant_id" int8 NOT NULL,
  "class_id" int8 NOT NULL,
  "handled_by_id" int8
)
;

-- ----------------------------
-- Table structure for class_student
-- ----------------------------
DROP TABLE IF EXISTS "public"."class_student";
CREATE TABLE "public"."class_student" (
  "id" int8 NOT NULL GENERATED BY DEFAULT AS IDENTITY (
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1
),
  "join_type" varchar(20) COLLATE "pg_catalog"."default" NOT NULL,
  "status" varchar(20) COLLATE "pg_catalog"."default" NOT NULL,
  "joined_at" timestamptz(6) NOT NULL,
  "class_id" int8 NOT NULL,
  "student_id" int8 NOT NULL
)
;

-- ----------------------------
-- Table structure for class_teacher
-- ----------------------------
DROP TABLE IF EXISTS "public"."class_teacher";
CREATE TABLE "public"."class_teacher" (
  "id" int8 NOT NULL GENERATED BY DEFAULT AS IDENTITY (
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1
),
  "role" varchar(20) COLLATE "pg_catalog"."default" NOT NULL,
  "class_id" int8 NOT NULL,
  "teacher_id" int8 NOT NULL
)
;

-- ----------------------------
-- Table structure for course
-- ----------------------------
DROP TABLE IF EXISTS "public"."course";
CREATE TABLE "public"."course" (
  "id" int8 NOT NULL GENERATED BY DEFAULT AS IDENTITY (
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1
),
  "name" varchar(200) COLLATE "pg_catalog"."default" NOT NULL,
  "description" text COLLATE "pg_catalog"."default",
  "subject" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "grade_level" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "cover_image" varchar(500) COLLATE "pg_catalog"."default",
  "is_deleted" bool NOT NULL,
  "created_at" timestamptz(6) NOT NULL,
  "updated_at" timestamptz(6) NOT NULL,
  "teacher_id" int8 NOT NULL
)
;

-- ----------------------------
-- Table structure for course_material
-- ----------------------------
DROP TABLE IF EXISTS "public"."course_material";
CREATE TABLE "public"."course_material" (
  "id" int8 NOT NULL GENERATED BY DEFAULT AS IDENTITY (
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1
),
  "name" varchar(255) COLLATE "pg_catalog"."default" NOT NULL,
  "file_path" varchar(500) COLLATE "pg_catalog"."default" NOT NULL,
  "file_type" varchar(20) COLLATE "pg_catalog"."default" NOT NULL,
  "file_size" int8 NOT NULL,
  "mime_type" varchar(100) COLLATE "pg_catalog"."default" NOT NULL,
  "is_deleted" bool NOT NULL,
  "created_at" timestamptz(6) NOT NULL,
  "course_id" int8 NOT NULL,
  "uploaded_by_id" int8
)
;

-- ----------------------------
-- Table structure for course_question_link
-- ----------------------------
DROP TABLE IF EXISTS "public"."course_question_link";
CREATE TABLE "public"."course_question_link" (
  "id" int8 NOT NULL GENERATED BY DEFAULT AS IDENTITY (
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1
),
  "source" varchar(30) COLLATE "pg_catalog"."default" NOT NULL,
  "source_course_name" varchar(200) COLLATE "pg_catalog"."default",
  "is_deleted" bool NOT NULL,
  "created_at" timestamptz(6) NOT NULL,
  "course_id" int8 NOT NULL,
  "question_id" int8 NOT NULL,
  "tree_node_id" int8
)
;

-- ----------------------------
-- Table structure for course_tree
-- ----------------------------
DROP TABLE IF EXISTS "public"."course_tree";
CREATE TABLE "public"."course_tree" (
  "id" int8 NOT NULL GENERATED BY DEFAULT AS IDENTITY (
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1
),
  "name" varchar(200) COLLATE "pg_catalog"."default" NOT NULL,
  "sort_order" int4 NOT NULL,
  "created_at" timestamptz(6) NOT NULL,
  "course_id" int8 NOT NULL,
  "parent_id" int8
)
;

-- ----------------------------
-- Table structure for course_variant_task
-- ----------------------------
DROP TABLE IF EXISTS "public"."course_variant_task";
CREATE TABLE "public"."course_variant_task" (
  "id" int8 NOT NULL GENERATED BY DEFAULT AS IDENTITY (
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1
),
  "variant_mode" varchar(30) COLLATE "pg_catalog"."default" NOT NULL,
  "status" varchar(20) COLLATE "pg_catalog"."default" NOT NULL,
  "generator_result" jsonb,
  "verifier_result" jsonb,
  "generated_question" jsonb,
  "error_message" text COLLATE "pg_catalog"."default",
  "created_at" timestamptz(6) NOT NULL,
  "completed_at" timestamptz(6),
  "original_question_id" int8 NOT NULL
)
;

-- ----------------------------
-- Table structure for django_admin_log
-- ----------------------------
DROP TABLE IF EXISTS "public"."django_admin_log";
CREATE TABLE "public"."django_admin_log" (
  "id" int4 NOT NULL GENERATED BY DEFAULT AS IDENTITY (
INCREMENT 1
MINVALUE  1
MAXVALUE 2147483647
START 1
CACHE 1
),
  "action_time" timestamptz(6) NOT NULL,
  "object_id" text COLLATE "pg_catalog"."default",
  "object_repr" varchar(200) COLLATE "pg_catalog"."default" NOT NULL,
  "action_flag" int2 NOT NULL,
  "change_message" text COLLATE "pg_catalog"."default" NOT NULL,
  "content_type_id" int4,
  "user_id" int4 NOT NULL
)
;

-- ----------------------------
-- Table structure for django_content_type
-- ----------------------------
DROP TABLE IF EXISTS "public"."django_content_type";
CREATE TABLE "public"."django_content_type" (
  "id" int4 NOT NULL GENERATED BY DEFAULT AS IDENTITY (
INCREMENT 1
MINVALUE  1
MAXVALUE 2147483647
START 1
CACHE 1
),
  "app_label" varchar(100) COLLATE "pg_catalog"."default" NOT NULL,
  "model" varchar(100) COLLATE "pg_catalog"."default" NOT NULL
)
;

-- ----------------------------
-- Table structure for django_migrations
-- ----------------------------
DROP TABLE IF EXISTS "public"."django_migrations";
CREATE TABLE "public"."django_migrations" (
  "id" int8 NOT NULL GENERATED BY DEFAULT AS IDENTITY (
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1
),
  "app" varchar(255) COLLATE "pg_catalog"."default" NOT NULL,
  "name" varchar(255) COLLATE "pg_catalog"."default" NOT NULL,
  "applied" timestamptz(6) NOT NULL
)
;

-- ----------------------------
-- Table structure for django_session
-- ----------------------------
DROP TABLE IF EXISTS "public"."django_session";
CREATE TABLE "public"."django_session" (
  "session_key" varchar(40) COLLATE "pg_catalog"."default" NOT NULL,
  "session_data" text COLLATE "pg_catalog"."default" NOT NULL,
  "expire_date" timestamptz(6) NOT NULL
)
;

-- ----------------------------
-- Table structure for dlq_messages
-- ----------------------------
DROP TABLE IF EXISTS "public"."dlq_messages";
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

-- ----------------------------
-- Table structure for gemini_results
-- ----------------------------
DROP TABLE IF EXISTS "public"."gemini_results";
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

-- ----------------------------
-- Table structure for institution
-- ----------------------------
DROP TABLE IF EXISTS "public"."institution";
CREATE TABLE "public"."institution" (
  "id" int8 NOT NULL GENERATED BY DEFAULT AS IDENTITY (
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1
),
  "institution_name" varchar(200) COLLATE "pg_catalog"."default" NOT NULL,
  "contact_name" varchar(100) COLLATE "pg_catalog"."default",
  "contact_phone" varchar(20) COLLATE "pg_catalog"."default",
  "contact_email" varchar(200) COLLATE "pg_catalog"."default",
  "address" varchar(500) COLLATE "pg_catalog"."default",
  "status" varchar(20) COLLATE "pg_catalog"."default" NOT NULL,
  "created_at" timestamptz(6) NOT NULL,
  "updated_at" timestamptz(6) NOT NULL,
  "created_by_id" int8
)
;

-- ----------------------------
-- Table structure for institution_member
-- ----------------------------
DROP TABLE IF EXISTS "public"."institution_member";
CREATE TABLE "public"."institution_member" (
  "id" int8 NOT NULL GENERATED BY DEFAULT AS IDENTITY (
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1
),
  "role" varchar(20) COLLATE "pg_catalog"."default" NOT NULL,
  "status" varchar(20) COLLATE "pg_catalog"."default" NOT NULL,
  "joined_at" timestamptz(6) NOT NULL,
  "institution_id" int8 NOT NULL,
  "user_id" int8 NOT NULL
)
;

-- ----------------------------
-- Table structure for knowledge_points
-- ----------------------------
DROP TABLE IF EXISTS "public"."knowledge_points";
CREATE TABLE "public"."knowledge_points" (
  "id" int8 NOT NULL,
  "subject" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "stage" varchar(20) COLLATE "pg_catalog"."default" NOT NULL,
  "grade_index" int2 NOT NULL,
  "grade_name" varchar(20) COLLATE "pg_catalog"."default" NOT NULL,
  "term" varchar(10) COLLATE "pg_catalog"."default" NOT NULL,
  "chapter" varchar(255) COLLATE "pg_catalog"."default" NOT NULL,
  "module" varchar(255) COLLATE "pg_catalog"."default" NOT NULL,
  "node_type" varchar(20) COLLATE "pg_catalog"."default" NOT NULL,
  "content" text COLLATE "pg_catalog"."default" NOT NULL,
  "created_at" timestamp(6) NOT NULL DEFAULT CURRENT_TIMESTAMP
)
;

-- ----------------------------
-- Table structure for learning_mission
-- ----------------------------
DROP TABLE IF EXISTS "public"."learning_mission";
CREATE TABLE "public"."learning_mission" (
  "id" int8 NOT NULL GENERATED BY DEFAULT AS IDENTITY (
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1
),
  "mission_no" varchar(32) COLLATE "pg_catalog"."default" NOT NULL,
  "mission_name" varchar(120) COLLATE "pg_catalog"."default" NOT NULL,
  "goal_text" varchar(255) COLLATE "pg_catalog"."default" NOT NULL,
  "start_at" timestamptz(6),
  "end_at" timestamptz(6),
  "status" varchar(20) COLLATE "pg_catalog"."default" NOT NULL,
  "default_mode_policy" varchar(50) COLLATE "pg_catalog"."default",
  "created_at" timestamptz(6) NOT NULL,
  "updated_at" timestamptz(6) NOT NULL,
  "creator_teacher_id_id" int8 NOT NULL,
  "class_id" int8
)
;

-- ----------------------------
-- Table structure for llm_audit
-- ----------------------------
DROP TABLE IF EXISTS "public"."llm_audit";
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

-- ----------------------------
-- Table structure for mastery_record
-- ----------------------------
DROP TABLE IF EXISTS "public"."mastery_record";
CREATE TABLE "public"."mastery_record" (
  "id" int8 NOT NULL GENERATED BY DEFAULT AS IDENTITY (
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1
),
  "mastery_type" varchar(20) COLLATE "pg_catalog"."default" NOT NULL,
  "target_code" varchar(64) COLLATE "pg_catalog"."default" NOT NULL,
  "mastery_status" varchar(20) COLLATE "pg_catalog"."default" NOT NULL,
  "mastery_score" numeric(5,2) NOT NULL,
  "next_review_at" timestamptz(6),
  "updated_at" timestamptz(6) NOT NULL,
  "student_user_id_id" int8 NOT NULL
)
;

-- ----------------------------
-- Table structure for mission_level
-- ----------------------------
DROP TABLE IF EXISTS "public"."mission_level";
CREATE TABLE "public"."mission_level" (
  "id" int8 NOT NULL GENERATED BY DEFAULT AS IDENTITY (
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1
),
  "level_no" int4 NOT NULL,
  "level_name" varchar(100) COLLATE "pg_catalog"."default" NOT NULL,
  "level_type" varchar(30) COLLATE "pg_catalog"."default" NOT NULL,
  "pass_rule_json" jsonb NOT NULL,
  "mode_policy" varchar(50) COLLATE "pg_catalog"."default",
  "hint_strength" varchar(20) COLLATE "pg_catalog"."default" NOT NULL,
  "mission_id" int8 NOT NULL
)
;

-- ----------------------------
-- Table structure for mission_question_rel
-- ----------------------------
DROP TABLE IF EXISTS "public"."mission_question_rel";
CREATE TABLE "public"."mission_question_rel" (
  "id" int8 NOT NULL GENERATED BY DEFAULT AS IDENTITY (
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1
),
  "question_id" int4 NOT NULL,
  "sort_no" int4 NOT NULL,
  "is_required" bool NOT NULL,
  "source_type" varchar(20) COLLATE "pg_catalog"."default" NOT NULL,
  "level_id" int8 NOT NULL,
  "mission_id" int8 NOT NULL
)
;

-- ----------------------------
-- Table structure for monitoring_metrics
-- ----------------------------
DROP TABLE IF EXISTS "public"."monitoring_metrics";
CREATE TABLE "public"."monitoring_metrics" (
  "id" int8 NOT NULL DEFAULT nextval('monitoring_metrics_id_seq'::regclass),
  "metric_name" varchar(100) COLLATE "pg_catalog"."default" NOT NULL,
  "metric_value" numeric(10,2) NOT NULL,
  "group_name" varchar(50) COLLATE "pg_catalog"."default",
  "time_window" varchar(20) COLLATE "pg_catalog"."default",
  "recorded_at" timestamp(6) DEFAULT CURRENT_TIMESTAMP
)
;

-- ----------------------------
-- Table structure for problem_results
-- ----------------------------
DROP TABLE IF EXISTS "public"."problem_results";
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

-- ----------------------------
-- Table structure for problems
-- ----------------------------
DROP TABLE IF EXISTS "public"."problems";
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

-- ----------------------------
-- Table structure for retry_queue
-- ----------------------------
DROP TABLE IF EXISTS "public"."retry_queue";
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

-- ----------------------------
-- Table structure for rollback_logs
-- ----------------------------
DROP TABLE IF EXISTS "public"."rollback_logs";
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

-- ----------------------------
-- Table structure for student_level_progress
-- ----------------------------
DROP TABLE IF EXISTS "public"."student_level_progress";
CREATE TABLE "public"."student_level_progress" (
  "id" int8 NOT NULL GENERATED BY DEFAULT AS IDENTITY (
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1
),
  "status" varchar(20) COLLATE "pg_catalog"."default" NOT NULL,
  "pass_score" numeric(5,2) NOT NULL,
  "attempt_count" int4 NOT NULL,
  "passed_at" timestamptz(6),
  "level_id" int8 NOT NULL,
  "student_user_id_id" int8 NOT NULL
)
;

-- ----------------------------
-- Table structure for student_mission_progress
-- ----------------------------
DROP TABLE IF EXISTS "public"."student_mission_progress";
CREATE TABLE "public"."student_mission_progress" (
  "id" int8 NOT NULL GENERATED BY DEFAULT AS IDENTITY (
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1
),
  "progress_status" varchar(20) COLLATE "pg_catalog"."default" NOT NULL,
  "progress_percent" numeric(5,2) NOT NULL,
  "last_action_at" timestamptz(6) NOT NULL,
  "current_level_id" int8,
  "mission_id" int8 NOT NULL,
  "student_user_id_id" int8 NOT NULL
)
;

-- ----------------------------
-- Table structure for student_parent_bind
-- ----------------------------
DROP TABLE IF EXISTS "public"."student_parent_bind";
CREATE TABLE "public"."student_parent_bind" (
  "id" int8 NOT NULL GENERATED BY DEFAULT AS IDENTITY (
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1
),
  "relation_type" varchar(20) COLLATE "pg_catalog"."default" NOT NULL,
  "bind_status" varchar(20) COLLATE "pg_catalog"."default" NOT NULL,
  "bound_at" timestamptz(6) NOT NULL,
  "parent_user_id_id" int8 NOT NULL,
  "student_user_id_id" int8 NOT NULL
)
;

-- ----------------------------
-- Table structure for system_config
-- ----------------------------
DROP TABLE IF EXISTS "public"."system_config";
CREATE TABLE "public"."system_config" (
  "id" int4 NOT NULL DEFAULT nextval('system_config_id_seq'::regclass),
  "key" varchar(100) COLLATE "pg_catalog"."default" NOT NULL,
  "value" varchar(500) COLLATE "pg_catalog"."default" NOT NULL,
  "description" varchar(500) COLLATE "pg_catalog"."default",
  "updated_by" varchar(100) COLLATE "pg_catalog"."default",
  "updated_at" timestamp(6) DEFAULT CURRENT_TIMESTAMP
)
;

-- ----------------------------
-- Table structure for task_outbox
-- ----------------------------
DROP TABLE IF EXISTS "public"."task_outbox";
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

-- ----------------------------
-- Table structure for test_connection
-- ----------------------------
DROP TABLE IF EXISTS "public"."test_connection";
CREATE TABLE "public"."test_connection" (
  "id" uuid NOT NULL DEFAULT uuid_generate_v4(),
  "name" varchar(100) COLLATE "pg_catalog"."default" NOT NULL,
  "created_at" timestamptz(6) DEFAULT now()
)
;

-- ----------------------------
-- Table structure for tiku_ai_parse_result
-- ----------------------------
DROP TABLE IF EXISTS "public"."tiku_ai_parse_result";
CREATE TABLE "public"."tiku_ai_parse_result" (
  "id" int8 NOT NULL GENERATED BY DEFAULT AS IDENTITY (
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1
),
  "model_name" varchar(100) COLLATE "pg_catalog"."default" NOT NULL,
  "prompt_version" varchar(50) COLLATE "pg_catalog"."default",
  "request_json" jsonb,
  "response_json" jsonb,
  "raw_response" text COLLATE "pg_catalog"."default",
  "is_valid_json" bool NOT NULL,
  "error_message" text COLLATE "pg_catalog"."default",
  "latency_ms" int4,
  "created_at" timestamptz(6) NOT NULL,
  "paper_id" int8 NOT NULL,
  "page_id" int8
)
;

-- ----------------------------
-- Table structure for tiku_exam_page
-- ----------------------------
DROP TABLE IF EXISTS "public"."tiku_exam_page";
CREATE TABLE "public"."tiku_exam_page" (
  "id" int8 NOT NULL GENERATED BY DEFAULT AS IDENTITY (
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1
),
  "page_no" int4 NOT NULL,
  "image_path" varchar(500) COLLATE "pg_catalog"."default" NOT NULL,
  "width" int4,
  "height" int4,
  "ocr_text" text COLLATE "pg_catalog"."default",
  "layout_json" jsonb,
  "parse_status" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "ai_confidence" numeric(5,4),
  "created_at" timestamptz(6) NOT NULL,
  "updated_at" timestamptz(6) NOT NULL,
  "paper_id" int8 NOT NULL
)
;

-- ----------------------------
-- Table structure for tiku_exam_paper
-- ----------------------------
DROP TABLE IF EXISTS "public"."tiku_exam_paper";
CREATE TABLE "public"."tiku_exam_paper" (
  "id" int8 NOT NULL GENERATED BY DEFAULT AS IDENTITY (
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1
),
  "title" varchar(255) COLLATE "pg_catalog"."default" NOT NULL,
  "subject" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "stage" varchar(50) COLLATE "pg_catalog"."default",
  "grade" varchar(50) COLLATE "pg_catalog"."default",
  "paper_type" varchar(50) COLLATE "pg_catalog"."default",
  "has_solution" bool NOT NULL,
  "source_file_path" varchar(500) COLLATE "pg_catalog"."default" NOT NULL,
  "pdf_file_path" varchar(500) COLLATE "pg_catalog"."default",
  "total_pages" int4 NOT NULL,
  "total_questions" int4 NOT NULL,
  "status" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "error_message" text COLLATE "pg_catalog"."default",
  "created_at" timestamptz(6) NOT NULL,
  "updated_at" timestamptz(6) NOT NULL,
  "paper_code" varchar(20) COLLATE "pg_catalog"."default",
  "region" varchar(100) COLLATE "pg_catalog"."default",
  "is_deleted" bool NOT NULL,
  "creator_id" int8,
  "uploaded_by_id" int8
)
;

-- ----------------------------
-- Table structure for tiku_exam_question
-- ----------------------------
DROP TABLE IF EXISTS "public"."tiku_exam_question";
CREATE TABLE "public"."tiku_exam_question" (
  "id" int8 NOT NULL GENERATED BY DEFAULT AS IDENTITY (
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1
),
  "question_no" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "section_title" varchar(255) COLLATE "pg_catalog"."default",
  "question_type" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "subject" varchar(50) COLLATE "pg_catalog"."default",
  "stem" text COLLATE "pg_catalog"."default" NOT NULL,
  "stem_html" text COLLATE "pg_catalog"."default",
  "answer" text COLLATE "pg_catalog"."default",
  "analysis" text COLLATE "pg_catalog"."default",
  "solution" text COLLATE "pg_catalog"."default",
  "comment" text COLLATE "pg_catalog"."default",
  "raw_explanation" text COLLATE "pg_catalog"."default",
  "raw_text" text COLLATE "pg_catalog"."default",
  "knowledge_points" jsonb,
  "difficulty" numeric(4,2),
  "page_start" int4,
  "page_end" int4,
  "bbox" jsonb,
  "region_json" jsonb,
  "sort_order" int4 NOT NULL,
  "confidence" numeric(5,4),
  "formula_need_review" bool NOT NULL,
  "need_review" bool NOT NULL,
  "review_status" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "parse_status" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "created_at" timestamptz(6) NOT NULL,
  "updated_at" timestamptz(6) NOT NULL,
  "original_question_id" int8,
  "paper_id" int8 NOT NULL,
  "parent_question_id" int8,
  "system_id" varchar(10) COLLATE "pg_catalog"."default",
  "paper_question_no" varchar(50) COLLATE "pg_catalog"."default",
  "ai_answer_a" jsonb,
  "ai_answer_b" jsonb,
  "ai_answer_c" jsonb,
  "ai_knowledge_enrichment" jsonb,
  "ai_probe_result" jsonb,
  "ai_vision_extract" jsonb,
  "ai_verifier_result" jsonb,
  "ai_processed_at" timestamptz(6),
  "ai_processing_status" varchar(20) COLLATE "pg_catalog"."default" NOT NULL
)
;

-- ----------------------------
-- Table structure for tiku_favorite
-- ----------------------------
DROP TABLE IF EXISTS "public"."tiku_favorite";
CREATE TABLE "public"."tiku_favorite" (
  "id" int8 NOT NULL GENERATED BY DEFAULT AS IDENTITY (
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1
),
  "user_id" int8 NOT NULL,
  "question_id" int4 NOT NULL,
  "created_at" timestamptz(6) NOT NULL
)
;

-- ----------------------------
-- Table structure for tiku_paper_code_counter
-- ----------------------------
DROP TABLE IF EXISTS "public"."tiku_paper_code_counter";
CREATE TABLE "public"."tiku_paper_code_counter" (
  "id" int8 NOT NULL GENERATED BY DEFAULT AS IDENTITY (
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1
),
  "letter" varchar(1) COLLATE "pg_catalog"."default" NOT NULL,
  "grade_char" varchar(1) COLLATE "pg_catalog"."default" NOT NULL,
  "next_seq" int4 NOT NULL
)
;

-- ----------------------------
-- Table structure for tiku_parse_task
-- ----------------------------
DROP TABLE IF EXISTS "public"."tiku_parse_task";
CREATE TABLE "public"."tiku_parse_task" (
  "id" int8 NOT NULL GENERATED BY DEFAULT AS IDENTITY (
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1
),
  "task_type" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "status" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "progress" int4 NOT NULL,
  "current_step" varchar(255) COLLATE "pg_catalog"."default",
  "error_message" text COLLATE "pg_catalog"."default",
  "retry_count" int4 NOT NULL,
  "celery_task_id" varchar(255) COLLATE "pg_catalog"."default",
  "started_at" timestamptz(6),
  "finished_at" timestamptz(6),
  "created_at" timestamptz(6) NOT NULL,
  "updated_at" timestamptz(6) NOT NULL,
  "paper_id" int8 NOT NULL,
  "question_id" int8
)
;

-- ----------------------------
-- Table structure for tiku_question_id_counter
-- ----------------------------
DROP TABLE IF EXISTS "public"."tiku_question_id_counter";
CREATE TABLE "public"."tiku_question_id_counter" (
  "id" int8 NOT NULL GENERATED BY DEFAULT AS IDENTITY (
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1
),
  "subject" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "next_seq" int4 NOT NULL
)
;

-- ----------------------------
-- Table structure for tiku_question_image
-- ----------------------------
DROP TABLE IF EXISTS "public"."tiku_question_image";
CREATE TABLE "public"."tiku_question_image" (
  "id" int8 NOT NULL GENERATED BY DEFAULT AS IDENTITY (
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1
),
  "image_type" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "file_path" varchar(500) COLLATE "pg_catalog"."default" NOT NULL,
  "source_page_image_path" varchar(500) COLLATE "pg_catalog"."default",
  "bbox" jsonb,
  "expanded_bbox" jsonb,
  "description" varchar(500) COLLATE "pg_catalog"."default",
  "sort_order" int4 NOT NULL,
  "created_at" timestamptz(6) NOT NULL,
  "page_id" int8,
  "paper_id" int8 NOT NULL,
  "question_id" int8 NOT NULL
)
;

-- ----------------------------
-- Table structure for tiku_question_option
-- ----------------------------
DROP TABLE IF EXISTS "public"."tiku_question_option";
CREATE TABLE "public"."tiku_question_option" (
  "id" int8 NOT NULL GENERATED BY DEFAULT AS IDENTITY (
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1
),
  "option_label" varchar(10) COLLATE "pg_catalog"."default" NOT NULL,
  "content" text COLLATE "pg_catalog"."default" NOT NULL,
  "content_html" text COLLATE "pg_catalog"."default",
  "bbox" jsonb,
  "sort_order" int4 NOT NULL,
  "created_at" timestamptz(6) NOT NULL,
  "updated_at" timestamptz(6) NOT NULL,
  "question_id" int8 NOT NULL
)
;

-- ----------------------------
-- Table structure for tiku_teacher_favorite
-- ----------------------------
DROP TABLE IF EXISTS "public"."tiku_teacher_favorite";
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

-- ----------------------------
-- Table structure for tiku_teacher_profile
-- ----------------------------
DROP TABLE IF EXISTS "public"."tiku_teacher_profile";
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

-- ----------------------------
-- Table structure for user_account
-- ----------------------------
DROP TABLE IF EXISTS "public"."user_account";
CREATE TABLE "public"."user_account" (
  "id" int8 NOT NULL GENERATED BY DEFAULT AS IDENTITY (
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1
),
  "role_type" varchar(20) COLLATE "pg_catalog"."default" NOT NULL,
  "login_name" varchar(64) COLLATE "pg_catalog"."default",
  "mobile" varchar(20) COLLATE "pg_catalog"."default" NOT NULL,
  "display_name" varchar(64) COLLATE "pg_catalog"."default" NOT NULL,
  "avatar_url" varchar(255) COLLATE "pg_catalog"."default",
  "status" varchar(20) COLLATE "pg_catalog"."default" NOT NULL,
  "created_at" timestamptz(6) NOT NULL,
  "updated_at" timestamptz(6) NOT NULL,
  "last_login" timestamptz(6),
  "password" varchar(128) COLLATE "pg_catalog"."default" NOT NULL,
  "subject" varchar(20) COLLATE "pg_catalog"."default",
  "stages" jsonb,
  "grade_level" varchar(20) COLLATE "pg_catalog"."default"
)
;

-- ----------------------------
-- Table structure for users
-- ----------------------------
DROP TABLE IF EXISTS "public"."users";
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

-- ----------------------------
-- Table structure for wrong_book_item
-- ----------------------------
DROP TABLE IF EXISTS "public"."wrong_book_item";
CREATE TABLE "public"."wrong_book_item" (
  "id" int8 NOT NULL GENERATED BY DEFAULT AS IDENTITY (
INCREMENT 1
MINVALUE  1
MAXVALUE 9223372036854775807
START 1
CACHE 1
),
  "question_id" int4 NOT NULL,
  "first_wrong_at" timestamptz(6) NOT NULL,
  "latest_wrong_at" timestamptz(6) NOT NULL,
  "wrong_reason_type" varchar(30) COLLATE "pg_catalog"."default",
  "status" varchar(20) COLLATE "pg_catalog"."default" NOT NULL,
  "retry_count" int4 NOT NULL,
  "variant_done_count" int4 NOT NULL,
  "student_user_id_id" int8 NOT NULL
)
;

-- ----------------------------
-- Function structure for uuid_generate_v1
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."uuid_generate_v1"();
CREATE OR REPLACE FUNCTION "public"."uuid_generate_v1"()
  RETURNS "pg_catalog"."uuid" AS '$libdir/uuid-ossp', 'uuid_generate_v1'
  LANGUAGE c VOLATILE STRICT
  COST 1;

-- ----------------------------
-- Function structure for uuid_generate_v1mc
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."uuid_generate_v1mc"();
CREATE OR REPLACE FUNCTION "public"."uuid_generate_v1mc"()
  RETURNS "pg_catalog"."uuid" AS '$libdir/uuid-ossp', 'uuid_generate_v1mc'
  LANGUAGE c VOLATILE STRICT
  COST 1;

-- ----------------------------
-- Function structure for uuid_generate_v3
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."uuid_generate_v3"("namespace" uuid, "name" text);
CREATE OR REPLACE FUNCTION "public"."uuid_generate_v3"("namespace" uuid, "name" text)
  RETURNS "pg_catalog"."uuid" AS '$libdir/uuid-ossp', 'uuid_generate_v3'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for uuid_generate_v4
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."uuid_generate_v4"();
CREATE OR REPLACE FUNCTION "public"."uuid_generate_v4"()
  RETURNS "pg_catalog"."uuid" AS '$libdir/uuid-ossp', 'uuid_generate_v4'
  LANGUAGE c VOLATILE STRICT
  COST 1;

-- ----------------------------
-- Function structure for uuid_generate_v5
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."uuid_generate_v5"("namespace" uuid, "name" text);
CREATE OR REPLACE FUNCTION "public"."uuid_generate_v5"("namespace" uuid, "name" text)
  RETURNS "pg_catalog"."uuid" AS '$libdir/uuid-ossp', 'uuid_generate_v5'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for uuid_nil
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."uuid_nil"();
CREATE OR REPLACE FUNCTION "public"."uuid_nil"()
  RETURNS "pg_catalog"."uuid" AS '$libdir/uuid-ossp', 'uuid_nil'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for uuid_ns_dns
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."uuid_ns_dns"();
CREATE OR REPLACE FUNCTION "public"."uuid_ns_dns"()
  RETURNS "pg_catalog"."uuid" AS '$libdir/uuid-ossp', 'uuid_ns_dns'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for uuid_ns_oid
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."uuid_ns_oid"();
CREATE OR REPLACE FUNCTION "public"."uuid_ns_oid"()
  RETURNS "pg_catalog"."uuid" AS '$libdir/uuid-ossp', 'uuid_ns_oid'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for uuid_ns_url
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."uuid_ns_url"();
CREATE OR REPLACE FUNCTION "public"."uuid_ns_url"()
  RETURNS "pg_catalog"."uuid" AS '$libdir/uuid-ossp', 'uuid_ns_url'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Function structure for uuid_ns_x500
-- ----------------------------
DROP FUNCTION IF EXISTS "public"."uuid_ns_x500"();
CREATE OR REPLACE FUNCTION "public"."uuid_ns_x500"()
  RETURNS "pg_catalog"."uuid" AS '$libdir/uuid-ossp', 'uuid_ns_x500'
  LANGUAGE c IMMUTABLE STRICT
  COST 1;

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."ai_guidance_session_id_seq"
OWNED BY "public"."ai_guidance_session"."id";
SELECT setval('"public"."ai_guidance_session_id_seq"', 5, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."ai_parse_result_id_seq"
OWNED BY "public"."tiku_ai_parse_result"."id";
SELECT setval('"public"."ai_parse_result_id_seq"', 99, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."alert_logs_id_seq"
OWNED BY "public"."alert_logs"."id";
SELECT setval('"public"."alert_logs_id_seq"', 1, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."answer_attempt_id_seq"
OWNED BY "public"."answer_attempt"."id";
SELECT setval('"public"."answer_attempt_id_seq"', 2, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."api_task_logs_id_seq"
OWNED BY "public"."api_task_logs"."id";
SELECT setval('"public"."api_task_logs_id_seq"', 1567, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."auth_group_id_seq"
OWNED BY "public"."auth_group"."id";
SELECT setval('"public"."auth_group_id_seq"', 1, false);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."auth_group_permissions_id_seq"
OWNED BY "public"."auth_group_permissions"."id";
SELECT setval('"public"."auth_group_permissions_id_seq"', 1, false);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."auth_permission_id_seq"
OWNED BY "public"."auth_permission"."id";
SELECT setval('"public"."auth_permission_id_seq"', 164, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."auth_user_groups_id_seq"
OWNED BY "public"."auth_user_groups"."id";
SELECT setval('"public"."auth_user_groups_id_seq"', 1, false);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."auth_user_id_seq"
OWNED BY "public"."auth_user"."id";
SELECT setval('"public"."auth_user_id_seq"', 1, false);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."auth_user_user_permissions_id_seq"
OWNED BY "public"."auth_user_user_permissions"."id";
SELECT setval('"public"."auth_user_user_permissions_id_seq"', 1, false);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."class_id_seq"
OWNED BY "public"."class"."id";
SELECT setval('"public"."class_id_seq"', 5, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."class_join_request_id_seq"
OWNED BY "public"."class_join_request"."id";
SELECT setval('"public"."class_join_request_id_seq"', 1, false);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."class_student_id_seq"
OWNED BY "public"."class_student"."id";
SELECT setval('"public"."class_student_id_seq"', 2, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."class_teacher_id_seq"
OWNED BY "public"."class_teacher"."id";
SELECT setval('"public"."class_teacher_id_seq"', 4, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."course_id_seq"
OWNED BY "public"."course"."id";
SELECT setval('"public"."course_id_seq"', 1, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."course_material_id_seq"
OWNED BY "public"."course_material"."id";
SELECT setval('"public"."course_material_id_seq"', 3, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."course_question_link_id_seq"
OWNED BY "public"."course_question_link"."id";
SELECT setval('"public"."course_question_link_id_seq"', 1, false);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."course_tree_id_seq"
OWNED BY "public"."course_tree"."id";
SELECT setval('"public"."course_tree_id_seq"', 5, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."course_variant_task_id_seq"
OWNED BY "public"."course_variant_task"."id";
SELECT setval('"public"."course_variant_task_id_seq"', 1, false);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."django_admin_log_id_seq"
OWNED BY "public"."django_admin_log"."id";
SELECT setval('"public"."django_admin_log_id_seq"', 1, false);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."django_content_type_id_seq"
OWNED BY "public"."django_content_type"."id";
SELECT setval('"public"."django_content_type_id_seq"', 41, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."django_migrations_id_seq"
OWNED BY "public"."django_migrations"."id";
SELECT setval('"public"."django_migrations_id_seq"', 50, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."dlq_messages_id_seq"
OWNED BY "public"."dlq_messages"."id";
SELECT setval('"public"."dlq_messages_id_seq"', 1, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."exam_page_id_seq"
OWNED BY "public"."tiku_exam_page"."id";
SELECT setval('"public"."exam_page_id_seq"', 102, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."exam_question_id_seq"
OWNED BY "public"."tiku_exam_question"."id";
SELECT setval('"public"."exam_question_id_seq"', 76, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."gemini_results_id_seq"
OWNED BY "public"."gemini_results"."id";
SELECT setval('"public"."gemini_results_id_seq"', 1, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."institution_id_seq"
OWNED BY "public"."institution"."id";
SELECT setval('"public"."institution_id_seq"', 4, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."institution_member_id_seq"
OWNED BY "public"."institution_member"."id";
SELECT setval('"public"."institution_member_id_seq"', 10, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."learning_mission_id_seq"
OWNED BY "public"."learning_mission"."id";
SELECT setval('"public"."learning_mission_id_seq"', 7, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."llm_audit_id_seq"
OWNED BY "public"."llm_audit"."id";
SELECT setval('"public"."llm_audit_id_seq"', 1, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."mastery_record_id_seq"
OWNED BY "public"."mastery_record"."id";
SELECT setval('"public"."mastery_record_id_seq"', 1, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."mission_level_id_seq"
OWNED BY "public"."mission_level"."id";
SELECT setval('"public"."mission_level_id_seq"', 10, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."mission_question_rel_id_seq"
OWNED BY "public"."mission_question_rel"."id";
SELECT setval('"public"."mission_question_rel_id_seq"', 30, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."monitoring_metrics_id_seq"
OWNED BY "public"."monitoring_metrics"."id";
SELECT setval('"public"."monitoring_metrics_id_seq"', 1, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."problem_results_id_seq"
OWNED BY "public"."problem_results"."id";
SELECT setval('"public"."problem_results_id_seq"', 1, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."problems_id_seq"
OWNED BY "public"."problems"."id";
SELECT setval('"public"."problems_id_seq"', 5, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."question_image_id_seq"
OWNED BY "public"."tiku_question_image"."id";
SELECT setval('"public"."question_image_id_seq"', 113, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."question_option_id_seq"
OWNED BY "public"."tiku_question_option"."id";
SELECT setval('"public"."question_option_id_seq"', 112, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."retry_queue_id_seq"
OWNED BY "public"."retry_queue"."id";
SELECT setval('"public"."retry_queue_id_seq"', 1, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."rollback_logs_id_seq"
OWNED BY "public"."rollback_logs"."id";
SELECT setval('"public"."rollback_logs_id_seq"', 1, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."student_level_progress_id_seq"
OWNED BY "public"."student_level_progress"."id";
SELECT setval('"public"."student_level_progress_id_seq"', 1, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."student_mission_progress_id_seq"
OWNED BY "public"."student_mission_progress"."id";
SELECT setval('"public"."student_mission_progress_id_seq"', 1, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."student_parent_bind_id_seq"
OWNED BY "public"."student_parent_bind"."id";
SELECT setval('"public"."student_parent_bind_id_seq"', 1, false);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."system_config_id_seq"
OWNED BY "public"."system_config"."id";
SELECT setval('"public"."system_config_id_seq"', 9, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."task_outbox_id_seq"
OWNED BY "public"."task_outbox"."id";
SELECT setval('"public"."task_outbox_id_seq"', 1, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."tiku_exam_paper_id_seq"
OWNED BY "public"."tiku_exam_paper"."id";
SELECT setval('"public"."tiku_exam_paper_id_seq"', 24, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."tiku_favorite_id_seq"
OWNED BY "public"."tiku_favorite"."id";
SELECT setval('"public"."tiku_favorite_id_seq"', 5, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."tiku_paper_code_counter_id_seq"
OWNED BY "public"."tiku_paper_code_counter"."id";
SELECT setval('"public"."tiku_paper_code_counter_id_seq"', 3, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."tiku_parse_task_id_seq"
OWNED BY "public"."tiku_parse_task"."id";
SELECT setval('"public"."tiku_parse_task_id_seq"', 34, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."tiku_question_id_counter_id_seq"
OWNED BY "public"."tiku_question_id_counter"."id";
SELECT setval('"public"."tiku_question_id_counter_id_seq"', 3, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."tiku_teacher_favorite_id_seq"
OWNED BY "public"."tiku_teacher_favorite"."id";
SELECT setval('"public"."tiku_teacher_favorite_id_seq"', 1, false);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."tiku_teacher_profile_id_seq"
OWNED BY "public"."tiku_teacher_profile"."id";
SELECT setval('"public"."tiku_teacher_profile_id_seq"', 1, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."user_account_id_seq"
OWNED BY "public"."user_account"."id";
SELECT setval('"public"."user_account_id_seq"', 14, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."users_id_seq"
OWNED BY "public"."users"."id";
SELECT setval('"public"."users_id_seq"', 8, true);

-- ----------------------------
-- Alter sequences owned by
-- ----------------------------
ALTER SEQUENCE "public"."wrong_book_item_id_seq"
OWNED BY "public"."wrong_book_item"."id";
SELECT setval('"public"."wrong_book_item_id_seq"', 3, true);

-- ----------------------------
-- Indexes structure for table ai_guidance_session
-- ----------------------------
CREATE INDEX "ai_guidance_session_student_user_id_id_35f0c5eb" ON "public"."ai_guidance_session" USING btree (
  "student_user_id_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table ai_guidance_session
-- ----------------------------
ALTER TABLE "public"."ai_guidance_session" ADD CONSTRAINT "ai_guidance_session_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table alert_logs
-- ----------------------------
CREATE INDEX "idx_al_level" ON "public"."alert_logs" USING btree (
  "level" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_al_sent_at" ON "public"."alert_logs" USING btree (
  "sent_at" "pg_catalog"."timestamp_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table alert_logs
-- ----------------------------
ALTER TABLE "public"."alert_logs" ADD CONSTRAINT "alert_logs_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table answer_attempt
-- ----------------------------
CREATE INDEX "answer_attempt_level_id_48e1cfa6" ON "public"."answer_attempt" USING btree (
  "level_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);
CREATE INDEX "answer_attempt_mission_id_c743e0cb" ON "public"."answer_attempt" USING btree (
  "mission_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);
CREATE INDEX "answer_attempt_student_user_id_id_2ca881b1" ON "public"."answer_attempt" USING btree (
  "student_user_id_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table answer_attempt
-- ----------------------------
ALTER TABLE "public"."answer_attempt" ADD CONSTRAINT "answer_attempt_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table api_task_logs
-- ----------------------------
CREATE INDEX "idx_atl_error_classification" ON "public"."api_task_logs" USING btree (
  "error_classification" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_atl_finished_at" ON "public"."api_task_logs" USING btree (
  "finished_at" "pg_catalog"."timestamp_ops" ASC NULLS LAST
);
CREATE INDEX "idx_atl_mode" ON "public"."api_task_logs" USING btree (
  "mode" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_atl_next_retry_at" ON "public"."api_task_logs" USING btree (
  "next_retry_at" "pg_catalog"."timestamp_ops" ASC NULLS LAST
);
CREATE INDEX "idx_atl_problem_id" ON "public"."api_task_logs" USING btree (
  "problem_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);
CREATE INDEX "idx_atl_retry_count" ON "public"."api_task_logs" USING btree (
  "retry_count" "pg_catalog"."int2_ops" ASC NULLS LAST
);
CREATE INDEX "idx_atl_started_at" ON "public"."api_task_logs" USING btree (
  "started_at" "pg_catalog"."timestamp_ops" ASC NULLS LAST
);
CREATE INDEX "idx_atl_status" ON "public"."api_task_logs" USING btree (
  "status" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_atl_status_retry_next" ON "public"."api_task_logs" USING btree (
  "status" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST,
  "retry_count" "pg_catalog"."int2_ops" ASC NULLS LAST,
  "next_retry_at" "pg_catalog"."timestamp_ops" ASC NULLS LAST
);
CREATE INDEX "idx_atl_status_task_type" ON "public"."api_task_logs" USING btree (
  "status" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST,
  "task_type" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_atl_task_type" ON "public"."api_task_logs" USING btree (
  "task_type" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_atl_trace_id" ON "public"."api_task_logs" USING btree (
  "trace_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_atl_user_id" ON "public"."api_task_logs" USING btree (
  "user_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);

-- ----------------------------
-- Uniques structure for table api_task_logs
-- ----------------------------
ALTER TABLE "public"."api_task_logs" ADD CONSTRAINT "api_task_logs_task_id_key" UNIQUE ("task_id");

-- ----------------------------
-- Primary Key structure for table api_task_logs
-- ----------------------------
ALTER TABLE "public"."api_task_logs" ADD CONSTRAINT "api_task_logs_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table auth_group
-- ----------------------------
CREATE INDEX "auth_group_name_a6ea08ec_like" ON "public"."auth_group" USING btree (
  "name" COLLATE "pg_catalog"."default" "pg_catalog"."varchar_pattern_ops" ASC NULLS LAST
);

-- ----------------------------
-- Uniques structure for table auth_group
-- ----------------------------
ALTER TABLE "public"."auth_group" ADD CONSTRAINT "auth_group_name_key" UNIQUE ("name");

-- ----------------------------
-- Primary Key structure for table auth_group
-- ----------------------------
ALTER TABLE "public"."auth_group" ADD CONSTRAINT "auth_group_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table auth_group_permissions
-- ----------------------------
CREATE INDEX "auth_group_permissions_group_id_b120cbf9" ON "public"."auth_group_permissions" USING btree (
  "group_id" "pg_catalog"."int4_ops" ASC NULLS LAST
);
CREATE INDEX "auth_group_permissions_permission_id_84c5c92e" ON "public"."auth_group_permissions" USING btree (
  "permission_id" "pg_catalog"."int4_ops" ASC NULLS LAST
);

-- ----------------------------
-- Uniques structure for table auth_group_permissions
-- ----------------------------
ALTER TABLE "public"."auth_group_permissions" ADD CONSTRAINT "auth_group_permissions_group_id_permission_id_0cd325b0_uniq" UNIQUE ("group_id", "permission_id");

-- ----------------------------
-- Primary Key structure for table auth_group_permissions
-- ----------------------------
ALTER TABLE "public"."auth_group_permissions" ADD CONSTRAINT "auth_group_permissions_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table auth_permission
-- ----------------------------
CREATE INDEX "auth_permission_content_type_id_2f476e4b" ON "public"."auth_permission" USING btree (
  "content_type_id" "pg_catalog"."int4_ops" ASC NULLS LAST
);

-- ----------------------------
-- Uniques structure for table auth_permission
-- ----------------------------
ALTER TABLE "public"."auth_permission" ADD CONSTRAINT "auth_permission_content_type_id_codename_01ab375a_uniq" UNIQUE ("content_type_id", "codename");

-- ----------------------------
-- Primary Key structure for table auth_permission
-- ----------------------------
ALTER TABLE "public"."auth_permission" ADD CONSTRAINT "auth_permission_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table auth_user
-- ----------------------------
CREATE INDEX "auth_user_username_6821ab7c_like" ON "public"."auth_user" USING btree (
  "username" COLLATE "pg_catalog"."default" "pg_catalog"."varchar_pattern_ops" ASC NULLS LAST
);

-- ----------------------------
-- Uniques structure for table auth_user
-- ----------------------------
ALTER TABLE "public"."auth_user" ADD CONSTRAINT "auth_user_username_key" UNIQUE ("username");

-- ----------------------------
-- Primary Key structure for table auth_user
-- ----------------------------
ALTER TABLE "public"."auth_user" ADD CONSTRAINT "auth_user_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table auth_user_groups
-- ----------------------------
CREATE INDEX "auth_user_groups_group_id_97559544" ON "public"."auth_user_groups" USING btree (
  "group_id" "pg_catalog"."int4_ops" ASC NULLS LAST
);
CREATE INDEX "auth_user_groups_user_id_6a12ed8b" ON "public"."auth_user_groups" USING btree (
  "user_id" "pg_catalog"."int4_ops" ASC NULLS LAST
);

-- ----------------------------
-- Uniques structure for table auth_user_groups
-- ----------------------------
ALTER TABLE "public"."auth_user_groups" ADD CONSTRAINT "auth_user_groups_user_id_group_id_94350c0c_uniq" UNIQUE ("user_id", "group_id");

-- ----------------------------
-- Primary Key structure for table auth_user_groups
-- ----------------------------
ALTER TABLE "public"."auth_user_groups" ADD CONSTRAINT "auth_user_groups_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table auth_user_user_permissions
-- ----------------------------
CREATE INDEX "auth_user_user_permissions_permission_id_1fbb5f2c" ON "public"."auth_user_user_permissions" USING btree (
  "permission_id" "pg_catalog"."int4_ops" ASC NULLS LAST
);
CREATE INDEX "auth_user_user_permissions_user_id_a95ead1b" ON "public"."auth_user_user_permissions" USING btree (
  "user_id" "pg_catalog"."int4_ops" ASC NULLS LAST
);

-- ----------------------------
-- Uniques structure for table auth_user_user_permissions
-- ----------------------------
ALTER TABLE "public"."auth_user_user_permissions" ADD CONSTRAINT "auth_user_user_permissions_user_id_permission_id_14a6b632_uniq" UNIQUE ("user_id", "permission_id");

-- ----------------------------
-- Primary Key structure for table auth_user_user_permissions
-- ----------------------------
ALTER TABLE "public"."auth_user_user_permissions" ADD CONSTRAINT "auth_user_user_permissions_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table class
-- ----------------------------
CREATE INDEX "class_class_no_af22b5a1_like" ON "public"."class" USING btree (
  "class_no" COLLATE "pg_catalog"."default" "pg_catalog"."varchar_pattern_ops" ASC NULLS LAST
);
CREATE INDEX "class_creator_teacher_id_7a6558ab" ON "public"."class" USING btree (
  "creator_teacher_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);
CREATE INDEX "class_institution_id_27903dc7" ON "public"."class" USING btree (
  "institution_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);
CREATE INDEX "class_invite_code_12c04c15_like" ON "public"."class" USING btree (
  "invite_code" COLLATE "pg_catalog"."default" "pg_catalog"."varchar_pattern_ops" ASC NULLS LAST
);

-- ----------------------------
-- Uniques structure for table class
-- ----------------------------
ALTER TABLE "public"."class" ADD CONSTRAINT "class_class_no_key" UNIQUE ("class_no");
ALTER TABLE "public"."class" ADD CONSTRAINT "class_invite_code_key" UNIQUE ("invite_code");

-- ----------------------------
-- Primary Key structure for table class
-- ----------------------------
ALTER TABLE "public"."class" ADD CONSTRAINT "class_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table class_join_request
-- ----------------------------
CREATE INDEX "class_join_request_applicant_id_6808a15f" ON "public"."class_join_request" USING btree (
  "applicant_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);
CREATE INDEX "class_join_request_class_id_0db05907" ON "public"."class_join_request" USING btree (
  "class_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);
CREATE INDEX "class_join_request_handled_by_id_6da7c4f5" ON "public"."class_join_request" USING btree (
  "handled_by_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table class_join_request
-- ----------------------------
ALTER TABLE "public"."class_join_request" ADD CONSTRAINT "class_join_request_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table class_student
-- ----------------------------
CREATE INDEX "class_student_class_id_aac5f036" ON "public"."class_student" USING btree (
  "class_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);
CREATE INDEX "class_student_student_id_b3a11024" ON "public"."class_student" USING btree (
  "student_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);

-- ----------------------------
-- Uniques structure for table class_student
-- ----------------------------
ALTER TABLE "public"."class_student" ADD CONSTRAINT "class_student_class_id_student_id_34cde5d1_uniq" UNIQUE ("class_id", "student_id");

-- ----------------------------
-- Primary Key structure for table class_student
-- ----------------------------
ALTER TABLE "public"."class_student" ADD CONSTRAINT "class_student_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table class_teacher
-- ----------------------------
CREATE INDEX "class_teacher_class_id_27aef63d" ON "public"."class_teacher" USING btree (
  "class_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);
CREATE INDEX "class_teacher_teacher_id_4e089a1e" ON "public"."class_teacher" USING btree (
  "teacher_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);

-- ----------------------------
-- Uniques structure for table class_teacher
-- ----------------------------
ALTER TABLE "public"."class_teacher" ADD CONSTRAINT "class_teacher_class_id_teacher_id_3022953b_uniq" UNIQUE ("class_id", "teacher_id");

-- ----------------------------
-- Primary Key structure for table class_teacher
-- ----------------------------
ALTER TABLE "public"."class_teacher" ADD CONSTRAINT "class_teacher_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table course
-- ----------------------------
CREATE INDEX "course_teacher_id_b694c4f5" ON "public"."course" USING btree (
  "teacher_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table course
-- ----------------------------
ALTER TABLE "public"."course" ADD CONSTRAINT "course_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table course_material
-- ----------------------------
CREATE INDEX "course_material_course_id_e3866b9f" ON "public"."course_material" USING btree (
  "course_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);
CREATE INDEX "course_material_uploaded_by_id_de650306" ON "public"."course_material" USING btree (
  "uploaded_by_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table course_material
-- ----------------------------
ALTER TABLE "public"."course_material" ADD CONSTRAINT "course_material_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table course_question_link
-- ----------------------------
CREATE INDEX "course_question_link_course_id_969244a2" ON "public"."course_question_link" USING btree (
  "course_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);
CREATE INDEX "course_question_link_question_id_86f1a9f6" ON "public"."course_question_link" USING btree (
  "question_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);
CREATE INDEX "course_question_link_tree_node_id_ae40e3c8" ON "public"."course_question_link" USING btree (
  "tree_node_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);

-- ----------------------------
-- Uniques structure for table course_question_link
-- ----------------------------
ALTER TABLE "public"."course_question_link" ADD CONSTRAINT "course_question_link_course_id_question_id_e018ba11_uniq" UNIQUE ("course_id", "question_id");

-- ----------------------------
-- Primary Key structure for table course_question_link
-- ----------------------------
ALTER TABLE "public"."course_question_link" ADD CONSTRAINT "course_question_link_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table course_tree
-- ----------------------------
CREATE INDEX "course_tree_course_id_3d6c0495" ON "public"."course_tree" USING btree (
  "course_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);
CREATE INDEX "course_tree_parent_id_fae96f5d" ON "public"."course_tree" USING btree (
  "parent_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table course_tree
-- ----------------------------
ALTER TABLE "public"."course_tree" ADD CONSTRAINT "course_tree_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table course_variant_task
-- ----------------------------
CREATE INDEX "course_variant_task_original_question_id_5b5d7825" ON "public"."course_variant_task" USING btree (
  "original_question_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table course_variant_task
-- ----------------------------
ALTER TABLE "public"."course_variant_task" ADD CONSTRAINT "course_variant_task_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table django_admin_log
-- ----------------------------
CREATE INDEX "django_admin_log_content_type_id_c4bce8eb" ON "public"."django_admin_log" USING btree (
  "content_type_id" "pg_catalog"."int4_ops" ASC NULLS LAST
);
CREATE INDEX "django_admin_log_user_id_c564eba6" ON "public"."django_admin_log" USING btree (
  "user_id" "pg_catalog"."int4_ops" ASC NULLS LAST
);

-- ----------------------------
-- Checks structure for table django_admin_log
-- ----------------------------
ALTER TABLE "public"."django_admin_log" ADD CONSTRAINT "django_admin_log_action_flag_check" CHECK (action_flag >= 0);

-- ----------------------------
-- Primary Key structure for table django_admin_log
-- ----------------------------
ALTER TABLE "public"."django_admin_log" ADD CONSTRAINT "django_admin_log_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Uniques structure for table django_content_type
-- ----------------------------
ALTER TABLE "public"."django_content_type" ADD CONSTRAINT "django_content_type_app_label_model_76bd3d3b_uniq" UNIQUE ("app_label", "model");

-- ----------------------------
-- Primary Key structure for table django_content_type
-- ----------------------------
ALTER TABLE "public"."django_content_type" ADD CONSTRAINT "django_content_type_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table django_migrations
-- ----------------------------
ALTER TABLE "public"."django_migrations" ADD CONSTRAINT "django_migrations_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table django_session
-- ----------------------------
CREATE INDEX "django_session_expire_date_a5c62663" ON "public"."django_session" USING btree (
  "expire_date" "pg_catalog"."timestamptz_ops" ASC NULLS LAST
);
CREATE INDEX "django_session_session_key_c0390e0f_like" ON "public"."django_session" USING btree (
  "session_key" COLLATE "pg_catalog"."default" "pg_catalog"."varchar_pattern_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table django_session
-- ----------------------------
ALTER TABLE "public"."django_session" ADD CONSTRAINT "django_session_pkey" PRIMARY KEY ("session_key");

-- ----------------------------
-- Indexes structure for table dlq_messages
-- ----------------------------
CREATE INDEX "idx_dlq_entered_dlq_at" ON "public"."dlq_messages" USING btree (
  "entered_dlq_at" "pg_catalog"."timestamp_ops" ASC NULLS LAST
);
CREATE INDEX "idx_dlq_error_code" ON "public"."dlq_messages" USING btree (
  "error_code" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_dlq_status" ON "public"."dlq_messages" USING btree (
  "status" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_dlq_task_id" ON "public"."dlq_messages" USING btree (
  "task_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);

-- ----------------------------
-- Uniques structure for table dlq_messages
-- ----------------------------
ALTER TABLE "public"."dlq_messages" ADD CONSTRAINT "dlq_messages_task_id_key" UNIQUE ("task_id");

-- ----------------------------
-- Primary Key structure for table dlq_messages
-- ----------------------------
ALTER TABLE "public"."dlq_messages" ADD CONSTRAINT "dlq_messages_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table gemini_results
-- ----------------------------
CREATE INDEX "idx_gr_created_at" ON "public"."gemini_results" USING btree (
  "created_at" "pg_catalog"."timestamp_ops" ASC NULLS LAST
);
CREATE INDEX "idx_gr_task_id" ON "public"."gemini_results" USING btree (
  "task_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_gr_task_type" ON "public"."gemini_results" USING btree (
  "task_type" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_gr_user_id" ON "public"."gemini_results" USING btree (
  "user_id" "pg_catalog"."int4_ops" ASC NULLS LAST
);

-- ----------------------------
-- Uniques structure for table gemini_results
-- ----------------------------
ALTER TABLE "public"."gemini_results" ADD CONSTRAINT "gemini_results_task_id_key" UNIQUE ("task_id");

-- ----------------------------
-- Primary Key structure for table gemini_results
-- ----------------------------
ALTER TABLE "public"."gemini_results" ADD CONSTRAINT "gemini_results_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table institution
-- ----------------------------
CREATE INDEX "institution_created_by_id_9b8900f1" ON "public"."institution" USING btree (
  "created_by_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table institution
-- ----------------------------
ALTER TABLE "public"."institution" ADD CONSTRAINT "institution_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table institution_member
-- ----------------------------
CREATE INDEX "institution_member_institution_id_a8d35f11" ON "public"."institution_member" USING btree (
  "institution_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);
CREATE INDEX "institution_member_user_id_c0f0ef7a" ON "public"."institution_member" USING btree (
  "user_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);

-- ----------------------------
-- Uniques structure for table institution_member
-- ----------------------------
ALTER TABLE "public"."institution_member" ADD CONSTRAINT "institution_member_institution_id_user_id_3d314d76_uniq" UNIQUE ("institution_id", "user_id");

-- ----------------------------
-- Primary Key structure for table institution_member
-- ----------------------------
ALTER TABLE "public"."institution_member" ADD CONSTRAINT "institution_member_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table knowledge_points
-- ----------------------------
CREATE INDEX "idx_kp_module" ON "public"."knowledge_points" USING btree (
  "module" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_kp_subject" ON "public"."knowledge_points" USING btree (
  "subject" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table knowledge_points
-- ----------------------------
ALTER TABLE "public"."knowledge_points" ADD CONSTRAINT "knowledge_points_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table learning_mission
-- ----------------------------
CREATE INDEX "learning_mission_class_id_c2f8da19" ON "public"."learning_mission" USING btree (
  "class_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);
CREATE INDEX "learning_mission_creator_teacher_id_id_bdcbd33b" ON "public"."learning_mission" USING btree (
  "creator_teacher_id_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);
CREATE INDEX "learning_mission_mission_no_f3b14a3a_like" ON "public"."learning_mission" USING btree (
  "mission_no" COLLATE "pg_catalog"."default" "pg_catalog"."varchar_pattern_ops" ASC NULLS LAST
);

-- ----------------------------
-- Uniques structure for table learning_mission
-- ----------------------------
ALTER TABLE "public"."learning_mission" ADD CONSTRAINT "learning_mission_mission_no_key" UNIQUE ("mission_no");

-- ----------------------------
-- Primary Key structure for table learning_mission
-- ----------------------------
ALTER TABLE "public"."learning_mission" ADD CONSTRAINT "learning_mission_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table llm_audit
-- ----------------------------
CREATE INDEX "idx_la_created_at" ON "public"."llm_audit" USING btree (
  "created_at" "pg_catalog"."timestamp_ops" ASC NULLS LAST
);
CREATE INDEX "idx_la_model_name" ON "public"."llm_audit" USING btree (
  "model_name" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_la_status" ON "public"."llm_audit" USING btree (
  "status" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_la_task_id" ON "public"."llm_audit" USING btree (
  "task_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_la_trace_id" ON "public"."llm_audit" USING btree (
  "trace_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table llm_audit
-- ----------------------------
ALTER TABLE "public"."llm_audit" ADD CONSTRAINT "llm_audit_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table mastery_record
-- ----------------------------
CREATE INDEX "mastery_record_student_user_id_id_e99c8a50" ON "public"."mastery_record" USING btree (
  "student_user_id_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table mastery_record
-- ----------------------------
ALTER TABLE "public"."mastery_record" ADD CONSTRAINT "mastery_record_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table mission_level
-- ----------------------------
CREATE INDEX "mission_level_mission_id_838fe8ff" ON "public"."mission_level" USING btree (
  "mission_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table mission_level
-- ----------------------------
ALTER TABLE "public"."mission_level" ADD CONSTRAINT "mission_level_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table mission_question_rel
-- ----------------------------
CREATE INDEX "mission_question_rel_level_id_32b565b1" ON "public"."mission_question_rel" USING btree (
  "level_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);
CREATE INDEX "mission_question_rel_mission_id_350a17b0" ON "public"."mission_question_rel" USING btree (
  "mission_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table mission_question_rel
-- ----------------------------
ALTER TABLE "public"."mission_question_rel" ADD CONSTRAINT "mission_question_rel_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table monitoring_metrics
-- ----------------------------
CREATE INDEX "idx_mm_metric_name" ON "public"."monitoring_metrics" USING btree (
  "metric_name" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_mm_recorded_at" ON "public"."monitoring_metrics" USING btree (
  "recorded_at" "pg_catalog"."timestamp_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table monitoring_metrics
-- ----------------------------
ALTER TABLE "public"."monitoring_metrics" ADD CONSTRAINT "monitoring_metrics_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table problem_results
-- ----------------------------
CREATE INDEX "idx_pr_created_at" ON "public"."problem_results" USING btree (
  "created_at" "pg_catalog"."timestamp_ops" ASC NULLS LAST
);
CREATE INDEX "idx_pr_mode" ON "public"."problem_results" USING btree (
  "mode" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_pr_norm_hash" ON "public"."problem_results" USING btree (
  "normalized_text_hash" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_pr_problem_id" ON "public"."problem_results" USING btree (
  "problem_id" "pg_catalog"."int4_ops" ASC NULLS LAST
);
CREATE INDEX "idx_pr_version_hash" ON "public"."problem_results" USING btree (
  "version_hash" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);

-- ----------------------------
-- Uniques structure for table problem_results
-- ----------------------------
ALTER TABLE "public"."problem_results" ADD CONSTRAINT "uk_problem_version" UNIQUE ("problem_id", "version_hash", "mode");

-- ----------------------------
-- Primary Key structure for table problem_results
-- ----------------------------
ALTER TABLE "public"."problem_results" ADD CONSTRAINT "problem_results_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table problems
-- ----------------------------
CREATE INDEX "idx_p_content_md5" ON "public"."problems" USING btree (
  "content_md5" COLLATE "pg_catalog"."default" "pg_catalog"."bpchar_ops" ASC NULLS LAST
);
CREATE INDEX "idx_p_corrected_image_url" ON "public"."problems" USING btree (
  "corrected_image_url1" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_p_created_at" ON "public"."problems" USING btree (
  "created_at" "pg_catalog"."timestamp_ops" ASC NULLS LAST
);
CREATE INDEX "idx_p_difficulty" ON "public"."problems" USING btree (
  "difficulty" "pg_catalog"."int2_ops" ASC NULLS LAST
);
CREATE INDEX "idx_p_mode" ON "public"."problems" USING btree (
  "mode" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_p_pic1" ON "public"."problems" USING btree (
  "pic1" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_p_status" ON "public"."problems" USING btree (
  "status" "pg_catalog"."int2_ops" ASC NULLS LAST
);
CREATE INDEX "idx_p_subject" ON "public"."problems" USING btree (
  "subject" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_p_user_id" ON "public"."problems" USING btree (
  "user_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table problems
-- ----------------------------
ALTER TABLE "public"."problems" ADD CONSTRAINT "problems_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table retry_queue
-- ----------------------------
CREATE INDEX "idx_rq_problem_id" ON "public"."retry_queue" USING btree (
  "problem_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);
CREATE INDEX "idx_rq_scheduled_at" ON "public"."retry_queue" USING btree (
  "scheduled_at" "pg_catalog"."timestamp_ops" ASC NULLS LAST
);
CREATE INDEX "idx_rq_status" ON "public"."retry_queue" USING btree (
  "status" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_rq_user_id" ON "public"."retry_queue" USING btree (
  "user_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);

-- ----------------------------
-- Uniques structure for table retry_queue
-- ----------------------------
ALTER TABLE "public"."retry_queue" ADD CONSTRAINT "retry_queue_task_id_key" UNIQUE ("task_id");

-- ----------------------------
-- Primary Key structure for table retry_queue
-- ----------------------------
ALTER TABLE "public"."retry_queue" ADD CONSTRAINT "retry_queue_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table rollback_logs
-- ----------------------------
CREATE INDEX "idx_rl_reason" ON "public"."rollback_logs" USING btree (
  "reason" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_rl_timestamp" ON "public"."rollback_logs" USING btree (
  "timestamp" "pg_catalog"."timestamp_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table rollback_logs
-- ----------------------------
ALTER TABLE "public"."rollback_logs" ADD CONSTRAINT "rollback_logs_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table student_level_progress
-- ----------------------------
CREATE INDEX "student_level_progress_level_id_17ffe39b" ON "public"."student_level_progress" USING btree (
  "level_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);
CREATE INDEX "student_level_progress_student_user_id_id_f1aeba27" ON "public"."student_level_progress" USING btree (
  "student_user_id_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);

-- ----------------------------
-- Uniques structure for table student_level_progress
-- ----------------------------
ALTER TABLE "public"."student_level_progress" ADD CONSTRAINT "student_level_progress_level_id_student_user_id_e18437d4_uniq" UNIQUE ("level_id", "student_user_id_id");

-- ----------------------------
-- Primary Key structure for table student_level_progress
-- ----------------------------
ALTER TABLE "public"."student_level_progress" ADD CONSTRAINT "student_level_progress_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table student_mission_progress
-- ----------------------------
CREATE INDEX "student_mission_progress_current_level_id_8ba939fb" ON "public"."student_mission_progress" USING btree (
  "current_level_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);
CREATE INDEX "student_mission_progress_mission_id_35441e2c" ON "public"."student_mission_progress" USING btree (
  "mission_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);
CREATE INDEX "student_mission_progress_student_user_id_id_d0f501fa" ON "public"."student_mission_progress" USING btree (
  "student_user_id_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);

-- ----------------------------
-- Uniques structure for table student_mission_progress
-- ----------------------------
ALTER TABLE "public"."student_mission_progress" ADD CONSTRAINT "student_mission_progress_mission_id_student_user__db62a46f_uniq" UNIQUE ("mission_id", "student_user_id_id");

-- ----------------------------
-- Primary Key structure for table student_mission_progress
-- ----------------------------
ALTER TABLE "public"."student_mission_progress" ADD CONSTRAINT "student_mission_progress_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table student_parent_bind
-- ----------------------------
CREATE INDEX "student_parent_bind_parent_user_id_id_c91c68c5" ON "public"."student_parent_bind" USING btree (
  "parent_user_id_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);
CREATE INDEX "student_parent_bind_student_user_id_id_7ae57eeb" ON "public"."student_parent_bind" USING btree (
  "student_user_id_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table student_parent_bind
-- ----------------------------
ALTER TABLE "public"."student_parent_bind" ADD CONSTRAINT "student_parent_bind_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table system_config
-- ----------------------------
CREATE INDEX "idx_sc_key" ON "public"."system_config" USING btree (
  "key" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);

-- ----------------------------
-- Uniques structure for table system_config
-- ----------------------------
ALTER TABLE "public"."system_config" ADD CONSTRAINT "system_config_key_key" UNIQUE ("key");

-- ----------------------------
-- Primary Key structure for table system_config
-- ----------------------------
ALTER TABLE "public"."system_config" ADD CONSTRAINT "system_config_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table task_outbox
-- ----------------------------
CREATE INDEX "idx_to_created_at" ON "public"."task_outbox" USING btree (
  "created_at" "pg_catalog"."timestamp_ops" ASC NULLS LAST
);
CREATE INDEX "idx_to_problem_id" ON "public"."task_outbox" USING btree (
  "problem_id" "pg_catalog"."int4_ops" ASC NULLS LAST
);
CREATE INDEX "idx_to_sent_at" ON "public"."task_outbox" USING btree (
  "sent_at" "pg_catalog"."timestamp_ops" ASC NULLS LAST
);
CREATE INDEX "idx_to_status" ON "public"."task_outbox" USING btree (
  "status" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_to_user_id" ON "public"."task_outbox" USING btree (
  "user_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);

-- ----------------------------
-- Uniques structure for table task_outbox
-- ----------------------------
ALTER TABLE "public"."task_outbox" ADD CONSTRAINT "task_outbox_task_id_key" UNIQUE ("task_id");
ALTER TABLE "public"."task_outbox" ADD CONSTRAINT "task_outbox_trace_id_key" UNIQUE ("trace_id");
ALTER TABLE "public"."task_outbox" ADD CONSTRAINT "task_outbox_request_key_key" UNIQUE ("request_key");

-- ----------------------------
-- Primary Key structure for table task_outbox
-- ----------------------------
ALTER TABLE "public"."task_outbox" ADD CONSTRAINT "task_outbox_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Primary Key structure for table test_connection
-- ----------------------------
ALTER TABLE "public"."test_connection" ADD CONSTRAINT "test_connection_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table tiku_ai_parse_result
-- ----------------------------
CREATE INDEX "ai_parse_result_page_id_60c48895" ON "public"."tiku_ai_parse_result" USING btree (
  "page_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);
CREATE INDEX "ai_parse_result_paper_id_c01b00ab" ON "public"."tiku_ai_parse_result" USING btree (
  "paper_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table tiku_ai_parse_result
-- ----------------------------
ALTER TABLE "public"."tiku_ai_parse_result" ADD CONSTRAINT "ai_parse_result_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table tiku_exam_page
-- ----------------------------
CREATE INDEX "exam_page_paper_id_197a5b7f" ON "public"."tiku_exam_page" USING btree (
  "paper_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);

-- ----------------------------
-- Uniques structure for table tiku_exam_page
-- ----------------------------
ALTER TABLE "public"."tiku_exam_page" ADD CONSTRAINT "exam_page_paper_id_page_no_ad938d95_uniq" UNIQUE ("paper_id", "page_no");

-- ----------------------------
-- Primary Key structure for table tiku_exam_page
-- ----------------------------
ALTER TABLE "public"."tiku_exam_page" ADD CONSTRAINT "exam_page_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table tiku_exam_paper
-- ----------------------------
CREATE INDEX "tiku_exam_paper_creator_id_0c8683e5" ON "public"."tiku_exam_paper" USING btree (
  "creator_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);
CREATE INDEX "tiku_exam_paper_is_deleted_1e7da5ac" ON "public"."tiku_exam_paper" USING btree (
  "is_deleted" "pg_catalog"."bool_ops" ASC NULLS LAST
);
CREATE INDEX "tiku_exam_paper_paper_code_de2dd0ab_like" ON "public"."tiku_exam_paper" USING btree (
  "paper_code" COLLATE "pg_catalog"."default" "pg_catalog"."varchar_pattern_ops" ASC NULLS LAST
);
CREATE INDEX "tiku_exam_paper_uploaded_by_id_bff84818" ON "public"."tiku_exam_paper" USING btree (
  "uploaded_by_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);

-- ----------------------------
-- Uniques structure for table tiku_exam_paper
-- ----------------------------
ALTER TABLE "public"."tiku_exam_paper" ADD CONSTRAINT "tiku_exam_paper_paper_code_key" UNIQUE ("paper_code");

-- ----------------------------
-- Primary Key structure for table tiku_exam_paper
-- ----------------------------
ALTER TABLE "public"."tiku_exam_paper" ADD CONSTRAINT "tiku_exam_paper_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table tiku_exam_question
-- ----------------------------
CREATE INDEX "exam_question_original_question_id_d5f8f89a" ON "public"."tiku_exam_question" USING btree (
  "original_question_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);
CREATE INDEX "exam_question_paper_id_4d8294c6" ON "public"."tiku_exam_question" USING btree (
  "paper_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);
CREATE INDEX "exam_question_parent_question_id_6cb2d0ba" ON "public"."tiku_exam_question" USING btree (
  "parent_question_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);
CREATE INDEX "idx_paper_qno" ON "public"."tiku_exam_question" USING btree (
  "paper_question_no" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_paper_question" ON "public"."tiku_exam_question" USING btree (
  "paper_id" "pg_catalog"."int8_ops" ASC NULLS LAST,
  "question_no" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_question_type" ON "public"."tiku_exam_question" USING btree (
  "question_type" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_review_status" ON "public"."tiku_exam_question" USING btree (
  "review_status" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "idx_system_id" ON "public"."tiku_exam_question" USING btree (
  "system_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "tiku_exam_question_paper_question_no_e1fbc602" ON "public"."tiku_exam_question" USING btree (
  "paper_question_no" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "tiku_exam_question_paper_question_no_e1fbc602_like" ON "public"."tiku_exam_question" USING btree (
  "paper_question_no" COLLATE "pg_catalog"."default" "pg_catalog"."varchar_pattern_ops" ASC NULLS LAST
);
CREATE INDEX "tiku_exam_question_system_id_6cacb2aa_like" ON "public"."tiku_exam_question" USING btree (
  "system_id" COLLATE "pg_catalog"."default" "pg_catalog"."varchar_pattern_ops" ASC NULLS LAST
);

-- ----------------------------
-- Uniques structure for table tiku_exam_question
-- ----------------------------
ALTER TABLE "public"."tiku_exam_question" ADD CONSTRAINT "tiku_exam_question_system_id_key" UNIQUE ("system_id");

-- ----------------------------
-- Primary Key structure for table tiku_exam_question
-- ----------------------------
ALTER TABLE "public"."tiku_exam_question" ADD CONSTRAINT "exam_question_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table tiku_favorite
-- ----------------------------
CREATE INDEX "tiku_favorite_question_id_b17ae687" ON "public"."tiku_favorite" USING btree (
  "question_id" "pg_catalog"."int4_ops" ASC NULLS LAST
);
CREATE INDEX "tiku_favorite_user_id_0fcd7358" ON "public"."tiku_favorite" USING btree (
  "user_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);

-- ----------------------------
-- Uniques structure for table tiku_favorite
-- ----------------------------
ALTER TABLE "public"."tiku_favorite" ADD CONSTRAINT "tiku_favorite_user_id_question_id_0bf0f962_uniq" UNIQUE ("user_id", "question_id");

-- ----------------------------
-- Primary Key structure for table tiku_favorite
-- ----------------------------
ALTER TABLE "public"."tiku_favorite" ADD CONSTRAINT "tiku_favorite_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Uniques structure for table tiku_paper_code_counter
-- ----------------------------
ALTER TABLE "public"."tiku_paper_code_counter" ADD CONSTRAINT "tiku_paper_code_counter_letter_grade_char_d01c5a44_uniq" UNIQUE ("letter", "grade_char");

-- ----------------------------
-- Primary Key structure for table tiku_paper_code_counter
-- ----------------------------
ALTER TABLE "public"."tiku_paper_code_counter" ADD CONSTRAINT "tiku_paper_code_counter_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table tiku_parse_task
-- ----------------------------
CREATE INDEX "idx_task_status" ON "public"."tiku_parse_task" USING btree (
  "status" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "tiku_parse_task_paper_id_ec9d7583" ON "public"."tiku_parse_task" USING btree (
  "paper_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);
CREATE INDEX "tiku_parse_task_question_id_27ed1243" ON "public"."tiku_parse_task" USING btree (
  "question_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table tiku_parse_task
-- ----------------------------
ALTER TABLE "public"."tiku_parse_task" ADD CONSTRAINT "tiku_parse_task_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table tiku_question_id_counter
-- ----------------------------
CREATE INDEX "tiku_question_id_counter_subject_c7597706_like" ON "public"."tiku_question_id_counter" USING btree (
  "subject" COLLATE "pg_catalog"."default" "pg_catalog"."varchar_pattern_ops" ASC NULLS LAST
);

-- ----------------------------
-- Uniques structure for table tiku_question_id_counter
-- ----------------------------
ALTER TABLE "public"."tiku_question_id_counter" ADD CONSTRAINT "tiku_question_id_counter_subject_key" UNIQUE ("subject");

-- ----------------------------
-- Primary Key structure for table tiku_question_id_counter
-- ----------------------------
ALTER TABLE "public"."tiku_question_id_counter" ADD CONSTRAINT "tiku_question_id_counter_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table tiku_question_image
-- ----------------------------
CREATE INDEX "question_image_page_id_9b429df2" ON "public"."tiku_question_image" USING btree (
  "page_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);
CREATE INDEX "question_image_paper_id_38092e30" ON "public"."tiku_question_image" USING btree (
  "paper_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);
CREATE INDEX "question_image_question_id_24577956" ON "public"."tiku_question_image" USING btree (
  "question_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table tiku_question_image
-- ----------------------------
ALTER TABLE "public"."tiku_question_image" ADD CONSTRAINT "question_image_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table tiku_question_option
-- ----------------------------
CREATE INDEX "question_option_question_id_1c698d8e" ON "public"."tiku_question_option" USING btree (
  "question_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);

-- ----------------------------
-- Uniques structure for table tiku_question_option
-- ----------------------------
ALTER TABLE "public"."tiku_question_option" ADD CONSTRAINT "question_option_question_id_option_label_c6c733f2_uniq" UNIQUE ("question_id", "option_label");

-- ----------------------------
-- Primary Key structure for table tiku_question_option
-- ----------------------------
ALTER TABLE "public"."tiku_question_option" ADD CONSTRAINT "question_option_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table tiku_teacher_favorite
-- ----------------------------
CREATE INDEX "tiku_teacher_favorite_question_id_81a98c5c" ON "public"."tiku_teacher_favorite" USING btree (
  "question_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);
CREATE INDEX "tiku_teacher_favorite_teacher_id_6f5ecc3e" ON "public"."tiku_teacher_favorite" USING btree (
  "teacher_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);
CREATE INDEX "tiku_teacher_favorite_user_id_573151b0" ON "public"."tiku_teacher_favorite" USING btree (
  "user_id" "pg_catalog"."int4_ops" ASC NULLS LAST
);

-- ----------------------------
-- Uniques structure for table tiku_teacher_favorite
-- ----------------------------
ALTER TABLE "public"."tiku_teacher_favorite" ADD CONSTRAINT "tiku_teacher_favorite_teacher_id_question_id_4ca85fb7_uniq" UNIQUE ("teacher_id", "question_id");

-- ----------------------------
-- Primary Key structure for table tiku_teacher_favorite
-- ----------------------------
ALTER TABLE "public"."tiku_teacher_favorite" ADD CONSTRAINT "tiku_teacher_favorite_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table tiku_teacher_profile
-- ----------------------------
CREATE INDEX "tiku_teacher_profile_username_0b669e00_like" ON "public"."tiku_teacher_profile" USING btree (
  "username" COLLATE "pg_catalog"."default" "pg_catalog"."varchar_pattern_ops" ASC NULLS LAST
);

-- ----------------------------
-- Uniques structure for table tiku_teacher_profile
-- ----------------------------
ALTER TABLE "public"."tiku_teacher_profile" ADD CONSTRAINT "tiku_teacher_profile_username_key" UNIQUE ("username");

-- ----------------------------
-- Primary Key structure for table tiku_teacher_profile
-- ----------------------------
ALTER TABLE "public"."tiku_teacher_profile" ADD CONSTRAINT "tiku_teacher_profile_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table user_account
-- ----------------------------
CREATE INDEX "user_account_mobile_e9c10212_like" ON "public"."user_account" USING btree (
  "mobile" COLLATE "pg_catalog"."default" "pg_catalog"."varchar_pattern_ops" ASC NULLS LAST
);

-- ----------------------------
-- Uniques structure for table user_account
-- ----------------------------
ALTER TABLE "public"."user_account" ADD CONSTRAINT "user_account_mobile_key" UNIQUE ("mobile");

-- ----------------------------
-- Primary Key structure for table user_account
-- ----------------------------
ALTER TABLE "public"."user_account" ADD CONSTRAINT "user_account_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table users
-- ----------------------------
CREATE INDEX "idx_u_created_at" ON "public"."users" USING btree (
  "created_at" "pg_catalog"."timestamp_ops" ASC NULLS LAST
);
CREATE INDEX "idx_u_status" ON "public"."users" USING btree (
  "status" "pg_catalog"."int2_ops" ASC NULLS LAST
);
CREATE INDEX "idx_u_unionid" ON "public"."users" USING btree (
  "unionid" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);

-- ----------------------------
-- Uniques structure for table users
-- ----------------------------
ALTER TABLE "public"."users" ADD CONSTRAINT "users_openid_key" UNIQUE ("openid");

-- ----------------------------
-- Primary Key structure for table users
-- ----------------------------
ALTER TABLE "public"."users" ADD CONSTRAINT "users_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Indexes structure for table wrong_book_item
-- ----------------------------
CREATE INDEX "wrong_book_item_student_user_id_id_04b6ed28" ON "public"."wrong_book_item" USING btree (
  "student_user_id_id" "pg_catalog"."int8_ops" ASC NULLS LAST
);

-- ----------------------------
-- Uniques structure for table wrong_book_item
-- ----------------------------
ALTER TABLE "public"."wrong_book_item" ADD CONSTRAINT "wrong_book_item_student_user_id_id_question_id_a31f2b0a_uniq" UNIQUE ("student_user_id_id", "question_id");

-- ----------------------------
-- Primary Key structure for table wrong_book_item
-- ----------------------------
ALTER TABLE "public"."wrong_book_item" ADD CONSTRAINT "wrong_book_item_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Foreign Keys structure for table ai_guidance_session
-- ----------------------------
ALTER TABLE "public"."ai_guidance_session" ADD CONSTRAINT "ai_guidance_session_student_user_id_id_35f0c5eb_fk_user_acco" FOREIGN KEY ("student_user_id_id") REFERENCES "public"."user_account" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION DEFERRABLE INITIALLY DEFERRED;

-- ----------------------------
-- Foreign Keys structure for table answer_attempt
-- ----------------------------
ALTER TABLE "public"."answer_attempt" ADD CONSTRAINT "answer_attempt_level_id_48e1cfa6_fk_mission_level_id" FOREIGN KEY ("level_id") REFERENCES "public"."mission_level" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE "public"."answer_attempt" ADD CONSTRAINT "answer_attempt_mission_id_c743e0cb_fk_learning_mission_id" FOREIGN KEY ("mission_id") REFERENCES "public"."learning_mission" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE "public"."answer_attempt" ADD CONSTRAINT "answer_attempt_student_user_id_id_2ca881b1_fk_user_account_id" FOREIGN KEY ("student_user_id_id") REFERENCES "public"."user_account" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION DEFERRABLE INITIALLY DEFERRED;

-- ----------------------------
-- Foreign Keys structure for table auth_group_permissions
-- ----------------------------
ALTER TABLE "public"."auth_group_permissions" ADD CONSTRAINT "auth_group_permissio_permission_id_84c5c92e_fk_auth_perm" FOREIGN KEY ("permission_id") REFERENCES "public"."auth_permission" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE "public"."auth_group_permissions" ADD CONSTRAINT "auth_group_permissions_group_id_b120cbf9_fk_auth_group_id" FOREIGN KEY ("group_id") REFERENCES "public"."auth_group" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION DEFERRABLE INITIALLY DEFERRED;

-- ----------------------------
-- Foreign Keys structure for table auth_permission
-- ----------------------------
ALTER TABLE "public"."auth_permission" ADD CONSTRAINT "auth_permission_content_type_id_2f476e4b_fk_django_co" FOREIGN KEY ("content_type_id") REFERENCES "public"."django_content_type" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION DEFERRABLE INITIALLY DEFERRED;

-- ----------------------------
-- Foreign Keys structure for table auth_user_groups
-- ----------------------------
ALTER TABLE "public"."auth_user_groups" ADD CONSTRAINT "auth_user_groups_group_id_97559544_fk_auth_group_id" FOREIGN KEY ("group_id") REFERENCES "public"."auth_group" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE "public"."auth_user_groups" ADD CONSTRAINT "auth_user_groups_user_id_6a12ed8b_fk_auth_user_id" FOREIGN KEY ("user_id") REFERENCES "public"."auth_user" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION DEFERRABLE INITIALLY DEFERRED;

-- ----------------------------
-- Foreign Keys structure for table auth_user_user_permissions
-- ----------------------------
ALTER TABLE "public"."auth_user_user_permissions" ADD CONSTRAINT "auth_user_user_permi_permission_id_1fbb5f2c_fk_auth_perm" FOREIGN KEY ("permission_id") REFERENCES "public"."auth_permission" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE "public"."auth_user_user_permissions" ADD CONSTRAINT "auth_user_user_permissions_user_id_a95ead1b_fk_auth_user_id" FOREIGN KEY ("user_id") REFERENCES "public"."auth_user" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION DEFERRABLE INITIALLY DEFERRED;

-- ----------------------------
-- Foreign Keys structure for table class
-- ----------------------------
ALTER TABLE "public"."class" ADD CONSTRAINT "class_creator_teacher_id_7a6558ab_fk_user_account_id" FOREIGN KEY ("creator_teacher_id") REFERENCES "public"."user_account" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE "public"."class" ADD CONSTRAINT "class_institution_id_27903dc7_fk_institution_id" FOREIGN KEY ("institution_id") REFERENCES "public"."institution" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION DEFERRABLE INITIALLY DEFERRED;

-- ----------------------------
-- Foreign Keys structure for table class_join_request
-- ----------------------------
ALTER TABLE "public"."class_join_request" ADD CONSTRAINT "class_join_request_applicant_id_6808a15f_fk_user_account_id" FOREIGN KEY ("applicant_id") REFERENCES "public"."user_account" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE "public"."class_join_request" ADD CONSTRAINT "class_join_request_class_id_0db05907_fk_class_id" FOREIGN KEY ("class_id") REFERENCES "public"."class" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE "public"."class_join_request" ADD CONSTRAINT "class_join_request_handled_by_id_6da7c4f5_fk_user_account_id" FOREIGN KEY ("handled_by_id") REFERENCES "public"."user_account" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION DEFERRABLE INITIALLY DEFERRED;

-- ----------------------------
-- Foreign Keys structure for table class_student
-- ----------------------------
ALTER TABLE "public"."class_student" ADD CONSTRAINT "class_student_class_id_aac5f036_fk_class_id" FOREIGN KEY ("class_id") REFERENCES "public"."class" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE "public"."class_student" ADD CONSTRAINT "class_student_student_id_b3a11024_fk_user_account_id" FOREIGN KEY ("student_id") REFERENCES "public"."user_account" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION DEFERRABLE INITIALLY DEFERRED;

-- ----------------------------
-- Foreign Keys structure for table class_teacher
-- ----------------------------
ALTER TABLE "public"."class_teacher" ADD CONSTRAINT "class_teacher_class_id_27aef63d_fk_class_id" FOREIGN KEY ("class_id") REFERENCES "public"."class" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE "public"."class_teacher" ADD CONSTRAINT "class_teacher_teacher_id_4e089a1e_fk_user_account_id" FOREIGN KEY ("teacher_id") REFERENCES "public"."user_account" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION DEFERRABLE INITIALLY DEFERRED;

-- ----------------------------
-- Foreign Keys structure for table course
-- ----------------------------
ALTER TABLE "public"."course" ADD CONSTRAINT "course_teacher_id_b694c4f5_fk_user_account_id" FOREIGN KEY ("teacher_id") REFERENCES "public"."user_account" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION DEFERRABLE INITIALLY DEFERRED;

-- ----------------------------
-- Foreign Keys structure for table course_material
-- ----------------------------
ALTER TABLE "public"."course_material" ADD CONSTRAINT "course_material_course_id_e3866b9f_fk_course_id" FOREIGN KEY ("course_id") REFERENCES "public"."course" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE "public"."course_material" ADD CONSTRAINT "course_material_uploaded_by_id_de650306_fk_user_account_id" FOREIGN KEY ("uploaded_by_id") REFERENCES "public"."user_account" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION DEFERRABLE INITIALLY DEFERRED;

-- ----------------------------
-- Foreign Keys structure for table course_question_link
-- ----------------------------
ALTER TABLE "public"."course_question_link" ADD CONSTRAINT "course_question_link_course_id_969244a2_fk_course_id" FOREIGN KEY ("course_id") REFERENCES "public"."course" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE "public"."course_question_link" ADD CONSTRAINT "course_question_link_question_id_86f1a9f6_fk_tiku_exam" FOREIGN KEY ("question_id") REFERENCES "public"."tiku_exam_question" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE "public"."course_question_link" ADD CONSTRAINT "course_question_link_tree_node_id_ae40e3c8_fk_course_tree_id" FOREIGN KEY ("tree_node_id") REFERENCES "public"."course_tree" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION DEFERRABLE INITIALLY DEFERRED;

-- ----------------------------
-- Foreign Keys structure for table course_tree
-- ----------------------------
ALTER TABLE "public"."course_tree" ADD CONSTRAINT "course_tree_course_id_3d6c0495_fk_course_id" FOREIGN KEY ("course_id") REFERENCES "public"."course" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE "public"."course_tree" ADD CONSTRAINT "course_tree_parent_id_fae96f5d_fk_course_tree_id" FOREIGN KEY ("parent_id") REFERENCES "public"."course_tree" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION DEFERRABLE INITIALLY DEFERRED;

-- ----------------------------
-- Foreign Keys structure for table course_variant_task
-- ----------------------------
ALTER TABLE "public"."course_variant_task" ADD CONSTRAINT "course_variant_task_original_question_id_5b5d7825_fk_tiku_exam" FOREIGN KEY ("original_question_id") REFERENCES "public"."tiku_exam_question" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION DEFERRABLE INITIALLY DEFERRED;

-- ----------------------------
-- Foreign Keys structure for table django_admin_log
-- ----------------------------
ALTER TABLE "public"."django_admin_log" ADD CONSTRAINT "django_admin_log_content_type_id_c4bce8eb_fk_django_co" FOREIGN KEY ("content_type_id") REFERENCES "public"."django_content_type" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE "public"."django_admin_log" ADD CONSTRAINT "django_admin_log_user_id_c564eba6_fk_auth_user_id" FOREIGN KEY ("user_id") REFERENCES "public"."auth_user" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION DEFERRABLE INITIALLY DEFERRED;

-- ----------------------------
-- Foreign Keys structure for table institution
-- ----------------------------
ALTER TABLE "public"."institution" ADD CONSTRAINT "institution_created_by_id_9b8900f1_fk_user_account_id" FOREIGN KEY ("created_by_id") REFERENCES "public"."user_account" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION DEFERRABLE INITIALLY DEFERRED;

-- ----------------------------
-- Foreign Keys structure for table institution_member
-- ----------------------------
ALTER TABLE "public"."institution_member" ADD CONSTRAINT "institution_member_institution_id_a8d35f11_fk_institution_id" FOREIGN KEY ("institution_id") REFERENCES "public"."institution" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE "public"."institution_member" ADD CONSTRAINT "institution_member_user_id_c0f0ef7a_fk_user_account_id" FOREIGN KEY ("user_id") REFERENCES "public"."user_account" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION DEFERRABLE INITIALLY DEFERRED;

-- ----------------------------
-- Foreign Keys structure for table learning_mission
-- ----------------------------
ALTER TABLE "public"."learning_mission" ADD CONSTRAINT "learning_mission_class_id_c2f8da19_fk_class_id" FOREIGN KEY ("class_id") REFERENCES "public"."class" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE "public"."learning_mission" ADD CONSTRAINT "learning_mission_creator_teacher_id_i_bdcbd33b_fk_user_acco" FOREIGN KEY ("creator_teacher_id_id") REFERENCES "public"."user_account" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION DEFERRABLE INITIALLY DEFERRED;

-- ----------------------------
-- Foreign Keys structure for table mastery_record
-- ----------------------------
ALTER TABLE "public"."mastery_record" ADD CONSTRAINT "mastery_record_student_user_id_id_e99c8a50_fk_user_account_id" FOREIGN KEY ("student_user_id_id") REFERENCES "public"."user_account" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION DEFERRABLE INITIALLY DEFERRED;

-- ----------------------------
-- Foreign Keys structure for table mission_level
-- ----------------------------
ALTER TABLE "public"."mission_level" ADD CONSTRAINT "mission_level_mission_id_838fe8ff_fk_learning_mission_id" FOREIGN KEY ("mission_id") REFERENCES "public"."learning_mission" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION DEFERRABLE INITIALLY DEFERRED;

-- ----------------------------
-- Foreign Keys structure for table mission_question_rel
-- ----------------------------
ALTER TABLE "public"."mission_question_rel" ADD CONSTRAINT "mission_question_rel_level_id_32b565b1_fk_mission_level_id" FOREIGN KEY ("level_id") REFERENCES "public"."mission_level" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE "public"."mission_question_rel" ADD CONSTRAINT "mission_question_rel_mission_id_350a17b0_fk_learning_mission_id" FOREIGN KEY ("mission_id") REFERENCES "public"."learning_mission" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION DEFERRABLE INITIALLY DEFERRED;

-- ----------------------------
-- Foreign Keys structure for table student_level_progress
-- ----------------------------
ALTER TABLE "public"."student_level_progress" ADD CONSTRAINT "student_level_progre_student_user_id_id_f1aeba27_fk_user_acco" FOREIGN KEY ("student_user_id_id") REFERENCES "public"."user_account" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE "public"."student_level_progress" ADD CONSTRAINT "student_level_progress_level_id_17ffe39b_fk_mission_level_id" FOREIGN KEY ("level_id") REFERENCES "public"."mission_level" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION DEFERRABLE INITIALLY DEFERRED;

-- ----------------------------
-- Foreign Keys structure for table student_mission_progress
-- ----------------------------
ALTER TABLE "public"."student_mission_progress" ADD CONSTRAINT "student_mission_prog_current_level_id_8ba939fb_fk_mission_l" FOREIGN KEY ("current_level_id") REFERENCES "public"."mission_level" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE "public"."student_mission_progress" ADD CONSTRAINT "student_mission_prog_mission_id_35441e2c_fk_learning_" FOREIGN KEY ("mission_id") REFERENCES "public"."learning_mission" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE "public"."student_mission_progress" ADD CONSTRAINT "student_mission_prog_student_user_id_id_d0f501fa_fk_user_acco" FOREIGN KEY ("student_user_id_id") REFERENCES "public"."user_account" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION DEFERRABLE INITIALLY DEFERRED;

-- ----------------------------
-- Foreign Keys structure for table student_parent_bind
-- ----------------------------
ALTER TABLE "public"."student_parent_bind" ADD CONSTRAINT "student_parent_bind_parent_user_id_id_c91c68c5_fk_user_acco" FOREIGN KEY ("parent_user_id_id") REFERENCES "public"."user_account" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE "public"."student_parent_bind" ADD CONSTRAINT "student_parent_bind_student_user_id_id_7ae57eeb_fk_user_acco" FOREIGN KEY ("student_user_id_id") REFERENCES "public"."user_account" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION DEFERRABLE INITIALLY DEFERRED;

-- ----------------------------
-- Foreign Keys structure for table tiku_ai_parse_result
-- ----------------------------
ALTER TABLE "public"."tiku_ai_parse_result" ADD CONSTRAINT "ai_parse_result_page_id_60c48895_fk_exam_page_id" FOREIGN KEY ("page_id") REFERENCES "public"."tiku_exam_page" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE "public"."tiku_ai_parse_result" ADD CONSTRAINT "ai_parse_result_paper_id_c01b00ab_fk_tiku_exam_paper_id" FOREIGN KEY ("paper_id") REFERENCES "public"."tiku_exam_paper" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION DEFERRABLE INITIALLY DEFERRED;

-- ----------------------------
-- Foreign Keys structure for table tiku_exam_page
-- ----------------------------
ALTER TABLE "public"."tiku_exam_page" ADD CONSTRAINT "exam_page_paper_id_197a5b7f_fk_tiku_exam_paper_id" FOREIGN KEY ("paper_id") REFERENCES "public"."tiku_exam_paper" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION DEFERRABLE INITIALLY DEFERRED;

-- ----------------------------
-- Foreign Keys structure for table tiku_exam_paper
-- ----------------------------
ALTER TABLE "public"."tiku_exam_paper" ADD CONSTRAINT "tiku_exam_paper_creator_id_0c8683e5_fk_user_account_id" FOREIGN KEY ("creator_id") REFERENCES "public"."user_account" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE "public"."tiku_exam_paper" ADD CONSTRAINT "tiku_exam_paper_uploaded_by_id_bff84818_fk_user_account_id" FOREIGN KEY ("uploaded_by_id") REFERENCES "public"."user_account" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION DEFERRABLE INITIALLY DEFERRED;

-- ----------------------------
-- Foreign Keys structure for table tiku_exam_question
-- ----------------------------
ALTER TABLE "public"."tiku_exam_question" ADD CONSTRAINT "exam_question_original_question_id_d5f8f89a_fk_exam_question_id" FOREIGN KEY ("original_question_id") REFERENCES "public"."tiku_exam_question" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE "public"."tiku_exam_question" ADD CONSTRAINT "exam_question_paper_id_4d8294c6_fk_tiku_exam_paper_id" FOREIGN KEY ("paper_id") REFERENCES "public"."tiku_exam_paper" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE "public"."tiku_exam_question" ADD CONSTRAINT "exam_question_parent_question_id_6cb2d0ba_fk_exam_question_id" FOREIGN KEY ("parent_question_id") REFERENCES "public"."tiku_exam_question" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION DEFERRABLE INITIALLY DEFERRED;

-- ----------------------------
-- Foreign Keys structure for table tiku_favorite
-- ----------------------------
ALTER TABLE "public"."tiku_favorite" ADD CONSTRAINT "tiku_favorite_user_id_0fcd7358_fk_user_account_id" FOREIGN KEY ("user_id") REFERENCES "public"."user_account" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION DEFERRABLE INITIALLY DEFERRED;

-- ----------------------------
-- Foreign Keys structure for table tiku_parse_task
-- ----------------------------
ALTER TABLE "public"."tiku_parse_task" ADD CONSTRAINT "tiku_parse_task_paper_id_ec9d7583_fk_tiku_exam_paper_id" FOREIGN KEY ("paper_id") REFERENCES "public"."tiku_exam_paper" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE "public"."tiku_parse_task" ADD CONSTRAINT "tiku_parse_task_question_id_27ed1243_fk_tiku_exam_question_id" FOREIGN KEY ("question_id") REFERENCES "public"."tiku_exam_question" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION DEFERRABLE INITIALLY DEFERRED;

-- ----------------------------
-- Foreign Keys structure for table tiku_question_image
-- ----------------------------
ALTER TABLE "public"."tiku_question_image" ADD CONSTRAINT "question_image_page_id_9b429df2_fk_exam_page_id" FOREIGN KEY ("page_id") REFERENCES "public"."tiku_exam_page" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE "public"."tiku_question_image" ADD CONSTRAINT "question_image_paper_id_38092e30_fk_tiku_exam_paper_id" FOREIGN KEY ("paper_id") REFERENCES "public"."tiku_exam_paper" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE "public"."tiku_question_image" ADD CONSTRAINT "question_image_question_id_24577956_fk_exam_question_id" FOREIGN KEY ("question_id") REFERENCES "public"."tiku_exam_question" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION DEFERRABLE INITIALLY DEFERRED;

-- ----------------------------
-- Foreign Keys structure for table tiku_question_option
-- ----------------------------
ALTER TABLE "public"."tiku_question_option" ADD CONSTRAINT "question_option_question_id_1c698d8e_fk_exam_question_id" FOREIGN KEY ("question_id") REFERENCES "public"."tiku_exam_question" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION DEFERRABLE INITIALLY DEFERRED;

-- ----------------------------
-- Foreign Keys structure for table tiku_teacher_favorite
-- ----------------------------
ALTER TABLE "public"."tiku_teacher_favorite" ADD CONSTRAINT "tiku_teacher_favorit_question_id_81a98c5c_fk_tiku_exam" FOREIGN KEY ("question_id") REFERENCES "public"."tiku_exam_question" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE "public"."tiku_teacher_favorite" ADD CONSTRAINT "tiku_teacher_favorit_teacher_id_6f5ecc3e_fk_tiku_teac" FOREIGN KEY ("teacher_id") REFERENCES "public"."tiku_teacher_profile" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE "public"."tiku_teacher_favorite" ADD CONSTRAINT "tiku_teacher_favorite_user_id_573151b0_fk_auth_user_id" FOREIGN KEY ("user_id") REFERENCES "public"."auth_user" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION DEFERRABLE INITIALLY DEFERRED;

-- ----------------------------
-- Foreign Keys structure for table wrong_book_item
-- ----------------------------
ALTER TABLE "public"."wrong_book_item" ADD CONSTRAINT "wrong_book_item_student_user_id_id_04b6ed28_fk_user_account_id" FOREIGN KEY ("student_user_id_id") REFERENCES "public"."user_account" ("id") ON DELETE NO ACTION ON UPDATE NO ACTION DEFERRABLE INITIALLY DEFERRED;
