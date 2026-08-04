"""Tests for papers app."""
from django.test import TestCase
from apps.papers.models import ExamPaper, ParseTask
from apps.common import status as const


class ExamPaperModelTest(TestCase):
    def test_create_exam_paper(self):
        paper = ExamPaper.objects.create(
            title='2024年高考数学试卷',
            subject='数学',
            stage='高中',
            grade='高三',
            paper_type='高考真题',
            has_solution=True,
            source_file_path='exams/1/source/original.docx',
        )
        self.assertEqual(paper.title, '2024年高考数学试卷')
        self.assertEqual(paper.subject, '数学')
        self.assertEqual(paper.status, 'uploaded')
        self.assertEqual(paper.total_pages, 0)
        self.assertEqual(paper.total_questions, 0)
        self.assertTrue(paper.has_solution)

    def test_exam_paper_str(self):
        paper = ExamPaper.objects.create(
            title='测试试卷', subject='物理',
            source_file_path='exams/2/source/test.docx'
        )
        self.assertEqual(str(paper), '测试试卷')


class ParseTaskModelTest(TestCase):
    def test_create_parse_task(self):
        paper = ExamPaper.objects.create(
            title='测试试卷', subject='物理',
            source_file_path='exams/3/source/test.docx'
        )
        task = ParseTask.objects.create(
            paper=paper,
            task_type='full_parse',
            status=const.TASK_RUNNING,
        )
        self.assertEqual(task.task_type, 'full_parse')
        self.assertEqual(task.progress, 0)
        self.assertEqual(task.retry_count, 0)
        self.assertIsNotNone(task.created_at)

    def test_parse_task_str(self):
        paper = ExamPaper.objects.create(
            title='测试试卷', subject='化学',
            source_file_path='exams/4/source/test.docx'
        )
        task = ParseTask.objects.create(
            paper=paper, task_type='full_parse', status=const.TASK_PENDING
        )
        self.assertIn('测试试卷', str(task))
