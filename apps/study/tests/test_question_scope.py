import pytest
from django.db import connection
from rest_framework.test import APIClient

from apps.accounts.models import UserAccount
from apps.papers.models import ExamPaper
from apps.parser.models import ExamQuestion, QuestionOption
from apps.study.models import QuestionTag, QuestionTagRelation


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


@pytest.mark.django_db
def test_knowledge_point_filter_matches_uuid_id_inside_multi_point_array(
    teacher_client, junior_physics_paper
):
    selected_knowledge_point_id = '019fb217-3a21-75c3-b261-c2f4f68f41d6'
    matching_question = ExamQuestion.objects.create(
        paper=junior_physics_paper,
        question_no='uuid-multi-point',
        question_type='single_choice',
        subject='physics',
        stem='Question whose second knowledge point is selected',
        knowledge_points=[
            {'id': '019fb217-37ff-7a41-9172-8598f4b2b7fa'},
            {'id': selected_knowledge_point_id},
        ],
    )
    unrelated_question = ExamQuestion.objects.create(
        paper=junior_physics_paper,
        question_no='uuid-unrelated',
        question_type='single_choice',
        subject='physics',
        stem='Question without the selected knowledge point',
        knowledge_points=[{'id': '019fb217-3a2f-7e90-a52f-d6560031f07d'}],
    )

    response = teacher_client.get(
        '/api/v1/questions/', {'knowledge_point_id': selected_knowledge_point_id}
    )

    assert response.status_code == 200
    question_ids = {item['id'] for item in response.data['data']['items']}
    assert str(matching_question.id) in question_ids
    assert str(unrelated_question.id) not in question_ids


@pytest.mark.django_db
def test_question_list_requires_every_keyword_and_keeps_tag_and_knowledge_filters(
    teacher_client, junior_physics_paper, knowledge_point_table, physics_teacher
):
    """A multi-keyword search must intersect every token with existing filters."""
    tag = QuestionTag.objects.create(name='autumn-practice', created_by=physics_teacher)
    matching_question = ExamQuestion.objects.create(
        paper=junior_physics_paper,
        question_no='keyword-match',
        question_type='single_choice',
        subject='physics',
        stem='Speed analysis question',
        knowledge_points=[{'id': '9001'}],
    )
    QuestionOption.objects.create(
        question=matching_question,
        option_label='A',
        content='Velocity changes over time',
    )
    QuestionTagRelation.objects.create(question=matching_question, tag=tag)

    missing_keyword_question = ExamQuestion.objects.create(
        paper=junior_physics_paper,
        question_no='keyword-missing',
        question_type='single_choice',
        subject='physics',
        stem='Speed stays constant',
        knowledge_points=[{'id': '9001'}],
    )
    QuestionTagRelation.objects.create(question=missing_keyword_question, tag=tag)

    wrong_tag_question = ExamQuestion.objects.create(
        paper=junior_physics_paper,
        question_no='wrong-tag',
        question_type='single_choice',
        subject='physics',
        stem='Speed changes quickly',
        knowledge_points=[{'id': '9001'}],
    )

    response = teacher_client.get(
        '/api/v1/questions/',
        {
            'keyword': 'Speed, changes Speed',
            'knowledge_point_id': '9001',
            'tag': tag.name,
        },
    )

    assert response.status_code == 200
    question_ids = {item['id'] for item in response.data['data']['items']}
    assert question_ids == {str(matching_question.id)}
