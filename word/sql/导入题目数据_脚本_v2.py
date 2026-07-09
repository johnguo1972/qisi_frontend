#!/usr/bin/env python
"""
题目数据导入脚本（MySQL SQL → PostgreSQL）
正确的解析逻辑：逐字符扫描，正确处理字符串、转义、JSON、嵌套逗号

使用方法：
python word/sql/导入题目数据_脚本_v2.py

数据来源：154道题目 + 232个选项
导入范围：前13道题目（含完整题干、答案、解析、选项）
"""

import os
import sys
import re
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from apps.parser.models import ExamQuestion, QuestionOption, ExamPaper
from apps.accounts.models import UserAccount


class MySQLValuesParser:
    """MySQL INSERT VALUES解析器（逐字符扫描）"""
    
    def parse_insert_line(self, line):
        """
        解析MySQL INSERT语句的VALUES部分
        返回字段值列表
        """
        # 提取VALUES(...)部分
        match = re.search(r'VALUES\s*\((.*)\);', line)
        if not match:
            return None
        
        values_str = match.group(1)
        return self._parse_values_string(values_str)
    
    def _parse_values_string(self, s):
        """逐字符解析VALUES字符串"""
        fields = []
        current = ''
        in_string = False
        escape_next = False
        in_json = False
        json_depth = 0
        
        for i, char in enumerate(s):
            # 处理转义字符
            if escape_next:
                current += char
                escape_next = False
                continue
            
            # 遇到反斜杠，标记下一个字符需要转义处理
            if char == '\\' and in_string:
                escape_next = True
                current += char
                continue
            
            # 单引号：字符串边界
            if char == "'":
                if not in_json:  # JSON内部的单引号不作为边界
                    in_string = not in_string
                current += char
                continue
            
            # 方括号：JSON数组边界
            if char == '[':
                json_depth += 1
                in_json = True
                current += char
                continue
            
            if char == ']':
                json_depth -= 1
                if json_depth == 0:
                    in_json = False
                current += char
                continue
            
            # 花括号：JSON对象边界
            if char == '{':
                json_depth += 1
                in_json = True
                current += char
                continue
            
            if char == '}':
                json_depth -= 1
                if json_depth == 0:
                    in_json = False
                current += char
                continue
            
            # 逗号：字段分隔符（仅在字符串外和JSON外）
            if char == ',' and not in_string and not in_json:
                fields.append(current.strip())
                current = ''
                continue
            
            # 其他字符
            current += char
        
        # 最后一个字段
        if current:
            fields.append(current.strip())
        
        return fields
    
    def clean_field_value(self, val):
        """清理字段值，转换为Python类型"""
        if val == 'NULL':
            return None
        
        # 字符串类型：去掉单引号，处理转义
        if val.startswith("'") and val.endswith("'"):
            val = val[1:-1]
            # 处理转义
            val = val.replace("\\'", "'")
            val = val.replace("\\\\", "\\")
            val = val.replace("\\n", "\n")
            val = val.replace("\\r", "\r")
            val = val.replace("\\t", "\t")
            return val
        
        # 数字类型
        try:
            if '.' in val:
                return float(val)
            return int(val)
        except:
            pass
        
        # 其他
        return val


def import_data(sql_file_path, limit=13):
    """导入题目和选项数据"""
    
    parser = MySQLValuesParser()
    
    print("=" * 70)
    print("题目数据导入脚本 v2（正确解析版）")
    print("=" * 70)
    
    # 读取SQL文件
    print(f"\n[步骤1] 读取SQL文件: {sql_file_path}")
    with open(sql_file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # 查找教师用户
    print("\n[步骤2] 查找教师用户...")
    teacher = UserAccount.objects.filter(role_type='teacher').first()
    if not teacher:
        # 尝试修正账号角色
        print("  [WARN] 未找到教师用户，尝试修正账号角色...")
        teacher = UserAccount.objects.filter(mobile='15883633570').first()
        if teacher:
            teacher.role_type = 'teacher'
            teacher.save()
            print(f"  [OK] 账号修正成功: {teacher.mobile} → role_type={teacher.role_type}")
        else:
            print("  [FAIL] 未找到教师用户，导入终止")
            return False
    
    print(f"  [OK] 教师用户: {teacher.mobile} (ID={teacher.id})")
    
    # 创建试卷记录
    print("\n[步骤3] 创建试卷记录...")
    paper, created = ExamPaper.objects.get_or_create(
        paper_code='M90001',
        defaults={
            'title': '2026高考数学真题（导入测试）',
            'subject': '数学',
            'stage': '高中',
            'grade': '高三',
            'paper_type': '高考真题',
            'uploaded_by': teacher,
            'source_file_path': '/test/import.pdf',
            'status': 'finished',
            'total_questions': limit,
            'total_pages': 1,
        }
    )
    print(f"  [OK] 试卷: {paper.title} (ID={paper.id}, {'新建' if created else '已存在'})")
    
    # 解析题目数据
    print(f"\n[步骤4] 解析题目数据（ID 1-{limit})...")
    question_lines = []
    for line in lines:
        if "INSERT INTO `tiku_exam_question` VALUES" in line:
            # 提取题目ID
            match = re.search(r'VALUES\s*\((\d+),', line)
            if match:
                qid = int(match.group(1))
                if qid <= limit:
                    question_lines.append((qid, line))
    
    print(f"  找到 {len(question_lines)} 条题目INSERT语句")
    
    # 导入题目
    print(f"\n[步骤5] 导入题目到数据库...")
    imported_questions = 0
    
    # 字段映射（MySQL → Django）
    # 字段索引：[0]=id, [1]=question_no, [2]=section_title, [3]=question_type, 
    #           [4]=subject, [5]=stem, [6]=stem_html, [7]=answer, [8]=analysis
    
    for qid, line in question_lines:
        try:
            fields = parser.parse_insert_line(line)
            if not fields or len(fields) < 30:
                print(f"  [FAIL] 题目{qid}字段解析失败（字段数={len(fields) if fields else 0})")
                continue
            
            # 提取关键字段
            question_no = parser.clean_field_value(fields[1])
            section_title = parser.clean_field_value(fields[2])
            question_type = parser.clean_field_value(fields[3])
            subject = parser.clean_field_value(fields[4])
            stem = parser.clean_field_value(fields[5])
            answer = parser.clean_field_value(fields[7])
            analysis = parser.clean_field_value(fields[8])
            
            # 提取其他字段
            difficulty = parser.clean_field_value(fields[14])
            if difficulty is None:
                difficulty = 2.0
            
            knowledge_points_str = parser.clean_field_value(fields[13])
            knowledge_points = None
            if knowledge_points_str and knowledge_points_str.startswith('['):
                try:
                    # 清理JSON字符串
                    kp_clean = knowledge_points_str.replace("'", '"')
                    knowledge_points = json.loads(kp_clean)
                except:
                    knowledge_points = None
            
            review_status = parser.clean_field_value(fields[24])
            if review_status is None:
                review_status = 'unreviewed'
            
            system_id = parser.clean_field_value(fields[30])
            paper_question_no = parser.clean_field_value(fields[31])
            
            # 创建题目
            question, created = ExamQuestion.objects.update_or_create(
                id=qid,
                defaults={
                    'paper': paper,
                    'question_no': question_no,
                    'section_title': section_title,
                    'question_type': question_type,
                    'subject': subject,
                    'stem': stem,
                    'answer': answer,
                    'analysis': analysis,
                    'difficulty': difficulty,
                    'knowledge_points': knowledge_points,
                    'review_status': review_status,
                    'parse_status': 'auto_parsed',
                    'sort_order': qid,
                    'system_id': system_id,
                    'paper_question_no': paper_question_no,
                    'confidence': 0.98,
                    'formula_need_review': False,
                    'need_review': False,
                }
            )
            
            status = "新建" if created else "更新"
            stem_preview = stem[:60] if stem else ''
            print(f"  [OK] 题目{qid}: {question_type} | {stem_preview}... [{status}]")
            imported_questions += 1
            
        except Exception as e:
            print(f"  [FAIL] 题目{qid}导入失败: {str(e)[:100]}")
            import traceback
            traceback.print_exc()
            continue
    
    print(f"\n题目导入完成: {imported_questions}/{limit} 道")
    
    # 解析选项数据
    print(f"\n[步骤6] 解析选项数据...")
    option_lines = []
    for line in lines:
        if "INSERT INTO `tiku_question_option` VALUES" in line:
            # 提取选项ID和关联题目ID
            match = re.search(r'VALUES\s*\((\d+),', line)
            if match:
                fields = parser.parse_insert_line(line)
                if fields and len(fields) >= 9:
                    question_id = parser.clean_field_value(fields[8])
                    if question_id and int(question_id) <= limit:
                        option_lines.append((line, fields))
    
    print(f"  找到 {len(option_lines)} 条选项INSERT语句")
    
    # 导入选项
    print(f"\n[步骤7] 导入选项到数据库...")
    imported_options = 0
    
    for line, fields in option_lines:
        try:
            # 字段索引：[0]=id, [1]=option_label, [2]=content, [3]=content_html,
            #           [4]=bbox, [5]=sort_order, [6]=created_at, [7]=updated_at, [8]=question_id
            
            option_label = parser.clean_field_value(fields[1])
            content = parser.clean_field_value(fields[2])
            question_id = parser.clean_field_value(fields[8])
            sort_order = parser.clean_field_value(fields[5])
            
            if sort_order is None:
                sort_order = ord(option_label) - ord('A')
            
            # 查找题目
            question = ExamQuestion.objects.filter(id=question_id).first()
            if not question:
                print(f"  [WARN] 选项{option_label}未找到题目{question_id}")
                continue
            
            # 创建选项
            option, created = QuestionOption.objects.update_or_create(
                question=question,
                option_label=option_label,
                defaults={
                    'content': content,
                    'sort_order': sort_order,
                }
            )
            
            status = "新建" if created else "更新"
            content_preview = content[:30] if content else ''
            print(f"  [OK] 题目{question_id}选项{option_label}: {content_preview}... [{status}]")
            imported_options += 1
            
        except Exception as e:
            print(f"  [FAIL] 选项导入失败: {str(e)[:100]}")
            continue
    
    print(f"\n选项导入完成: {imported_options} 个")
    
    # 最终统计
    print("\n" + "=" * 70)
    print("导入完成统计")
    print("=" * 70)
    print(f"试卷: {paper.title} (ID={paper.id})")
    print(f"题目: {imported_questions} 道（ID 1-{limit})")
    print(f"选项: {imported_options} 个")
    
    # 验证数据
    print("\n[步骤8] 验证数据库...")
    total_questions = ExamQuestion.objects.filter(paper=paper).count()
    total_options = QuestionOption.objects.filter(question__paper=paper).count()
    
    print(f"数据库题目总数: {total_questions}")
    print(f"数据库选项总数: {total_options}")
    
    # 显示样本题目
    print("\n[样本题目展示]")
    for q in ExamQuestion.objects.filter(id__lte=3).order_by('id'):
        stem_preview = q.stem[:80] if q.stem else ''
        print(f"\n题目{q.id} ({q.question_type}):")
        print(f"  题干: {stem_preview}...")
        print(f"  答案: {q.answer}")
        print(f"  选项数: {q.options.count()}")
        if q.options.count() > 0:
            for opt in q.options.all():
                print(f"    {opt.option_label}: {opt.content[:40]}...")
    
    return True


def main():
    """主函数"""
    sql_file = os.path.join(os.path.dirname(__file__), 'qisi_ai_tutor.sql')
    
    if not os.path.exists(sql_file):
        print(f"[FAIL] SQL文件不存在: {sql_file}")
        return False
    
    print("开始导入题目数据...")
    
    success = import_data(sql_file, limit=13)
    
    if success:
        print("\n" + "=" * 70)
        print("[OK] 导入成功！")
        print("=" * 70)
        print("\n下一步操作:")
        print("  1. 在DBeaver中查看表 tiku_exam_question")
        print("  2. 在DBeaver中查看表 tiku_question_option")
        print("  3. 验证数据：题目13道，每题4个选项（共52个）")
        print("  4. 开始阶段1功能验证")
    else:
        print("\n[FAIL] 导入失败，请检查错误信息")
    
    return success


if __name__ == '__main__':
    main()