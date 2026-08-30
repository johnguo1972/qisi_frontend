import os
import tempfile
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.accounts.models import UserAccount
from apps.courses.models import Course, CourseMaterial
from apps.courses import views


class CourseMaterialConversionStatusTests(TestCase):
    def setUp(self):
        self.teacher = UserAccount.objects.create(
            mobile='13800000031',
            display_name='转换状态测试教师',
            role_type='teacher',
        )
        self.course = Course.objects.create(
            name='转换状态测试课程',
            subject='physics',
            grade_level='九年级',
            teacher=self.teacher,
        )

    def test_word_material_can_persist_conversion_lifecycle(self):
        material = CourseMaterial.objects.create(
            course=self.course,
            name='讲义.docx',
            file_path='courses/test/materials/lecture.docx',
            file_type='docx',
            file_size=1024,
            mime_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            uploaded_by=self.teacher,
            conversion_status=CourseMaterial.ConversionStatus.CONVERTING,
        )

        material.converted_pdf_path = 'courses/test/materials/lecture.pdf'
        material.conversion_status = CourseMaterial.ConversionStatus.COMPLETED
        material.save()
        material.refresh_from_db()

        self.assertEqual(
            material.conversion_status,
            CourseMaterial.ConversionStatus.COMPLETED,
        )
        self.assertEqual(
            material.converted_pdf_path,
            'courses/test/materials/lecture.pdf',
        )

    @override_settings(MEDIA_ROOT='/tmp/qisi-material-conversion-tests')
    @patch('apps.courses.convert_service.convert_word_to_pdf')
    def test_conversion_task_marks_material_completed_with_relative_pdf_path(self, convert_word_to_pdf):
        from apps.courses.tasks import convert_course_material

        material = CourseMaterial.objects.create(
            course=self.course,
            name='讲义.docx',
            file_path='courses/test/materials/lecture.docx',
            file_type='docx',
            file_size=1024,
            mime_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            uploaded_by=self.teacher,
            conversion_status=CourseMaterial.ConversionStatus.CONVERTING,
        )
        convert_word_to_pdf.return_value = '/tmp/qisi-material-conversion-tests/courses/test/materials/lecture.pdf'

        result = convert_course_material.run(str(material.id))

        material.refresh_from_db()
        self.assertEqual(result['status'], CourseMaterial.ConversionStatus.COMPLETED)
        self.assertEqual(material.conversion_status, CourseMaterial.ConversionStatus.COMPLETED)
        self.assertEqual(material.converted_pdf_path, 'courses/test/materials/lecture.pdf')

    @patch('apps.courses.convert_service.convert_word_to_pdf', return_value=None)
    def test_conversion_task_marks_material_failed_when_pdf_is_unavailable(self, convert_word_to_pdf):
        from apps.courses.tasks import convert_course_material

        material = CourseMaterial.objects.create(
            course=self.course,
            name='lecture.docx',
            file_path='courses/test/materials/lecture.docx',
            file_type='docx',
            file_size=1024,
            mime_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            uploaded_by=self.teacher,
            conversion_status=CourseMaterial.ConversionStatus.PENDING,
        )

        result = convert_course_material.run(str(material.id))

        material.refresh_from_db()
        self.assertEqual(result['status'], CourseMaterial.ConversionStatus.FAILED)
        self.assertEqual(material.conversion_status, CourseMaterial.ConversionStatus.FAILED)
        self.assertTrue(material.conversion_error)

    def test_preview_returns_conversion_in_progress_without_sync_conversion(self):
        material = CourseMaterial.objects.create(
            course=self.course,
            name='lecture.docx',
            file_path='courses/test/materials/lecture.docx',
            file_type='docx',
            file_size=1024,
            mime_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            uploaded_by=self.teacher,
            conversion_status=CourseMaterial.ConversionStatus.PENDING,
        )
        request = APIRequestFactory().get('/unused')
        force_authenticate(request, user=self.teacher)

        response = views.material_preview(request, self.course.id, material.id)

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data['code'], 'conversion_in_progress')

    @override_settings(MEDIA_ROOT=os.path.join(tempfile.gettempdir(), 'qisi-material-upload-tests'))
    def test_word_upload_returns_pending_status_and_queues_conversion(self):
        uploaded = SimpleUploadedFile(
            'lecture.docx', b'test word content',
            content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        )
        request = APIRequestFactory().post('/unused', {'file': uploaded}, format='multipart')
        force_authenticate(request, user=self.teacher)

        with patch('apps.courses.views._dispatch_material_conversion') as dispatch:
            with self.captureOnCommitCallbacks(execute=True):
                response = views.material_upload(request, self.course.id)

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['data']['conversion_status'], CourseMaterial.ConversionStatus.PENDING)
        dispatch.assert_called_once()
        self.assertEqual(str(dispatch.call_args.args[0]), response.data['data']['id'])
