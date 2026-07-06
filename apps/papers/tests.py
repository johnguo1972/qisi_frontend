"""Tests for papers app."""
from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
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


class UploadPaperAPITest(TestCase):
    def test_upload_docx_success(self):
        """Test uploading a valid .docx file."""
        uploaded_file = SimpleUploadedFile(
            'test_paper.docx',
            b'fake docx content',
            content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )
        response = self.client.post(
            '/api/papers/upload/',
            {
                'file': uploaded_file,
                'title': '测试试卷',
                'subject': '数学',
            },
            format='multipart'
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertIn('paper_id', data)
        self.assertIn('task_id', data)
        self.assertEqual(data['status'], 'uploaded')

        # Verify paper exists in DB
        paper = ExamPaper.objects.get(id=data['paper_id'])
        self.assertEqual(paper.title, '测试试卷')

    def test_upload_non_docx_rejected(self):
        """Test uploading a non-docx file is rejected."""
        uploaded_file = SimpleUploadedFile('test.txt', b'text content')
        response = self.client.post(
            '/api/papers/upload/',
            {'file': uploaded_file, 'title': '测试', 'subject': '数学'},
            format='multipart'
        )
        self.assertEqual(response.status_code, 400)

    def test_upload_missing_file(self):
        """Test uploading without file returns 400."""
        response = self.client.post(
            '/api/papers/upload/',
            {'title': '测试试卷', 'subject': '数学'},
            format='multipart'
        )
        self.assertEqual(response.status_code, 400)


class StartParseAPITest(TestCase):
    def test_start_parse_success(self):
        """Test starting a parse task for an existing paper."""
        paper = ExamPaper.objects.create(
            title='解析测试试卷', subject='数学',
            source_file_path='exams/7/source/test.docx'
        )
        response = self.client.post(f'/api/papers/{paper.id}/parse/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('paper_id', data)
        self.assertIn('task_id', data)
        self.assertIn(data['status'], (const.TASK_PENDING, const.TASK_RUNNING))

        # Verify task was created
        task = ParseTask.objects.filter(paper=paper).first()
        self.assertIsNotNone(task)
        self.assertEqual(task.task_type, 'full_parse')

    def test_start_parse_nonexistent_paper(self):
        """Test parsing a non-existent paper returns 404."""
        response = self.client.post('/api/papers/99999/parse/')
        self.assertEqual(response.status_code, 404)
        data = response.json()
        self.assertIn('error', data)


class HTMXViewsTest(TestCase):
    """Basic smoke tests for HTMX frontend views."""

    def setUp(self):
        ExamPaper.objects.create(
            title='HTMX 测试试卷', subject='物理',
            source_file_path='exams/8/source/test.docx'
        )

    def test_paper_list_page(self):
        """Test paper list page loads."""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '启思AI')
        self.assertContains(response, 'HTMX 测试试卷')

    def test_paper_detail_page(self):
        """Test paper detail page loads."""
        paper = ExamPaper.objects.first()
        response = self.client.get(f'/papers/{paper.id}/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, paper.title)
