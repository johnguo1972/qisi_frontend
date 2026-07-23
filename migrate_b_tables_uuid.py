"""
B 类表 id → uuid v7（修正：IDENTITY 列需先 DROP IDENTITY）
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.db import connection

B_TABLES = [
    'alert_logs', 'api_task_logs', 'dlq_messages', 'gemini_results',
    'llm_audit', 'monitoring_metrics', 'problem_results', 'problems',
    'retry_queue', 'rollback_logs', 'system_config', 'task_outbox', 'users',
    'tiku_teacher_favorite', 'tiku_teacher_profile',
]

print("=" * 60)
print("B 类表 id → uuid v7")
print("=" * 60)

with connection.cursor() as c:
    connection.autocommit = True

    success = 0
    failed = []
    for t in B_TABLES:
        try:
            # 1. 删主键约束（CASCADE）
            c.execute(
                "SELECT conname FROM pg_constraint WHERE conrelid=%s::regclass AND contype='p'",
                [t]
            )
            row = c.fetchone()
            if row and row[0]:
                c.execute(f'ALTER TABLE "{t}" DROP CONSTRAINT IF EXISTS "{row[0]}" CASCADE')

            # 2. 删 IDENTITY（若是 identity 列；非 identity 会报错，忽略）
            try:
                c.execute(f'ALTER TABLE "{t}" ALTER COLUMN id DROP IDENTITY')
            except Exception:
                pass  # 非 identity 列，忽略

            # 3. 删 DEFAULT（nextval 等）
            c.execute(f'ALTER TABLE "{t}" ALTER COLUMN id DROP DEFAULT')

            # 4. 改类型为 uuid
            c.execute(f'ALTER TABLE "{t}" ALTER COLUMN id TYPE uuid USING uuidv7()')

            # 5. 设默认 uuidv7()
            c.execute(f'ALTER TABLE "{t}" ALTER COLUMN id SET DEFAULT uuidv7()')

            # 6. 重建主键
            c.execute(f'ALTER TABLE "{t}" ADD PRIMARY KEY (id)')

            # 7. 删旧 sequence
            c.execute(f'DROP SEQUENCE IF EXISTS "{t}_id_seq"')

            print(f"  [OK] {t}")
            success += 1
        except Exception as e:
            err = str(e).split('\n')[0]
            print(f"  [FAIL] {t}: {err}")
            failed.append((t, err))

print(f"\n汇总: 成功 {success}/{len(B_TABLES)}")
if failed:
    print("失败:", [f[0] for f in failed])
print("=" * 60)
