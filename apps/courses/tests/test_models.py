"""模型测试 — 覆盖 5 个模型的创建、软删除、唯一约束等核心行为。"""
from django.test import TestCase
from django.db import IntegrityError

from apps.courses.models import (
    Course,
    CourseMaterial,
    CourseTree,
    CourseQuestionLink,
    VariantTask,
)
from apps.accounts.models import UserAccount
from apps.parser.models import ExamQuestion
from apps.papers.models import ExamPaper


class ModelTestCase(TestCase):
    """所有模型测试的基类 — 创建测试用户和基础数据。"""

    def setUp(self):
        self.teacher = UserAccount.objects.create(
            mobile='13800000001',
            display_name='测试教师',
            role_type='teacher',
        )
        self.student = UserAccount.objects.create(
            mobile='13800000002',
            display_name='测试学生',
            role_type='student',
        )
        self.paper = ExamPaper.objects.create(
            title='测试试卷',
            subject='math',
            grade='七年级',
        )
        self.question = ExamQuestion.objects.create(
            paper=self.paper,
            question_no='1',
            question_type='single_choice',
            subject='math',
            stem='测试题目内容',
        )
        self.course = Course.objects.create(
            name='测试课程',
            description='这是一个测试课程',
            subject='math',
            grade_level='七年级',
            teacher=self.teacher,
        )


class CourseModelTest(ModelTestCase):
    """Course 模型测试"""

    def test_course_creation(self):
        """测试课程基本创建 — 所有字段正确保存"""
        course = self.course
        self.assertEqual(course.name, '测试课程')
        self.assertEqual(course.description, '这是一个测试课程')
        self.assertEqual(course.subject, 'math')
        self.assertEqual(course.grade_level, '七年级')
        self.assertEqual(course.teacher, self.teacher)
        self.assertFalse(course.is_deleted)
        self.assertIsNotNone(course.created_at)
        self.assertIsNotNone(course.updated_at)

    def test_course_soft_delete(self):
        """测试软删除 — is_deleted 标记为 True 后仍可查询"""
        course = self.course
        self.assertFalse(course.is_deleted)
        course.is_deleted = True
        course.save()
        # 软删除后仍可查询
        deleted = Course.objects.get(pk=course.pk)
        self.assertTrue(deleted.is_deleted)


class CourseMaterialModelTest(ModelTestCase):
    """CourseMaterial 模型测试"""

    def test_course_material_creation(self):
        """测试课程资料创建 — 包括文件大小和类型"""
        material = CourseMaterial.objects.create(
            course=self.course,
            name='课程讲义.pdf',
            file_path='/media/courses/1/materials/lecture.pdf',
            file_type='pdf',
            file_size=1024000,
            mime_type='application/pdf',
            uploaded_by=self.teacher,
        )
        self.assertEqual(material.course, self.course)
        self.assertEqual(material.name, '课程讲义.pdf')
        self.assertEqual(material.file_type, 'pdf')
        self.assertEqual(material.file_size, 1024000)
        self.assertEqual(material.mime_type, 'application/pdf')
        self.assertFalse(material.is_deleted)
        self.assertIsNotNone(material.created_at)


class CourseTreeModelTest(ModelTestCase):
    """CourseTree 模型测试"""

    def test_course_tree_hierarchy(self):
        """测试课程树层级结构 — 父节点与子节点关系"""
        # 创建根节点
        root = CourseTree.objects.create(
            course=self.course,
            parent=None,
            name='第一章',
            sort_order=1,
        )
        # 创建子节点
        child = CourseTree.objects.create(
            course=self.course,
            parent=root,
            name='第一节',
            sort_order=1,
        )
        # 验证层级关系
        self.assertIsNone(root.parent)
        self.assertEqual(child.parent, root)
        # 验证 ordering
        children = list(CourseTree.objects.filter(parent=root))
        self.assertIn(child, children)
        self.assertEqual(len(children), 1)


class CourseQuestionLinkModelTest(ModelTestCase):
    """CourseQuestionLink 模型测试"""

    def test_course_question_link(self):
        """测试习题关联 — 创建关联记录"""
        tree_node = CourseTree.objects.create(
            course=self.course,
            name='第一章',
            sort_order=1,
        )
        link = CourseQuestionLink.objects.create(
            course=self.course,
            tree_node=tree_node,
            question=self.question,
            source='manual',
            source_course_name='源课程名称',
        )
        self.assertEqual(link.course, self.course)
        self.assertEqual(link.tree_node, tree_node)
        self.assertEqual(link.question, self.question)
        self.assertEqual(link.source, 'manual')
        self.assertEqual(link.source_course_name, '源课程名称')
        self.assertFalse(link.is_deleted)
        self.assertIsNotNone(link.created_at)

    def test_course_question_link_unique_together(self):
        """测试唯一约束 — 同一课程和题目不能重复关联"""
        CourseQuestionLink.objects.create(
            course=self.course,
            question=self.question,
            source='manual',
        )
        # 重复创建应失败
        with self.assertRaises(IntegrityError):
            CourseQuestionLink.objects.create(
                course=self.course,
                question=self.question,
                source='import',
            )


class VariantTaskModelTest(ModelTestCase):
    """VariantTask 模型测试"""

    def test_variant_task_creation(self):
        """测试变式题任务创建 — 包括 JSON 字段"""
        task = VariantTask.objects.create(
            original_question=self.question,
            variant_mode='difficulty_change',
            status='pending',
            generator_result={'difficulty': 'hard', 'result': '生成的题目'},
        )
        self.assertEqual(task.original_question, self.question)
        self.assertEqual(task.variant_mode, 'difficulty_change')
        self.assertEqual(task.status, 'pending')
        self.assertIsNotNone(task.created_at)
        self.assertIsNone(task.completed_at)
        self.assertEqual(task.generator_result['difficulty'], 'hard')
        self.assertIsNone(task.verifier_result)
        self.assertIsNone(task.generated_question)
        self.assertIsNone(task.error_message)
