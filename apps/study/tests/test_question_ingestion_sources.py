from types import SimpleNamespace
from unittest.mock import patch

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import UserAccount
from apps.courses.models import Course, CourseTree
from apps.papers.models import ExamPaper
from apps.parser.models import ExamQuestion
from apps.study import photo_views
from apps.study.models import QuestionIngestionBatch


def _plain_view_handler(decorated_view):
    return decorated_view.cls.post.__closure__[0].cell_contents


@pytest.fixture
def teacher(db):
    return UserAccount.objects.create(
        mobile='13900008201', display_name='Ingestion source teacher', role_type='teacher',
    )


@pytest.fixture
def api_client(teacher):
    client = APIClient()
    client.force_authenticate(user=teacher)
    return client


@pytest.fixture
def paper(teacher):
    return ExamPaper.objects.create(
        title='Ingestion source paper', subject='physics', uploaded_by=teacher,
    )


@pytest.fixture
def course(teacher):
    return Course.objects.create(
        name='Ingestion source course', subject='physics', grade_level='Grade 8', teacher=teacher,
    )


def _create_bank_question(paper, question_no):
    return ExamQuestion.objects.create(
        paper=paper,
        question_no=question_no,
        question_type='short_answer',
        stem=f'Question {question_no}',
    )


@pytest.mark.django_db
def test_manual_question_creation_records_successful_batch_and_normalizes_type(api_client, teacher, paper):
    response = api_client.post(
        '/api/v1/questions/create/',
        {
            'paper_id': str(paper.id),
            'question_no': 'manual-1',
            'question_type': 'single choice',
            'stem': 'Choose the correct answer',
            'answer': 'A',
            'options': [{'label': 'A', 'content': 'Correct'}],
        },
        format='json',
    )

    assert response.status_code == 200
    question = ExamQuestion.objects.get(id=response.data['data']['question_id'])
    assert question.question_type == 'single_choice'
    batch = QuestionIngestionBatch.objects.get(
        actor=teacher, source_type=QuestionIngestionBatch.SourceType.MANUAL_CREATE,
    )
    assert batch.paper_id == paper.id
    assert batch.created_count == 1
    assert batch.status == QuestionIngestionBatch.Status.SUCCESS


@pytest.mark.django_db
def test_manual_creation_error_after_batch_starts_finishes_failed_batch(api_client, teacher, paper):
    with patch(
        'apps.study.create_views.QuestionOption.objects.create',
        side_effect=RuntimeError('option persistence failed'),
    ):
        with pytest.raises(RuntimeError, match='option persistence failed'):
            api_client.post(
                '/api/v1/questions/create/',
                {
                    'paper_id': str(paper.id),
                    'question_type': 'single_choice',
                    'stem': 'Choose the correct answer',
                    'options': [{'label': 'A', 'content': 'Correct'}],
                },
                format='json',
            )

    batch = QuestionIngestionBatch.objects.get(
        actor=teacher, source_type=QuestionIngestionBatch.SourceType.MANUAL_CREATE,
    )
    assert batch.paper_id == paper.id
    assert batch.status == QuestionIngestionBatch.Status.FAILED
    assert batch.failed_count == 1


@pytest.mark.django_db
def test_photo_question_creation_records_successful_batch_and_normalizes_recognized_type(
    teacher, paper, tmp_path, monkeypatch,
):
    crop_dir = tmp_path / 'crops'
    crop_dir.mkdir()
    crop_file = crop_dir / 'question.png'
    crop_file.write_bytes(b'test image')
    monkeypatch.setattr(photo_views.settings, 'MEDIA_ROOT', tmp_path)

    class VisionParser:
        def recognize_photo(self, image_sources):
            assert image_sources == [str(crop_file)]
            return {
                'question_no': 'photo-1',
                'question_type': 'multiple choice',
                'stem': 'Photo-recognized question',
                'answer': 'AB',
                'options': [
                    {'label': 'A', 'content': 'One'},
                    {'label': 'B', 'content': 'Two'},
                ],
            }

        def close(self):
            pass

    request = SimpleNamespace(
        FILES=SimpleNamespace(getlist=lambda _name: []),
        POST={
            'paper_id': str(paper.id),
            'crop_file_path': 'crops/question.png',
            'page_no': '1',
        },
        user=teacher,
    )

    with (
        patch.object(photo_views, 'upload_crop_image_safe', return_value=None),
        patch.object(photo_views, 'vision_parser_component_factory', return_value=VisionParser()),
    ):
        response = _plain_view_handler(photo_views.photo_create_question)(request)

    assert response.status_code == 200
    question = ExamQuestion.objects.get(id=response.data['data']['question_id'])
    assert question.question_type == 'multiple_choice'
    batch = QuestionIngestionBatch.objects.get(
        actor=teacher, source_type=QuestionIngestionBatch.SourceType.PHOTO_CREATE,
    )
    assert batch.paper_id == paper.id
    assert batch.created_count == 1
    assert batch.status == QuestionIngestionBatch.Status.SUCCESS


@pytest.mark.django_db
def test_course_question_link_import_records_course_scoped_batch(api_client, teacher, course, paper):
    question = _create_bank_question(paper, 'course-link-1')

    response = api_client.post(
        f'/api/v1/courses/{course.id}/questions/import/',
        {'question_ids': [str(question.id)]},
        format='json',
    )

    assert response.status_code == 200
    batch = QuestionIngestionBatch.objects.get(
        actor=teacher, source_type=QuestionIngestionBatch.SourceType.COURSE_LINK_IMPORT,
    )
    assert batch.course_id == course.id
    assert batch.created_count == 1
    assert batch.status == QuestionIngestionBatch.Status.SUCCESS


@pytest.mark.django_db
def test_repeated_course_question_link_import_records_zero_created_batch(api_client, teacher, course, paper):
    question = _create_bank_question(paper, 'course-link-repeat')
    endpoint = f'/api/v1/courses/{course.id}/questions/import/'

    assert api_client.post(endpoint, {'question_ids': [str(question.id)]}, format='json').status_code == 200
    response = api_client.post(endpoint, {'question_ids': [str(question.id)]}, format='json')

    assert response.status_code == 200
    batches = QuestionIngestionBatch.objects.filter(
        actor=teacher,
        source_type=QuestionIngestionBatch.SourceType.COURSE_LINK_IMPORT,
    ).order_by('created_at')
    assert list(batches.values_list('created_count', flat=True)) == [1, 0]
    assert batches.last().status == QuestionIngestionBatch.Status.SUCCESS


@pytest.mark.django_db
def test_course_material_import_records_batch_and_normalizes_type(api_client, teacher, course):
    node = CourseTree.objects.create(course=course, name='Source material', sort_order=1)

    response = api_client.post(
        f'/api/v1/courses/{course.id}/import-question/',
        {
            'tree_node_id': str(node.id),
            'question_no': 'material-1',
            'question': {
                'question_type': 'single choice',
                'stem': 'Imported course material question',
                'answer': 'A',
                'options': {'A': 'Correct'},
            },
        },
        format='json',
    )

    assert response.status_code == 201
    question = ExamQuestion.objects.get(id=response.data['data']['question_id'])
    assert question.question_type == 'single_choice'
    batch = QuestionIngestionBatch.objects.get(
        actor=teacher, source_type=QuestionIngestionBatch.SourceType.COURSE_MATERIAL_IMPORT,
    )
    assert batch.course_id == course.id
    assert batch.paper_id == question.paper_id
    assert batch.created_count == 1
    assert batch.status == QuestionIngestionBatch.Status.SUCCESS
