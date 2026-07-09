#!/usr/bin/env python
"""
题目数据导入脚本（MySQL SQL → PostgreSQL）
从 word/sql/qisi_ai_tutor.sql 提取题目和选项数据，通过Django ORM导入到PostgreSQL数据库

使用方法：
1. 检查脚本内容，确认数据提取逻辑
2. 执行：python word/sql/导入题目数据_脚本.py
3. 验证导入结果：在DBeaver中查看 tiku_exam_question 表

数据来源：
- 题目：154条（tiku_exam_question）
- 选项：232条（tiku_question_option）

导入策略：
- 仅导入前13道题目（ID 1-13，含完整题干、答案、解析）
- 每道题含4个选项（A/B/C/D）
- 自动生成试卷记录（避免外键约束失败）
"""

import os
import sys
import django
import re
from datetime import datetime

# 设置Django环境
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.parser.models import ExamQuestion, QuestionOption, ExamPaper
from apps.accounts.models import UserAccount


def parse_sql_insert_values(line, table_name):
    """
    解析MySQL INSERT语句，提取VALUES部分
    格式：INSERT INTO `table_name` VALUES (1, 'text', ...);
    """
    pattern = r"INSERT INTO `" + table_name + r"` VALUES \((.*?)\);"
    match = re.search(pattern, line)
    if not match:
        return None
    
    values_str = match.group(1)
    
    # 使用简单的解析逻辑：按逗号分割，但需要处理字符串内的逗号
    # MySQL的字符串用单引号包裹，可能包含转义的单引号 \'
    
    values = []
    current = ''
    in_string = False
    escape_next = False
    
    for char in values_str:
        if escape_next:
            current += char
            escape_next = False
        elif char == '\\' and in_string:
            escape_next = True
            current += char  # 保留转义字符，后续处理
        elif char == "'" and not escape_next:
            in_string = not in_string
            current += char
        elif char == ',' and not in_string:
            values.append(current.strip())
            current = ''
        else:
            current += char
    
    if current:
        values.append(current.strip())
    
    return values


def clean_mysql_value(val):
    """清理MySQL值，转换为Python类型"""
    if val == 'NULL':
        return None
    
    # 去掉单引号
    if val.startswith("'") and val.endswith("'"):
        val = val[1:-1]
    
    # 处理转义字符
    val = val.replace("\\'", "'")
    val = val.replace("\\\\", "\\")
    
    return val


def import_questions(sql_file_path, limit=13):
    """导入题目数据"""
    print("=" * 60)
    print("题目数据导入脚本")
    print("=" * 60)
    
    # 读取SQL文件
    with open(sql_file_path, 'r', encoding='utf-8') as f:
        sql_content = f.read()
    
    # 先创建试卷记录（题目表需要paper外键）
    print("\n[步骤1] 创建试卷记录...")
    teacher = UserAccount.objects.filter(role_type='teacher').first()
    if not teacher:
        print("❌ 未找到教师用户，请先修正账号角色")
        return False
    
    paper, created = ExamPaper.objects.get_or_create(
        paper_code='M90001',
        defaults={
            'title': '2026高考数学真题（导入测试）',
            'subject': '数学',
            'stage': '高中',
            'grade': '高三',
            'paper_type': '高考真题',
            'uploaded_by': teacher,
            'source_file_path': '/test/test.pdf',
            'status': 'finished',
            'total_questions': limit,
        }
    )
    print(f"试卷记录：{paper.title} (ID={paper.id}, {'新建' if created else '已存在'})")
    
    # 提取题目INSERT语句
    print("\n[步骤2] 提取题目数据...")
    question_pattern = re.compile(r"INSERT INTO `tiku_exam_question` VALUES \((\d+),.*?\);", re.DOTALL)
    question_matches = question_pattern.findall(sql_content)
    
    # 简化提取：直接查找包含题目ID的行
    question_lines = []
    for line in sql_content.split('\n'):
        if "INSERT INTO `tiku_exam_question` VALUES" in line:
            # 提取题目ID（第一个字段）
            match = re.search(r"VALUES \((\d+),", line)
            if match:
                qid = int(match.group(1))
                if qid <= limit:  # 仅导入前13道题
                    question_lines.append((qid, line))
    
    print(f"找到 {len(question_lines)} 条题目INSERT语句（ID 1-{limit})")
    
    # 导入题目（使用Django ORM，避免SQL语法转换）
    print("\n[步骤3] 导入题目到数据库...")
    imported_count = 0
    
    for qid, line in question_lines[:limit]:
        # 手动解析题目字段（简化版）
        try:
            # 提取VALUES部分
            match = re.search(r"INSERT INTO `tiku_exam_question` VALUES \((.*?)\);", line)
            if not match:
                print(f"  ⚠️ 题目{qid}格式解析失败")
                continue
            
            values_str = match.group(1)
            
            # 粗暴解析：提取前几个关键字段
            # 字段顺序：id, question_no, section_title, question_type, subject, stem, stem_html, answer, analysis...
            
            # 找题号
            qno_match = re.search(r"VALUES \(\d+, '(.*?)',", values_str)
            question_no = qno_match.group(1) if qno_match else str(qid)
            
            # 找题型
            qtype_match = re.search(r"'(single_choice|multiple_choice|fill_blank|short_answer|essay|computation|proof)',", values_str)
            question_type = qtype_match.group(1) if qtype_match else 'single_choice'
            
            # 找题干（stem字段，在subject后）
            stem_match = re.search(r"'数学', '(.*?)', NULL", values_str)
            stem = stem_match.group(1) if stem_match else ''
            stem = stem.replace("\\'", "'").replace("\\\\", "\\")
            
            # 找答案
            answer_match = re.search(r"NULL, '([A-Z]+)',", values_str)
            answer = answer_match.group(1) if answer_match else ''
            
            # 找解析（analysis字段）
            analysis_match = re.search(r", '(.*?)', NULL", values_str)
            analysis = analysis_match.group(1) if analysis_match else ''
            analysis = analysis.replace("\\'", "'").replace("\\\\", "\\")
            
            # 创建题目记录
            question, created = ExamQuestion.objects.update_or_create(
                id=qid,
                defaults={
                    'paper': paper,
                    'question_no': question_no,
                    'question_type': question_type,
                    'subject': '数学',
                    'stem': stem,
                    'answer': answer,
                    'analysis': analysis,
                    'difficulty': 2.0,
                    'parse_status': 'auto_parsed',
                    'review_status': 'unreviewed',
                }
            )
            
            status = "新建" if created else "更新"
            print(f"  ✅ 题目{qid}: {question_type} | {stem[:50]}... [{status}]")
            imported_count += 1
            
        except Exception as e:
            print(f"  ❌ 题目{qid}导入失败: {e}")
            continue
    
    print(f"\n题目导入完成：{imported_count}/{limit} 道")
    
    # 导入选项（关联题目）
    print("\n[步骤4] 导入选项数据...")
    option_lines = []
    for line in sql_content.split('\n'):
        if "INSERT INTO `tiku_question_option` VALUES" in line:
            # 提取选项关联的题目ID（最后一个字段）
            match = re.search(r"VALUES \(\d+, '(A|B|C|D|E)', '(.*?)',.*?, (\d+)\);", line)
            if match:
                label = match.group(1)
                content = match.group(2)
                question_id = int(match.group(4))
                if question_id <= limit:  # 仅导入前13道题的选项
                    option_lines.append((question_id, label, content, line))
    
    option_imported = 0
    for question_id, label, content, line in option_lines:
        try:
            content = content.replace("\\'", "'").replace("\\\\", "\\")
            
            # 查找题目
            question = ExamQuestion.objects.filter(id=question_id).first()
            if not question:
                print(f"  ⚠️ 选项{label}未找到题目{question_id}")
                continue
            
            # 创建选项
            option, created = QuestionOption.objects.update_or_create(
                question=question,
                option_label=label,
                defaults={
                    'content': content,
                    'sort_order': ord(label) - ord('A'),
                }
            )
            
            status = "新建" if created else "更新"
            print(f"  ✅ 题目{question_id}选项{label}: {content[:30]}... [{status}]")
            option_imported += 1
            
        except Exception as e:
            print(f"  ❌ 选项导入失败: {e}")
            continue
    
    print(f"\n选项导入完成：{option_imported} 个")
    
    # 最终统计
    print("\n" + "=" * 60)
    print("导入完成统计")
    print("=" * 60)
    print(f"试卷：{paper.title} (ID={paper.id})")
    print(f"题目：{imported_count} 道（ID 1-{limit})")
    print(f"选项：{option_imported} 个")
    
    # 验证数据
    print("\n[步骤5] 验证数据库...")
    total_questions = ExamQuestion.objects.filter(paper=paper).count()
    total_options = QuestionOption.objects.filter(question__paper=paper).count()
    
    print(f"数据库题目总数：{total_questions}")
    print(f"数据库选项总数：{total_options}")
    
    # 显示样本题目
    print("\n[样本题目展示]")
    for q in ExamQuestion.objects.filter(id__lte=3):
        print(f"  题目{q.id}: {q.question_type} | {q.stem[:60]}...")
        print(f"    答案: {q.answer}")
        print(f"    选项数: {q.options.count()}")
    
    return True


def main():
    """主函数"""
    sql_file = os.path.join(os.path.dirname(__file__), 'qisi_ai_tutor.sql')
    
    if not os.path.exists(sql_file):
        print(f"❌ SQL文件不存在：{sql_file}")
        return False
    
    print("开始导入题目数据...")
    print(f"SQL文件：{sql_file}")
    
    success = import_questions(sql_file, limit=13)
    
    if success:
        print("\n✅ 导入成功！可在DBeaver中查看数据")
        print("提示：")
        print("  - 打开DBeaver")
        print("  - 查看表 tiku_exam_question")
        print("  - 查看表 tiku_question_option")
        print("  - 共13道题目，每题4个选项")
    else:
        print("\n❌ 导入失败，请检查错误信息")
    
    return success


if __name__ == '__main__':
    main()