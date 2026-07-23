"""
路径A（重建表法）：删除业务表 + 清迁移记录
为 UUID 结构的全新 makemigrations/migrate 做准备
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.db import connection

# 33 张 Django 托管的业务表
BUSINESS_TABLES = [
    'user_account', 'student_parent_bind',
    'knowledge_points',
    'learning_mission', 'mission_level', 'mission_question_rel',
    'institution', 'institution_member', 'class', 'class_teacher',
    'class_student', 'class_join_request',
    'tiku_exam_paper', 'tiku_parse_task', 'tiku_paper_code_counter', 'tiku_question_id_counter',
    'tiku_exam_page', 'tiku_ai_parse_result', 'tiku_exam_question',
    'tiku_question_option', 'tiku_question_image',
    'student_mission_progress', 'student_level_progress', 'answer_attempt',
    'tiku_favorite', 'ai_guidance_session',
    'wrong_book_item', 'mastery_record',
    'course', 'course_material', 'course_tree', 'course_question_link', 'course_variant_task',
]

# django_admin_log.user_id 引用 user_account，需一并重建（让 user_id 跟随 UUID 主键）
EXTRA_TABLES = ['django_admin_log']

# 需重置迁移记录的 app（业务9个 + admin，因 django_admin_log 重建）
APPS_TO_RESET = [
    'accounts', 'knowledge', 'missions', 'institutions',
    'papers', 'parser', 'study', 'wrongbook', 'courses',
    'admin',  # django_admin_log 重建
]

print("=" * 60)
print("路径A：删除业务表 + 清迁移记录")
print("=" * 60)

with connection.cursor() as cur:
    connection.autocommit = True

    # 1. 删除业务表 + django_admin_log（CASCADE 级联删外键约束）
    print("\n[1] 删除业务表...")
    dropped = 0
    for t in BUSINESS_TABLES + EXTRA_TABLES:
        cur.execute(f'DROP TABLE IF EXISTS "{t}" CASCADE;')
        dropped += 1
    print(f"    已处理 {dropped} 张表（DROP IF EXISTS CASCADE）")

    # 2. 清空迁移记录
    print("\n[2] 清空迁移记录...")
    for a in APPS_TO_RESET:
        cur.execute(f"DELETE FROM django_migrations WHERE app='{a}';")
        print(f"    清空 app={a}")

    # 3. 验证
    print("\n[3] 验证...")
    cur.execute("""
        SELECT COUNT(*) FROM information_schema.tables
        WHERE table_schema='public' AND table_type='BASE TABLE';
    """)
    remaining = cur.fetchone()[0]
    print(f"    剩余表数: {remaining}（应为框架表: auth_*/django_*/sessions 等）")

    cur.execute("SELECT COUNT(*) FROM django_migrations WHERE app IN ('accounts','knowledge','missions','institutions','papers','parser','study','wrongbook','courses','admin');")
    mig = cur.fetchone()[0]
    print(f"    剩余业务迁移记录: {mig}（应为 0）")

print("\n[OK] 准备就绪，下一步：makemigrations + migrate")
print("=" * 60)
