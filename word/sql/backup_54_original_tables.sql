-- ============================================================
-- 备份文件: 更新前的54张原始表
-- 数据库: qisi_ai_tutor
-- 导出日期: 2026-07-17
-- ============================================================

-- ----------------------------
-- Table: ai_guidance_session (8 rows)
-- ----------------------------
INSERT INTO "ai_guidance_session" ("id", "question_id", "mode_type", "session_status", "invalid_input_count", "script_source", "content_log_json", "created_at", "updated_at", "student_user_id_id") VALUES
  (1, 1, 'B', 'running', 0, 'ai_generated', '{''steps'': []}', '2026-07-08 10:24:55.151657+00:00', '2026-07-08 10:24:55.151668+00:00', 3),
  (2, 4, 'B', 'running', 0, 'ai_generated', '{''steps'': []}', '2026-07-08 10:25:04.407567+00:00', '2026-07-08 10:25:04.407578+00:00', 3),
  (3, 4, 'B', 'running', 0, 'ai_generated', '{''steps'': []}', '2026-07-08 10:26:47.840204+00:00', '2026-07-08 10:26:47.840215+00:00', 3),
  (4, 1, 'B', 'running', 0, 'ai_generated', '{''steps'': []}', '2026-07-08 10:27:00.470229+00:00', '2026-07-08 10:27:00.470242+00:00', 3),
  (8, 1, 'B', 'running', 0, 'ai_generated', '{''steps'': [], ''step_index'': 0}', '2026-07-08 12:12:53.317678+00:00', '2026-07-08 12:12:53.317692+00:00', 2),
  (9, 1, 'B', 'running', 0, 'ai_generated', '{''steps'': [], ''step_index'': 0}', '2026-07-08 12:22:41.742547+00:00', '2026-07-08 12:22:41.742557+00:00', 3),
  (10, 2, 'B', 'running', 0, 'ai_generated', '{''steps'': [], ''step_index'': 0}', '2026-07-08 12:45:45.632521+00:00', '2026-07-08 12:45:45.632533+00:00', 3),
  (11, 2, 'B', 'running', 0, 'ai_generated', '{''steps'': [], ''step_index'': 0}', '2026-07-08 12:55:31.587011+00:00', '2026-07-08 12:55:31.587027+00:00', 3);

-- ----------------------------
-- Table: alert_logs (0 rows)
-- ----------------------------
-- alert_logs 表无数据

-- ----------------------------
-- Table: answer_attempt (16 rows)
-- ----------------------------
INSERT INTO "answer_attempt" ("id", "question_id", "attempt_no", "answer_content", "is_correct", "score", "submit_source", "submitted_at", "level_id", "mission_id", "student_user_id_id", "is_subjective_pending") VALUES
  (8, 4, 1, '{''text'': ''这是主观题答案''}', FALSE, '0.00', 'manual', '2026-07-08 09:25:40.916835+00:00', 1, NULL, 3, FALSE),
  (9, 1, 1, '{''selected_options'': [''B'']}', FALSE, '0.00', 'manual', '2026-07-08 09:25:40.917085+00:00', 1, NULL, 3, FALSE),
  (10, 14, 1, '{''text'': ''3''}', FALSE, '0.00', 'manual', '2026-07-08 09:27:10.899908+00:00', 1, NULL, 3, TRUE),
  (11, 2, 1, '{''selected_options'': [''C'']}', TRUE, '100.00', 'variant', '2026-07-08 09:27:51.537516+00:00', NULL, NULL, 3, FALSE),
  (12, 2, 2, '{''selected_options'': [''A'']}', FALSE, '0.00', 'variant', '2026-07-08 09:57:11.142647+00:00', NULL, NULL, 3, FALSE),
  (13, 2, 3, '{''selected_options'': [''A'', ''B'']}', FALSE, '0.00', 'variant', '2026-07-08 09:57:22.520399+00:00', NULL, NULL, 3, FALSE),
  (14, 2, 4, '{''selected_options'': [''B'', ''C'']}', FALSE, '0.00', 'variant', '2026-07-08 09:57:25.408906+00:00', NULL, NULL, 3, FALSE),
  (15, 2, 5, '{''selected_options'': [''C'']}', TRUE, '100.00', 'variant', '2026-07-08 09:57:26.765578+00:00', NULL, NULL, 3, FALSE),
  (16, 2, 6, '{''selected_options'': [''C'']}', TRUE, '100.00', 'variant', '2026-07-08 10:23:27.144298+00:00', NULL, NULL, 3, FALSE),
  (17, 10, 1, '{''selected_options'': []}', TRUE, '100.00', 'variant', '2026-07-08 10:23:33.164654+00:00', NULL, NULL, 3, FALSE),
  (18, 2, 7, '{''selected_options'': [''C'']}', TRUE, '100.00', 'variant', '2026-07-08 10:23:45.993441+00:00', NULL, NULL, 3, FALSE),
  (19, 1, 2, '{''selected_options'': [''A'', ''C'', ''B'', ''D'']}', FALSE, '0.00', 'manual', '2026-07-08 12:22:37.797960+00:00', 1, NULL, 3, FALSE),
  (20, 1, 3, '{''selected_options'': [''A'']}', TRUE, '100.00', 'manual', '2026-07-08 12:23:22.200108+00:00', 1, NULL, 3, FALSE),
  (21, 1, 4, '{''selected_options'': [''A'']}', TRUE, '100.00', 'manual', '2026-07-08 12:45:29.114543+00:00', 1, NULL, 3, FALSE),
  (22, 2, 8, '{''selected_options'': [''A'']}', FALSE, '0.00', 'manual', '2026-07-08 12:45:34.882577+00:00', 1, NULL, 3, FALSE),
  (23, 2, 9, '{''selected_options'': [''D'']}', FALSE, '0.00', 'manual', '2026-07-08 12:45:43.561282+00:00', 1, NULL, 3, FALSE);

-- ----------------------------
-- Table: api_task_logs (0 rows)
-- ----------------------------
-- api_task_logs 表无数据

-- ----------------------------
-- Table: auth_group (0 rows)
-- ----------------------------
-- auth_group 表无数据

-- ----------------------------
-- Table: auth_group_permissions (0 rows)
-- ----------------------------
-- auth_group_permissions 表无数据

-- ----------------------------
-- Table: auth_permission (132 rows)
-- ----------------------------
INSERT INTO "auth_permission" ("id", "name", "content_type_id", "codename") VALUES
  (1, 'Can add log entry', 1, 'add_logentry'),
  (2, 'Can change log entry', 1, 'change_logentry'),
  (3, 'Can delete log entry', 1, 'delete_logentry'),
  (4, 'Can view log entry', 1, 'view_logentry'),
  (5, 'Can add permission', 2, 'add_permission'),
  (6, 'Can change permission', 2, 'change_permission'),
  (7, 'Can delete permission', 2, 'delete_permission'),
  (8, 'Can view permission', 2, 'view_permission'),
  (9, 'Can add group', 3, 'add_group'),
  (10, 'Can change group', 3, 'change_group'),
  (11, 'Can delete group', 3, 'delete_group'),
  (12, 'Can view group', 3, 'view_group'),
  (13, 'Can add content type', 4, 'add_contenttype'),
  (14, 'Can change content type', 4, 'change_contenttype'),
  (15, 'Can delete content type', 4, 'delete_contenttype'),
  (16, 'Can view content type', 4, 'view_contenttype'),
  (17, 'Can add session', 5, 'add_session'),
  (18, 'Can change session', 5, 'change_session'),
  (19, 'Can delete session', 5, 'delete_session'),
  (20, 'Can view session', 5, 'view_session'),
  (21, 'Can add 试卷', 6, 'add_exampaper'),
  (22, 'Can change 试卷', 6, 'change_exampaper'),
  (23, 'Can delete 试卷', 6, 'delete_exampaper'),
  (24, 'Can view 试卷', 6, 'view_exampaper'),
  (25, 'Can add 解析任务', 7, 'add_parsetask'),
  (26, 'Can change 解析任务', 7, 'change_parsetask'),
  (27, 'Can delete 解析任务', 7, 'delete_parsetask'),
  (28, 'Can view 解析任务', 7, 'view_parsetask'),
  (29, 'Can add 试卷编号计数器', 8, 'add_papercodecounter'),
  (30, 'Can change 试卷编号计数器', 8, 'change_papercodecounter'),
  (31, 'Can delete 试卷编号计数器', 8, 'delete_papercodecounter'),
  (32, 'Can view 试卷编号计数器', 8, 'view_papercodecounter'),
  (33, 'Can add 题目系统编号计数器', 9, 'add_questionidcounter'),
  (34, 'Can change 题目系统编号计数器', 9, 'change_questionidcounter'),
  (35, 'Can delete 题目系统编号计数器', 9, 'delete_questionidcounter'),
  (36, 'Can view 题目系统编号计数器', 9, 'view_questionidcounter'),
  (37, 'Can add 试卷页面', 10, 'add_exampage'),
  (38, 'Can change 试卷页面', 10, 'change_exampage'),
  (39, 'Can delete 试卷页面', 10, 'delete_exampage'),
  (40, 'Can view 试卷页面', 10, 'view_exampage'),
  (41, 'Can add AI解析结果', 11, 'add_aiparseresult'),
  (42, 'Can change AI解析结果', 11, 'change_aiparseresult'),
  (43, 'Can delete AI解析结果', 11, 'delete_aiparseresult'),
  (44, 'Can view AI解析结果', 11, 'view_aiparseresult'),
  (45, 'Can add 题目', 12, 'add_examquestion'),
  (46, 'Can change 题目', 12, 'change_examquestion'),
  (47, 'Can delete 题目', 12, 'delete_examquestion'),
  (48, 'Can view 题目', 12, 'view_examquestion'),
  (49, 'Can add 题目插图', 13, 'add_questionimage'),
  (50, 'Can change 题目插图', 13, 'change_questionimage'),
  (51, 'Can delete 题目插图', 13, 'delete_questionimage'),
  (52, 'Can view 题目插图', 13, 'view_questionimage'),
  (53, 'Can add 选项', 14, 'add_questionoption'),
  (54, 'Can change 选项', 14, 'change_questionoption'),
  (55, 'Can delete 选项', 14, 'delete_questionoption'),
  (56, 'Can view 选项', 14, 'view_questionoption'),
  (57, 'Can add 知识点', 15, 'add_knowledgepoint'),
  (58, 'Can change 知识点', 15, 'change_knowledgepoint'),
  (59, 'Can delete 知识点', 15, 'delete_knowledgepoint'),
  (60, 'Can view 知识点', 15, 'view_knowledgepoint'),
  (61, 'Can add user account', 16, 'add_useraccount'),
  (62, 'Can change user account', 16, 'change_useraccount'),
  (63, 'Can delete user account', 16, 'delete_useraccount'),
  (64, 'Can view user account', 16, 'view_useraccount'),
  (65, 'Can add student parent bind', 17, 'add_studentparentbind'),
  (66, 'Can change student parent bind', 17, 'change_studentparentbind'),
  (67, 'Can delete student parent bind', 17, 'delete_studentparentbind'),
  (68, 'Can view student parent bind', 17, 'view_studentparentbind'),
  (69, 'Can add learning mission', 18, 'add_learningmission'),
  (70, 'Can change learning mission', 18, 'change_learningmission'),
  (71, 'Can delete learning mission', 18, 'delete_learningmission'),
  (72, 'Can view learning mission', 18, 'view_learningmission'),
  (73, 'Can add mission level', 19, 'add_missionlevel'),
  (74, 'Can change mission level', 19, 'change_missionlevel'),
  (75, 'Can delete mission level', 19, 'delete_missionlevel'),
  (76, 'Can view mission level', 19, 'view_missionlevel'),
  (77, 'Can add mission question rel', 20, 'add_missionquestionrel'),
  (78, 'Can change mission question rel', 20, 'change_missionquestionrel'),
  (79, 'Can delete mission question rel', 20, 'delete_missionquestionrel'),
  (80, 'Can view mission question rel', 20, 'view_missionquestionrel'),
  (81, 'Can add ai guidance session', 21, 'add_aiguidancesession'),
  (82, 'Can change ai guidance session', 21, 'change_aiguidancesession'),
  (83, 'Can delete ai guidance session', 21, 'delete_aiguidancesession'),
  (84, 'Can view ai guidance session', 21, 'view_aiguidancesession'),
  (85, 'Can add answer attempt', 22, 'add_answerattempt'),
  (86, 'Can change answer attempt', 22, 'change_answerattempt'),
  (87, 'Can delete answer attempt', 22, 'delete_answerattempt'),
  (88, 'Can view answer attempt', 22, 'view_answerattempt'),
  (89, 'Can add student level progress', 23, 'add_studentlevelprogress'),
  (90, 'Can change student level progress', 23, 'change_studentlevelprogress'),
  (91, 'Can delete student level progress', 23, 'delete_studentlevelprogress'),
  (92, 'Can view student level progress', 23, 'view_studentlevelprogress'),
  (93, 'Can add student mission progress', 24, 'add_studentmissionprogress'),
  (94, 'Can change student mission progress', 24, 'change_studentmissionprogress'),
  (95, 'Can delete student mission progress', 24, 'delete_studentmissionprogress'),
  (96, 'Can view student mission progress', 24, 'view_studentmissionprogress'),
  (97, 'Can add favorite', 25, 'add_favorite'),
  (98, 'Can change favorite', 25, 'change_favorite'),
  (99, 'Can delete favorite', 25, 'delete_favorite'),
  (100, 'Can view favorite', 25, 'view_favorite');
INSERT INTO "auth_permission" ("id", "name", "content_type_id", "codename") VALUES
  (101, 'Can add mastery record', 26, 'add_masteryrecord'),
  (102, 'Can change mastery record', 26, 'change_masteryrecord'),
  (103, 'Can delete mastery record', 26, 'delete_masteryrecord'),
  (104, 'Can view mastery record', 26, 'view_masteryrecord'),
  (105, 'Can add wrong book item', 27, 'add_wrongbookitem'),
  (106, 'Can change wrong book item', 27, 'change_wrongbookitem'),
  (107, 'Can delete wrong book item', 27, 'delete_wrongbookitem'),
  (108, 'Can view wrong book item', 27, 'view_wrongbookitem'),
  (109, 'Can add class', 28, 'add_class'),
  (110, 'Can change class', 28, 'change_class'),
  (111, 'Can delete class', 28, 'delete_class'),
  (112, 'Can view class', 28, 'view_class'),
  (113, 'Can add class join request', 29, 'add_classjoinrequest'),
  (114, 'Can change class join request', 29, 'change_classjoinrequest'),
  (115, 'Can delete class join request', 29, 'delete_classjoinrequest'),
  (116, 'Can view class join request', 29, 'view_classjoinrequest'),
  (117, 'Can add institution', 30, 'add_institution'),
  (118, 'Can change institution', 30, 'change_institution'),
  (119, 'Can delete institution', 30, 'delete_institution'),
  (120, 'Can view institution', 30, 'view_institution'),
  (121, 'Can add class student', 31, 'add_classstudent'),
  (122, 'Can change class student', 31, 'change_classstudent'),
  (123, 'Can delete class student', 31, 'delete_classstudent'),
  (124, 'Can view class student', 31, 'view_classstudent'),
  (125, 'Can add class teacher', 32, 'add_classteacher'),
  (126, 'Can change class teacher', 32, 'change_classteacher'),
  (127, 'Can delete class teacher', 32, 'delete_classteacher'),
  (128, 'Can view class teacher', 32, 'view_classteacher'),
  (129, 'Can add institution member', 33, 'add_institutionmember'),
  (130, 'Can change institution member', 33, 'change_institutionmember'),
  (131, 'Can delete institution member', 33, 'delete_institutionmember'),
  (132, 'Can view institution member', 33, 'view_institutionmember');

-- ----------------------------
-- Table: auth_user (0 rows)
-- ----------------------------
-- auth_user 表无数据

-- ----------------------------
-- Table: auth_user_groups (0 rows)
-- ----------------------------
-- auth_user_groups 表无数据

-- ----------------------------
-- Table: auth_user_user_permissions (0 rows)
-- ----------------------------
-- auth_user_user_permissions 表无数据

-- ----------------------------
-- Table: class (2 rows)
-- ----------------------------
INSERT INTO "class" ("id", "class_no", "class_name", "description", "max_students", "invite_code", "allow_invite_join", "status", "created_at", "updated_at", "creator_teacher_id", "institution_id") VALUES
  (1, 'CLS-76008700', '阶段1验证班级', NULL, 50, 'TEST001', TRUE, 'active', '2026-07-08 09:24:42.489264+00:00', '2026-07-08 09:24:42.489271+00:00', 1, 1),
  (6, '_STEM_C', '_StemClass', NULL, 50, 'F0IIUUWP', TRUE, 'active', '2026-07-08 12:39:10.057778+00:00', '2026-07-08 12:39:10.057787+00:00', NULL, 6);

-- ----------------------------
-- Table: class_join_request (0 rows)
-- ----------------------------
-- class_join_request 表无数据

-- ----------------------------
-- Table: class_student (1 rows)
-- ----------------------------
INSERT INTO "class_student" ("id", "join_type", "status", "joined_at", "class_id", "student_id") VALUES
  (4, 'manual', 'active', '2026-07-08 09:24:45.180259+00:00', 1, 3);

-- ----------------------------
-- Table: class_teacher (0 rows)
-- ----------------------------
-- class_teacher 表无数据

-- ----------------------------
-- Table: django_admin_log (0 rows)
-- ----------------------------
-- django_admin_log 表无数据

-- ----------------------------
-- Table: django_content_type (33 rows)
-- ----------------------------
INSERT INTO "django_content_type" ("id", "app_label", "model") VALUES
  (1, 'admin', 'logentry'),
  (2, 'auth', 'permission'),
  (3, 'auth', 'group'),
  (4, 'contenttypes', 'contenttype'),
  (5, 'sessions', 'session'),
  (6, 'papers', 'exampaper'),
  (7, 'papers', 'parsetask'),
  (8, 'papers', 'papercodecounter'),
  (9, 'papers', 'questionidcounter'),
  (10, 'parser', 'exampage'),
  (11, 'parser', 'aiparseresult'),
  (12, 'parser', 'examquestion'),
  (13, 'parser', 'questionimage'),
  (14, 'parser', 'questionoption'),
  (15, 'knowledge', 'knowledgepoint'),
  (16, 'accounts', 'useraccount'),
  (17, 'accounts', 'studentparentbind'),
  (18, 'missions', 'learningmission'),
  (19, 'missions', 'missionlevel'),
  (20, 'missions', 'missionquestionrel'),
  (21, 'study', 'aiguidancesession'),
  (22, 'study', 'answerattempt'),
  (23, 'study', 'studentlevelprogress'),
  (24, 'study', 'studentmissionprogress'),
  (25, 'study', 'favorite'),
  (26, 'wrongbook', 'masteryrecord'),
  (27, 'wrongbook', 'wrongbookitem'),
  (28, 'institutions', 'class'),
  (29, 'institutions', 'classjoinrequest'),
  (30, 'institutions', 'institution'),
  (31, 'institutions', 'classstudent'),
  (32, 'institutions', 'classteacher'),
  (33, 'institutions', 'institutionmember');

-- ----------------------------
-- Table: django_migrations (43 rows)
-- ----------------------------
INSERT INTO "django_migrations" ("id", "app", "name", "applied") VALUES
  (1, 'accounts', '0001_initial', '2026-07-06 10:21:24.113827+00:00'),
  (2, 'accounts', '0002_remove_useraccount_last_login_at_and_more', '2026-07-06 10:21:24.122124+00:00'),
  (3, 'accounts', '0003_add_user_subject', '2026-07-06 10:21:24.125433+00:00'),
  (4, 'accounts', '0004_useraccount_stages', '2026-07-06 10:21:24.128443+00:00'),
  (5, 'contenttypes', '0001_initial', '2026-07-06 10:21:24.134476+00:00'),
  (6, 'admin', '0001_initial', '2026-07-06 10:21:24.146652+00:00'),
  (7, 'admin', '0002_logentry_remove_auto_add', '2026-07-06 10:21:24.148918+00:00'),
  (8, 'admin', '0003_logentry_add_action_flag_choices', '2026-07-06 10:21:24.151651+00:00'),
  (9, 'contenttypes', '0002_remove_content_type_name', '2026-07-06 10:21:24.157731+00:00'),
  (10, 'auth', '0001_initial', '2026-07-06 10:21:24.188951+00:00'),
  (11, 'auth', '0002_alter_permission_name_max_length', '2026-07-06 10:21:24.193091+00:00'),
  (12, 'auth', '0003_alter_user_email_max_length', '2026-07-06 10:21:24.195875+00:00'),
  (13, 'auth', '0004_alter_user_username_opts', '2026-07-06 10:21:24.198923+00:00'),
  (14, 'auth', '0005_alter_user_last_login_null', '2026-07-06 10:21:24.201897+00:00'),
  (15, 'auth', '0006_require_contenttypes_0002', '2026-07-06 10:21:24.203636+00:00'),
  (16, 'auth', '0007_alter_validators_add_error_messages', '2026-07-06 10:21:24.206693+00:00'),
  (17, 'auth', '0008_alter_user_username_max_length', '2026-07-06 10:21:24.209842+00:00'),
  (18, 'auth', '0009_alter_user_last_name_max_length', '2026-07-06 10:21:24.212641+00:00'),
  (19, 'auth', '0010_alter_group_name_max_length', '2026-07-06 10:21:24.217291+00:00'),
  (20, 'auth', '0011_update_proxy_permissions', '2026-07-06 10:21:24.220691+00:00'),
  (21, 'auth', '0012_alter_user_first_name_max_length', '2026-07-06 10:21:24.224041+00:00'),
  (22, 'institutions', '0001_initial', '2026-07-06 10:21:24.304663+00:00'),
  (23, 'knowledge', '0001_initial', '2026-07-06 10:21:24.306544+00:00'),
  (24, 'missions', '0001_initial', '2026-07-06 10:21:24.342962+00:00'),
  (25, 'missions', '0002_learningmission_class_obj', '2026-07-06 10:21:24.356823+00:00'),
  (26, 'papers', '0001_initial', '2026-07-06 10:21:24.374770+00:00'),
  (27, 'parser', '0001_initial', '2026-07-06 10:21:24.450923+00:00'),
  (28, 'parser', '0002_alter_aiparseresult_table_alter_exampage_table_and_more', '2026-07-06 10:21:24.467193+00:00'),
  (29, 'papers', '0002_add_paper_fields', '2026-07-06 10:21:24.496229+00:00'),
  (30, 'parser', '0003_add_question_fields', '2026-07-06 10:21:24.535246+00:00'),
  (31, 'parser', '0004_backfill_question_ids', '2026-07-06 10:21:24.548013+00:00'),
  (32, 'papers', '0003_backfill_paper_codes', '2026-07-06 10:21:24.560327+00:00'),
  (33, 'papers', '0004_exampaper_is_deleted', '2026-07-06 10:21:24.568890+00:00'),
  (34, 'papers', '0005_add_question_fk_to_parse_task', '2026-07-06 10:21:24.577199+00:00'),
  (35, 'papers', '0006_add_uploaded_by_to_exam_paper', '2026-07-06 10:21:24.589380+00:00'),
  (36, 'parser', '0005_add_ai_answer_fields', '2026-07-06 10:21:24.605578+00:00'),
  (37, 'parser', '0006_alter_examquestion_ai_answer_a_and_more', '2026-07-06 10:21:24.647745+00:00'),
  (38, 'parser', '0007_add_ai_processing_fields', '2026-07-06 10:21:24.670330+00:00'),
  (39, 'sessions', '0001_initial', '2026-07-06 10:21:24.680360+00:00'),
  (40, 'study', '0001_initial', '2026-07-06 10:21:24.752798+00:00'),
  (41, 'study', '0002_favorite', '2026-07-06 10:21:24.771965+00:00'),
  (42, 'wrongbook', '0001_initial', '2026-07-06 10:21:24.801379+00:00'),
  (43, 'study', '0003_answerattempt_is_subjective_pending', '2026-07-08 03:06:42.617874+00:00');

-- ----------------------------
-- Table: django_session (0 rows)
-- ----------------------------
-- django_session 表无数据

-- ----------------------------
-- Table: dlq_messages (0 rows)
-- ----------------------------
-- dlq_messages 表无数据

-- ----------------------------
-- Table: gemini_results (0 rows)
-- ----------------------------
-- gemini_results 表无数据

-- ----------------------------
-- Table: institution (2 rows)
-- ----------------------------
INSERT INTO "institution" ("id", "institution_name", "contact_name", "contact_phone", "contact_email", "address", "status", "created_at", "updated_at", "created_by_id") VALUES
  (1, '测试学校', NULL, NULL, NULL, NULL, 'active', '2026-07-08 09:24:42.485620+00:00', '2026-07-08 09:24:42.485632+00:00', NULL),
  (6, '_STEM_I', NULL, NULL, NULL, NULL, 'active', '2026-07-08 12:39:10.055803+00:00', '2026-07-08 12:39:10.055814+00:00', NULL);

-- ----------------------------
-- Table: institution_member (0 rows)
-- ----------------------------
-- institution_member 表无数据

-- ----------------------------
-- Table: knowledge_points (0 rows)
-- ----------------------------
-- knowledge_points 表无数据

-- ----------------------------
-- Table: learning_mission (2 rows)
-- ----------------------------
INSERT INTO "learning_mission" ("id", "mission_no", "mission_name", "goal_text", "start_at", "end_at", "status", "default_mode_policy", "created_at", "updated_at", "creator_teacher_id_id", "class_id") VALUES
  (1, 'MS07D3F74A8019', '阶段1验证任务', '', '2026-07-08 09:24:42.495286+00:00', '2026-07-15 09:24:42.495288+00:00', 'published', NULL, '2026-07-08 09:24:42.496359+00:00', '2026-07-08 10:43:33.964592+00:00', 1, 1),
  (6, 'MSB5E9ADEBFB80', '_STEM_M', '', NULL, NULL, 'published', NULL, '2026-07-08 12:39:10.059221+00:00', '2026-07-08 12:39:10.059226+00:00', 2, 6);

-- ----------------------------
-- Table: llm_audit (0 rows)
-- ----------------------------
-- llm_audit 表无数据

-- ----------------------------
-- Table: mastery_record (2 rows)
-- ----------------------------
INSERT INTO "mastery_record" ("id", "mastery_type", "target_code", "mastery_status", "mastery_score", "next_review_at", "updated_at", "student_user_id_id") VALUES
  (3, 'question', '2', 'mastered', '100.00', NULL, '2026-07-08 10:23:45.997724+00:00', 3),
  (4, 'question', '10', 'not_mastered', '50.00', NULL, '2026-07-08 10:23:33.168720+00:00', 3);

-- ----------------------------
-- Table: mission_level (1 rows)
-- ----------------------------
INSERT INTO "mission_level" ("id", "level_no", "level_name", "level_type", "pass_rule_json", "mode_policy", "hint_strength", "mission_id") VALUES
  (1, 1, '基础练习', 'practice', '{}', NULL, 'medium', 1);

-- ----------------------------
-- Table: mission_question_rel (7 rows)
-- ----------------------------
INSERT INTO "mission_question_rel" ("id", "question_id", "sort_no", "is_required", "source_type", "level_id", "mission_id") VALUES
  (1, 1, 1, TRUE, 'manual_select', 1, 1),
  (2, 2, 2, TRUE, 'manual_select', 1, 1),
  (3, 3, 3, TRUE, 'manual_select', 1, 1),
  (4, 4, 4, TRUE, 'manual_select', 1, 1),
  (5, 5, 5, TRUE, 'manual_select', 1, 1),
  (6, 14, 6, TRUE, 'manual_select', 1, 1),
  (7, 15, 7, TRUE, 'manual_select', 1, 1);

-- ----------------------------
-- Table: monitoring_metrics (0 rows)
-- ----------------------------
-- monitoring_metrics 表无数据

-- ----------------------------
-- Table: problem_results (0 rows)
-- ----------------------------
-- problem_results 表无数据

-- ----------------------------
-- Table: problems (0 rows)
-- ----------------------------
-- problems 表无数据

-- ----------------------------
-- Table: retry_queue (0 rows)
-- ----------------------------
-- retry_queue 表无数据

-- ----------------------------
-- Table: rollback_logs (0 rows)
-- ----------------------------
-- rollback_logs 表无数据

-- ----------------------------
-- Table: student_level_progress (2 rows)
-- ----------------------------
INSERT INTO "student_level_progress" ("id", "status", "pass_score", "attempt_count", "passed_at", "level_id", "student_user_id_id") VALUES
  (1, 'running', '100.00', 5, NULL, 1, 3),
  (2, 'running', '0.00', 0, NULL, 1, 2);

-- ----------------------------
-- Table: student_mission_progress (1 rows)
-- ----------------------------
INSERT INTO "student_mission_progress" ("id", "progress_status", "progress_percent", "last_action_at", "current_level_id", "mission_id", "student_user_id_id") VALUES
  (4, 'not_started', '0.00', '2026-07-08 09:24:45.183886+00:00', NULL, 1, 3);

-- ----------------------------
-- Table: student_parent_bind (0 rows)
-- ----------------------------
-- student_parent_bind 表无数据

-- ----------------------------
-- Table: system_config (0 rows)
-- ----------------------------
-- system_config 表无数据

-- ----------------------------
-- Table: task_outbox (0 rows)
-- ----------------------------
-- task_outbox 表无数据

-- ----------------------------
-- Table: test_connection (0 rows)
-- ----------------------------
-- test_connection 表无数据

-- ----------------------------
-- Table: tiku_ai_parse_result (0 rows)
-- ----------------------------
-- tiku_ai_parse_result 表无数据

-- ----------------------------
-- Table: tiku_exam_page (0 rows)
-- ----------------------------
-- tiku_exam_page 表无数据

-- ----------------------------
-- Table: tiku_exam_paper (1 rows)
-- ----------------------------
INSERT INTO "tiku_exam_paper" ("id", "title", "subject", "stage", "grade", "paper_type", "has_solution", "source_file_path", "pdf_file_path", "total_pages", "total_questions", "status", "error_message", "created_at", "updated_at", "paper_code", "region", "is_deleted", "uploaded_by_id", "creator_id") VALUES
  (7, '2026高考数学真题（导入测试）', '数学', '高中', '高三', '高考真题', FALSE, '/test/import.pdf', NULL, 1, 13, 'finished', NULL, '2026-07-08 09:20:09.145196+00:00', '2026-07-08 09:20:09.145207+00:00', 'M90001', NULL, FALSE, 3, NULL);

-- ----------------------------
-- Table: tiku_exam_question (15 rows)
-- ----------------------------
INSERT INTO "tiku_exam_question" ("id", "question_no", "section_title", "question_type", "subject", "stem", "stem_html", "answer", "analysis", "solution", "comment", "raw_explanation", "raw_text", "knowledge_points", "difficulty", "page_start", "page_end", "bbox", "region_json", "sort_order", "confidence", "formula_need_review", "need_review", "review_status", "parse_status", "created_at", "updated_at", "original_question_id", "paper_id", "parent_question_id", "system_id", "paper_question_no", "ai_answer_a", "ai_answer_b", "ai_answer_c", "ai_knowledge_enrichment", "ai_probe_result", "ai_vision_extract", "ai_verifier_result", "ai_processed_at", "ai_processing_status") VALUES
  (1, '1', '一、选择题', 'single_choice', '数学', '已知集合 $ A = \{x \mid -5 < x^3 < 5\} $，$ B = \{-3, -1, 0, 2, 3\} $，则 $ A \cap B = $（ ）', NULL, 'A', '先求集合 $ A $：由 $ -5 < x^3 < 5 $，得 $ \sqrt[3]{-5} < x < \sqrt[3]{5} $。由于 $ \sqrt[3]{-5} \approx -1.71 $，$ \sqrt[3]{5} \approx 1.71 $，所以 $ A = \{x \mid -1.71 < x < 1.71\} $。集合 $ B = \{-3, -1, 0, 2, 3\} $ 中，满足该范围的元素为 $ -1 $ 和 $ 0 $，故 $ A \cap B = \{-1, 0\} $。', NULL, NULL, NULL, NULL, NULL, '2.00', NULL, NULL, NULL, NULL, 1, '0.9800', FALSE, FALSE, 'confirmed', 'auto_parsed', '2026-07-08 09:20:09.153996+00:00', '2026-07-08 09:20:09.154003+00:00', NULL, 7, NULL, 'M00001', 'MX0010-1-1', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'pending'),
  (2, '2', '一、选择题', 'single_choice', '数学', '若 $\frac{z}{z-1} = 1 + i$，则 $z =$（ ）', NULL, 'C', '由复数四则运算法则直接运算即可求解.', NULL, NULL, NULL, NULL, NULL, '2.00', NULL, NULL, NULL, NULL, 2, '0.9800', FALSE, FALSE, 'unreviewed', 'auto_parsed', '2026-07-08 09:20:09.159434+00:00', '2026-07-08 09:20:09.159439+00:00', NULL, 7, NULL, 'M00002', 'MX0010-1-2', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'pending'),
  (3, '3', '一、选择题', 'single_choice', '数学', '已知向量 $\vec{a} = (0, 1)$，$\vec{b} = (2, x)$，若 $\vec{b} \perp (\vec{b} - 4\vec{a})$，则 $x =$（ ）', NULL, 'D', '根据向量垂直的坐标运算可求 $x$ 的值.', NULL, NULL, NULL, NULL, NULL, '3.00', NULL, NULL, NULL, NULL, 3, '0.9800', FALSE, FALSE, 'unreviewed', 'auto_parsed', '2026-07-08 09:20:09.162956+00:00', '2026-07-08 09:20:09.162961+00:00', NULL, 7, NULL, 'M00003', 'MX0010-1-3', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'pending'),
  (4, '4', '一、选择题', 'single_choice', '数学', '已知 $\cos(\alpha + \beta) = m$，$	an\alpha 	an\beta = 2$，则 $\cos(\alpha - \beta) =$（ ）', NULL, 'A', '', NULL, NULL, NULL, NULL, NULL, '4.00', NULL, NULL, NULL, NULL, 4, '0.9800', FALSE, FALSE, 'unreviewed', 'auto_parsed', '2026-07-08 09:20:09.166823+00:00', '2026-07-08 09:20:09.166830+00:00', NULL, 7, NULL, 'M00004', 'MX0010-1-4', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'pending'),
  (5, '5', '一、选择题', 'single_choice', '数学', '已知圆柱和圆锥的底面半径相等，侧面积相等，且它们的高均为$\sqrt{3}$，则圆锥的体积为（ ）', NULL, 'B', '设圆柱的底面半径为$r$，根据圆锥和圆柱的侧面积相等可得半径$r$的方程，求出解后可求圆锥的体积.', NULL, NULL, NULL, NULL, NULL, '3.00', NULL, NULL, NULL, NULL, 5, '0.9800', FALSE, FALSE, 'unreviewed', 'auto_parsed', '2026-07-08 09:20:09.170673+00:00', '2026-07-08 09:20:09.170678+00:00', NULL, 7, NULL, 'M00005', 'MX0010-1-5', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'pending'),
  (6, '6', '一、选择题', 'single_choice', '数学', '已知函数为$f(x)=\begin{cases}-x^2-2ax-a, x<0 \\ e^x+\ln(x+1), x\geq 0\end{cases}$，在$\mathbf{R}$上单调递增，则$a$取值的范围是（ ）', NULL, 'B', '', NULL, NULL, NULL, NULL, NULL, '4.00', NULL, NULL, NULL, NULL, 6, '0.9800', FALSE, FALSE, 'unreviewed', 'auto_parsed', '2026-07-08 09:20:09.174172+00:00', '2026-07-08 09:20:09.174176+00:00', NULL, 7, NULL, 'M00006', 'MX0010-1-6', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'pending'),
  (7, '7', '一、选择题', 'single_choice', '数学', '当 $x \in [0, 2\pi]$ 时，曲线 $y = \sin x$ 与 $y = 2\sin\left(3x - \frac{\pi}{6}ight)$ 的交点个数为（ ）', NULL, 'C', '画出两函数在 $[0, 2\pi]$ 上的图象，根据图象即可求解', NULL, NULL, NULL, NULL, NULL, '3.00', NULL, NULL, NULL, NULL, 7, '0.9800', FALSE, FALSE, 'unreviewed', 'auto_parsed', '2026-07-08 09:20:09.177620+00:00', '2026-07-08 09:20:09.177624+00:00', NULL, 7, NULL, 'M00007', 'MX0010-1-7', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'pending'),
  (8, '8', '', 'single_choice', '数学', '已知函数为 $ f(x) $ 的定义域为 $ \mathbf{R} $，$ f(x) > f(x-1) + f(x-2) $，且当 $ x < 3 $ 时 $ f(x) = x $，则下列结论中一定正确的是（ ）', NULL, 'B', '代入得到 $ f(1)=1, f(2)=2 $，再利用函数性质和不等式的性质，逐渐递推即可判断。', NULL, NULL, NULL, NULL, NULL, '4.00', NULL, NULL, NULL, NULL, 8, '0.9800', FALSE, FALSE, 'unreviewed', 'auto_parsed', '2026-07-08 09:20:09.181077+00:00', '2026-07-08 09:20:09.181081+00:00', NULL, 7, NULL, 'M00008', 'MX0010-0-1', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'pending'),
  (9, '9', '二、选择题', 'multiple_choice', '数学', '为了解推动出口后的亩收入（单位：万元）情况，从该种植区抽取样本，得到推动出口后亩收入的样本均值 $\bar{x} = 2.1$，样本方差 $s^2 = 0.01$，已知该种植区以往的亩收入 $X$ 服从正态分布 $N(1.8, 0.1^2)$，假设推动出口后的亩收入 $Y$ 服从正态分布 $N(\bar{x}, s^2)$，则（ ）（若随机变量 $Z$ 服从正态分布 $N(u, \sigma^2)$，$P(Z < u + \sigma) \approx 0.8413$）', NULL, 'BC', '根据正态分布的3σ原则以及正态分布的对称性即可解出。', NULL, NULL, NULL, NULL, NULL, '3.00', NULL, NULL, NULL, NULL, 9, '0.9800', FALSE, FALSE, 'unreviewed', 'auto_parsed', '2026-07-08 09:20:09.184719+00:00', '2026-07-08 09:20:09.184723+00:00', NULL, 7, NULL, 'M00009', 'MX0010-2-1', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'pending'),
  (10, '10', '二、选择题', 'multiple_choice', '数学', '设函数 $f(x) = (x-1)^2(x-4)$，则（ ）', NULL, '', '', NULL, NULL, NULL, NULL, '[]', '2.00', NULL, NULL, NULL, NULL, 10, '0.9800', FALSE, FALSE, 'need_review', 'auto_parsed', '2026-07-08 09:20:09.188435+00:00', '2026-07-08 09:20:09.188439+00:00', NULL, 7, NULL, 'M0000A', 'MX0010-2-2', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'pending'),
  (11, '10', '一、选择题', 'single_choice', '数学', 'A. $x=3$ 是 $f(x)$ 的极小值点
B. 当 $0<x<1$ 时，$f(x)<f\left(x^{2}ight)$
C. 当 $1<x<2$ 时，$-4<f(2x-1)<0$
D. 当 $-1<x<0$ 时，$f(2-x)>f(x)$', NULL, 'ACD', '【分析】求出函数 $f(x)$ 的导数，得到极值点，即可判断 A；利用函数的单调性可判断 B；根据函数 $f(x)$ 在 $(1,3)$ 上的值域即可判断 C；直接作差可判断 D.', NULL, NULL, NULL, NULL, NULL, '3.00', NULL, NULL, NULL, NULL, 11, '0.9800', FALSE, FALSE, 'unreviewed', 'auto_parsed', '2026-07-08 09:20:09.193125+00:00', '2026-07-08 09:20:09.193129+00:00', NULL, 7, NULL, 'M0000B', 'MX0010-1-8', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'pending'),
  (12, '11', '一、选择题', 'single_choice', '数学', '造型 $\psi$ 可以做成美丽的丝带，将其看作图中曲线 $C$ 的一部分。已知 $C$ 过坐标原点 $O$，且 $C$ 上的点满足横坐标大于 $-2$，到点 $F(2,0)$ 的距离与到定直线 $x=a(a<0)$ 的距离之积为 4，则（ ）', NULL, '', '', NULL, NULL, NULL, NULL, NULL, '4.00', NULL, NULL, NULL, NULL, 12, '0.9800', FALSE, FALSE, 'need_review', 'auto_parsed', '2026-07-08 09:20:09.196514+00:00', '2026-07-08 09:20:09.196518+00:00', NULL, 7, NULL, 'M0000C', 'MX0010-1-9', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'pending'),
  (13, '1', '一、选择题', 'single_choice', '数学', '（根据图像中曲线图及选项推断）设曲线 $ C $ 的方程为 $\sqrt{(x-2)^2 + y^2} \cdot |x - a| = 4$，其中 $ a $ 为常数，且曲线过原点 $ O $，焦点为 $ F(2,0) $。下列说法正确的是：', NULL, 'ABD', '根据题设将原点代入曲线方程后可求 $ a $，故可判断 A 的正误；结合曲线方程可判断 B 的正误；利用特例法可判断 C 的正误；将曲线方程化简后结合不等式的性质可判断 D 的正误。', NULL, NULL, NULL, NULL, NULL, '4.00', NULL, NULL, NULL, NULL, 13, '0.9800', FALSE, FALSE, 'unreviewed', 'auto_parsed', '2026-07-08 09:20:09.200252+00:00', '2026-07-08 09:20:09.200257+00:00', NULL, 7, NULL, 'M0000D', 'MX0010-1-10', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'pending'),
  (14, '14', NULL, 'fill_blank', '数学', '请填写答案：1+1=____。', NULL, '2', '这是一道填空题。', NULL, NULL, NULL, NULL, NULL, '2.00', NULL, NULL, NULL, NULL, 0, NULL, FALSE, TRUE, 'unreviewed', 'auto_parsed', '2026-07-08 09:26:57.443037+00:00', '2026-07-08 09:26:57.443046+00:00', NULL, 7, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'pending'),
  (15, '15', NULL, 'short_answer', '数学', '请简述勾股定理的内容。', NULL, '勾股定理：a²+b²=c²', '这是简答题。', NULL, NULL, NULL, NULL, NULL, '3.00', NULL, NULL, NULL, NULL, 0, NULL, FALSE, TRUE, 'unreviewed', 'auto_parsed', '2026-07-08 09:26:57.446913+00:00', '2026-07-08 09:26:57.446918+00:00', NULL, 7, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, 'pending');

-- ----------------------------
-- Table: tiku_favorite (0 rows)
-- ----------------------------
-- tiku_favorite 表无数据

-- ----------------------------
-- Table: tiku_paper_code_counter (0 rows)
-- ----------------------------
-- tiku_paper_code_counter 表无数据

-- ----------------------------
-- Table: tiku_parse_task (0 rows)
-- ----------------------------
-- tiku_parse_task 表无数据

-- ----------------------------
-- Table: tiku_question_id_counter (0 rows)
-- ----------------------------
-- tiku_question_id_counter 表无数据

-- ----------------------------
-- Table: tiku_question_image (0 rows)
-- ----------------------------
-- tiku_question_image 表无数据

-- ----------------------------
-- Table: tiku_question_option (42 rows)
-- ----------------------------
INSERT INTO "tiku_question_option" ("id", "option_label", "content", "content_html", "bbox", "sort_order", "created_at", "updated_at", "question_id") VALUES
  (9, 'A', '\{-1,0\}', NULL, NULL, 0, '2026-07-08 09:20:09.209420+00:00', '2026-07-08 09:20:09.209426+00:00', 1),
  (10, 'B', '\{2,3\}', NULL, NULL, 1, '2026-07-08 09:20:09.214267+00:00', '2026-07-08 09:20:09.214271+00:00', 1),
  (11, 'C', '\{-3,-1,0\}', NULL, NULL, 2, '2026-07-08 09:20:09.218536+00:00', '2026-07-08 09:20:09.218541+00:00', 1),
  (12, 'D', '\{-1,0,2\}', NULL, NULL, 3, '2026-07-08 09:20:09.222743+00:00', '2026-07-08 09:20:09.222748+00:00', 1),
  (13, 'A', '$-1 - i$', NULL, NULL, 0, '2026-07-08 09:20:09.226806+00:00', '2026-07-08 09:20:09.226811+00:00', 2),
  (14, 'B', '$-1 + i$', NULL, NULL, 1, '2026-07-08 09:20:09.231246+00:00', '2026-07-08 09:20:09.231250+00:00', 2),
  (15, 'C', '$1 - i$', NULL, NULL, 2, '2026-07-08 09:20:09.235488+00:00', '2026-07-08 09:20:09.235493+00:00', 2),
  (16, 'D', '$1 + i$', NULL, NULL, 3, '2026-07-08 09:20:09.239755+00:00', '2026-07-08 09:20:09.239760+00:00', 2),
  (17, 'A', '$-2$', NULL, NULL, 0, '2026-07-08 09:20:09.243804+00:00', '2026-07-08 09:20:09.243808+00:00', 3),
  (18, 'B', '$-1$', NULL, NULL, 1, '2026-07-08 09:20:09.248122+00:00', '2026-07-08 09:20:09.248126+00:00', 3),
  (19, 'C', '$1$', NULL, NULL, 2, '2026-07-08 09:20:09.252194+00:00', '2026-07-08 09:20:09.252199+00:00', 3),
  (20, 'D', '$2$', NULL, NULL, 3, '2026-07-08 09:20:09.256352+00:00', '2026-07-08 09:20:09.256356+00:00', 3),
  (21, 'A', '$-3m$', NULL, NULL, 0, '2026-07-08 09:20:09.260913+00:00', '2026-07-08 09:20:09.260919+00:00', 4),
  (22, 'B', '$-\frac{m}{3}$', NULL, NULL, 1, '2026-07-08 09:20:09.265057+00:00', '2026-07-08 09:20:09.265062+00:00', 4),
  (23, 'C', '$\frac{m}{3}$', NULL, NULL, 2, '2026-07-08 09:20:09.269388+00:00', '2026-07-08 09:20:09.269393+00:00', 4),
  (24, 'D', '$3m$', NULL, NULL, 3, '2026-07-08 09:20:09.273951+00:00', '2026-07-08 09:20:09.273955+00:00', 4),
  (25, 'A', '$2\sqrt{3}\pi$', NULL, NULL, 0, '2026-07-08 09:20:09.278237+00:00', '2026-07-08 09:20:09.278241+00:00', 5),
  (26, 'B', '$3\sqrt{3}\pi$', NULL, NULL, 1, '2026-07-08 09:20:09.282203+00:00', '2026-07-08 09:20:09.282207+00:00', 5),
  (27, 'C', '$6\sqrt{3}\pi$', NULL, NULL, 2, '2026-07-08 09:20:09.286558+00:00', '2026-07-08 09:20:09.286562+00:00', 5),
  (28, 'D', '$9\sqrt{3}\pi$', NULL, NULL, 3, '2026-07-08 09:20:09.290721+00:00', '2026-07-08 09:20:09.290727+00:00', 5),
  (29, 'B', '$[-1,0]$', NULL, NULL, 1, '2026-07-08 09:20:09.295183+00:00', '2026-07-08 09:20:09.295187+00:00', 6),
  (30, 'C', '$[-1,1]$', NULL, NULL, 2, '2026-07-08 09:20:09.299237+00:00', '2026-07-08 09:20:09.299241+00:00', 6),
  (31, 'A', '3', NULL, NULL, 0, '2026-07-08 09:20:09.303244+00:00', '2026-07-08 09:20:09.303249+00:00', 7),
  (32, 'B', '4', NULL, NULL, 1, '2026-07-08 09:20:09.307577+00:00', '2026-07-08 09:20:09.307581+00:00', 7),
  (33, 'C', '6', NULL, NULL, 2, '2026-07-08 09:20:09.311635+00:00', '2026-07-08 09:20:09.311639+00:00', 7),
  (34, 'D', '8', NULL, NULL, 3, '2026-07-08 09:20:09.315568+00:00', '2026-07-08 09:20:09.315572+00:00', 7),
  (35, 'A', '$ f(10) > 100 $', NULL, NULL, 0, '2026-07-08 09:20:09.320112+00:00', '2026-07-08 09:20:09.320117+00:00', 8),
  (36, 'B', '$ f(20) > 1000 $', NULL, NULL, 1, '2026-07-08 09:20:09.324428+00:00', '2026-07-08 09:20:09.324433+00:00', 8),
  (37, 'C', '$ f(10) < 1000 $', NULL, NULL, 2, '2026-07-08 09:20:09.328434+00:00', '2026-07-08 09:20:09.328439+00:00', 8),
  (38, 'D', '$ f(20) < 10000 $', NULL, NULL, 3, '2026-07-08 09:20:09.332395+00:00', '2026-07-08 09:20:09.332399+00:00', 8),
  (39, 'A', '$P(X > 2) > 0.2$', NULL, NULL, 0, '2026-07-08 09:20:09.336869+00:00', '2026-07-08 09:20:09.336876+00:00', 9),
  (40, 'B', '$P(X > 2) < 0.5$', NULL, NULL, 1, '2026-07-08 09:20:09.341338+00:00', '2026-07-08 09:20:09.341343+00:00', 9),
  (41, 'C', '$P(Y > 2) > 0.5$', NULL, NULL, 2, '2026-07-08 09:20:09.345487+00:00', '2026-07-08 09:20:09.345492+00:00', 9),
  (42, 'D', '$P(Y > 2) < 0.8$', NULL, NULL, 3, '2026-07-08 09:20:09.349567+00:00', '2026-07-08 09:20:09.349572+00:00', 9),
  (43, 'A', '$x=3$ 是 $f(x)$ 的极小值点', NULL, NULL, 0, '2026-07-08 09:20:09.353852+00:00', '2026-07-08 09:20:09.353857+00:00', 11),
  (44, 'B', '当 $0<x<1$ 时，$f(x)<f\left(x^{2}ight)$', NULL, NULL, 1, '2026-07-08 09:20:09.358016+00:00', '2026-07-08 09:20:09.358020+00:00', 11),
  (45, 'C', '当 $1<x<2$ 时，$-4<f(2x-1)<0$', NULL, NULL, 2, '2026-07-08 09:20:09.362021+00:00', '2026-07-08 09:20:09.362025+00:00', 11),
  (46, 'D', '当 $-1<x<0$ 时，$f(2-x)>f(x)$', NULL, NULL, 3, '2026-07-08 09:20:09.366149+00:00', '2026-07-08 09:20:09.366154+00:00', 11),
  (47, 'A', 'a = -2', NULL, NULL, 0, '2026-07-08 09:20:09.370338+00:00', '2026-07-08 09:20:09.370344+00:00', 13),
  (48, 'B', '点 $ (2\sqrt{2}, 0) $ 在 $ C $ 上', NULL, NULL, 1, '2026-07-08 09:20:09.374626+00:00', '2026-07-08 09:20:09.374630+00:00', 13),
  (49, 'C', 'C 在第一象限的点的纵坐标的最大值为 1', NULL, NULL, 2, '2026-07-08 09:20:09.378686+00:00', '2026-07-08 09:20:09.378690+00:00', 13),
  (50, 'D', '当点 $ (x_0, y_0) $ 在 $ C $ 上时，$ y_0 \le \frac{4}{x_0 + 2} $', NULL, NULL, 3, '2026-07-08 09:20:09.383357+00:00', '2026-07-08 09:20:09.383364+00:00', 13);

-- ----------------------------
-- Table: tiku_teacher_favorite (0 rows)
-- ----------------------------
-- tiku_teacher_favorite 表无数据

-- ----------------------------
-- Table: tiku_teacher_profile (0 rows)
-- ----------------------------
-- tiku_teacher_profile 表无数据

-- ----------------------------
-- Table: user_account (3 rows)
-- ----------------------------
INSERT INTO "user_account" ("id", "role_type", "login_name", "mobile", "display_name", "avatar_url", "status", "created_at", "updated_at", "last_login", "password", "subject", "stages", "grade_level") VALUES
  (1, 'teacher', NULL, '15883633570', 'User3570', NULL, 'active', '2026-07-06 11:23:28.397283+00:00', '2026-07-08 09:25:00.086789+00:00', '2026-07-08 09:33:28.001703+00:00', '', NULL, NULL, NULL),
  (2, 'student', NULL, '13800000001', '娴嬭瘯瀛︾敓', NULL, 'active', '2026-07-08 03:18:38.307831+00:00', '2026-07-08 03:18:38.307841+00:00', NULL, '', NULL, NULL, NULL),
  (3, 'student', NULL, '19513916986', 'User6986', NULL, 'active', '2026-07-08 07:28:56.480805+00:00', '2026-07-08 09:25:00.089046+00:00', '2026-07-17 03:26:26.856644+00:00', '', NULL, NULL, NULL);

-- ----------------------------
-- Table: users (0 rows)
-- ----------------------------
-- users 表无数据

-- ----------------------------
-- Table: wrong_book_item (3 rows)
-- ----------------------------
INSERT INTO "wrong_book_item" ("id", "question_id", "first_wrong_at", "latest_wrong_at", "wrong_reason_type", "status", "retry_count", "variant_done_count", "student_user_id_id") VALUES
  (5, 4, '2026-07-08 09:25:40.923314+00:00', '2026-07-08 09:25:40.923321+00:00', NULL, 'reviewing', 0, 1, 3),
  (6, 1, '2026-07-08 09:25:40.923505+00:00', '2026-07-08 09:25:40.923510+00:00', NULL, 'mastered', 0, 4, 3),
  (7, 2, '2026-07-08 12:45:34.888498+00:00', '2026-07-08 12:45:34.888508+00:00', NULL, 'not_reviewed', 0, 0, 3);

-- ============================================================
-- 导出完成, 共 54 张表, 316 行数据
-- ============================================================
