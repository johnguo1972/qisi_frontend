import pytest
from django.db import connection
from rest_framework.test import APIClient

from apps.accounts.models import UserAccount
from apps.papers.models import ExamPaper
from apps.parser.models import ExamQuestion


@pytest.fixture
def knowledge_point_table(db):
    with connection.cursor() as cursor:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_points (
                id BIGINT PRIMARY KEY,
                subject VARCHAR(50),
                stage VARCHAR(20),
                grade_index SMALLINT,
                grade_name VARCHAR(20),
                term VARCHAR(10),
                chapter VARCHAR(255),
                module VARCHAR(255),
                node_type VARCHAR(20),
                content TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("DELETE FROM knowledge_points")
        cursor.execute(
            """
            INSERT INTO knowledge_points
                (id, subject, stage, grade_index, grade_name, term, chapter, module, node_type, content)
            VALUES (9001, 'physics', 'junior', 8, 'Grade 8', 'up', 'Motion', 'Speed', 'general', 'Speed')
            """
        )
    yield
    with connection.cursor() as cursor:
        cursor.execute("DELETE FROM knowledge_points")


@pytest.fixture
def physics_teacher(db):
    return UserAccount.objects.create(
        role_type='teacher',
        mobile='13900009701',
        display_name='Physics Teacher',
        subject='physics',
        subjects=['physics'],
        stages=['junior'],
    )


@pytest.fixture
def teacher_client(physics_teacher):
    client = APIClient()
    client.force_authenticate(user=physics_teacher)
    return client


@pytest.fixture
def junior_physics_paper(db):
    return ExamPaper.objects.create(
        title='Junior Physics Paper',
        subject='physics',
        stage='junior',
        source_file_path='tests/junior-physics.pdf',
    )


@pytest.mark.django_db
def test_teacher_question_list_rejects_unassigned_subject(teacher_client):
    response = teacher_client.get('/api/v1/questions/', {'subject': 'math'})

    assert response.status_code == 403
    assert response.data['code'] == 'TEACHING_SCOPE_FORBIDDEN'


@pytest.mark.django_db
def test_knowledge_point_filter_matches_any_array_item_and_legacy_module(
    teacher_client, junior_physics_paper, knowledge_point_table
):
    multi_point_question = ExamQuestion.objects.create(
        paper=junior_physics_paper,
        question_no='multi-point',
        question_type='single_choice',
        subject='physics',
        stem='Question with two knowledge points',
        knowledge_points=[{'id': '9000'}, {'id': '9001'}],
    )
    legacy_module_question = ExamQuestion.objects.create(
        paper=junior_physics_paper,
        question_no='legacy-module',
        question_type='single_choice',
        subject='physics',
        stem='Question with a legacy module knowledge point',
        knowledge_points=[{'module': 'Speed'}],
    )

    response = teacher_client.get('/api/v1/questions/', {'knowledge_point_id': '9001'})

    assert response.status_code == 200
    question_ids = {item['id'] for item in response.data['data']['items']}
    assert str(multi_point_question.id) in question_ids
    assert str(legacy_module_question.id) in question_ids
