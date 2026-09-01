import pytest
from django.db import connection
from rest_framework.test import APIClient

from apps.accounts.models import UserAccount
from apps.courses.models import Course, CourseQuestionLink, CourseTree
from apps.papers.models import ExamPaper
from apps.parser.models import ExamQuestion, QuestionOption
from apps.study.models import QuestionTag, QuestionTagRelation


@pytest.fixture
def teacher(db):
    return UserAccount.objects.create(
        mobile='13900008101',
        display_name='Course question teacher',
        role_type='teacher',
    )


@pytest.fixture
def api_client(teacher):
    client = APIClient()
    client.force_authenticate(user=teacher)
    return client


@pytest.fixture
def course(teacher):
    return Course.objects.create(
        name='Course question filters',
        subject='physics',
        grade_level='Grade 8',
        teacher=teacher,
    )


@pytest.fixture
def node(course):
    return CourseTree.objects.create(course=course, name='Motion', sort_order=1)


@pytest.fixture
def knowledge_point_table(db):
    with connection.cursor() as cursor:
        cursor.execute(
            '''
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
            '''
        )
        cursor.execute('DELETE FROM knowledge_points')
        cursor.execute(
            '''
            INSERT INTO knowledge_points
                (id, subject, stage, grade_index, grade_name, term, chapter, module, node_type, content)
            VALUES (9001, 'physics', 'junior', 8, 'Grade 8', 'up', 'Motion', 'Speed', 'general', 'Speed')
            '''
        )
    yield
    with connection.cursor() as cursor:
        cursor.execute('DELETE FROM knowledge_points')


@pytest.fixture
def questions(course, node, teacher, knowledge_point_table):
    paper = ExamPaper.objects.create(title='Course questions', subject='physics')
    tag = QuestionTag.objects.create(name='autumn-practice', created_by=teacher)
    matching = ExamQuestion.objects.create(
        paper=paper,
        question_no='matching',
        question_type='single_choice',
        subject='physics',
        stem='Speed changes during motion',
        answer='A',
        analysis='Speed is distance divided by time.',
        difficulty='3.2',
        knowledge_points=[{'id': '9001'}],
        ai_answer_a={'answer': 'A'},
    )
    QuestionOption.objects.create(question=matching, option_label='A', content='Correct option')
    QuestionTagRelation.objects.create(question=matching, tag=tag)
    other_node = ExamQuestion.objects.create(
        paper=paper,
        question_no='other-node',
        question_type='single_choice',
        subject='physics',
        stem='Speed changes during motion',
        difficulty='3.2',
        knowledge_points=[{'id': '9001'}],
    )
    CourseQuestionLink.objects.create(course=course, tree_node=node, question=matching, source='manual')
    other_tree_node = CourseTree.objects.create(course=course, name='Force', sort_order=2)
    CourseQuestionLink.objects.create(course=course, tree_node=other_tree_node, question=other_node, source='manual')
    return type('Questions', (), {'matching': matching, 'other_node': other_node})()


@pytest.mark.django_db
def test_course_question_list_defaults_to_all_active_course_links(api_client, course, questions):
    response = api_client.get(f'/api/v1/courses/{course.id}/questions/')

    assert response.status_code == 200
    assert {item['id'] for item in response.data['data']['items']} == {
        str(questions.matching.id),
        str(questions.other_node.id),
    }


@pytest.mark.django_db
def test_course_question_list_rejects_foreign_course_node(api_client, course, teacher):
    foreign_course = Course.objects.create(
        name='Foreign course', subject='physics', grade_level='Grade 8',
        teacher=teacher,
    )
    foreign_node = CourseTree.objects.create(course=foreign_course, name='Foreign node', sort_order=1)

    response = api_client.get(
        f'/api/v1/courses/{course.id}/questions/', {'tree_node_id': str(foreign_node.id)}
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_course_question_list_rejects_malformed_tree_node_id(api_client, course):
    response = api_client.get(
        f'/api/v1/courses/{course.id}/questions/', {'tree_node_id': 'not-a-uuid'}
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_course_question_list_filters_only_current_node(api_client, course, node, questions):
    response = api_client.get(
        f'/api/v1/courses/{course.id}/questions/',
        {
            'tree_node_id': str(node.id),
            'keyword': 'Speed, changes',
            'knowledge_point_id': '9001',
            'tag': 'autumn-practice',
            'question_type': 'single_choice',
            'difficulty': '3.2',
            'page': 1,
            'page_size': 20,
        },
    )

    assert response.status_code == 200
    assert [item['id'] for item in response.data['data']['items']] == [str(questions.matching.id)]
    assert response.data['data']['total'] == 1
    assert str(questions.other_node.id) not in [item['id'] for item in response.data['data']['items']]


@pytest.mark.django_db
def test_course_question_list_applies_each_filter_within_the_same_node(api_client, course, node, questions):
    paper = ExamPaper.objects.get(title='Course questions')
    wrong_difficulty = ExamQuestion.objects.create(
        paper=paper, question_no='same-node-wrong-difficulty', question_type='single_choice',
        subject='physics', stem='Speed changes during motion', difficulty='5.0',
        knowledge_points=[{'id': '9001'}],
    )
    CourseQuestionLink.objects.create(course=course, tree_node=node, question=wrong_difficulty, source='manual')

    response = api_client.get(
        f'/api/v1/courses/{course.id}/questions/',
        {'tree_node_id': str(node.id), 'question_type': 'single_choice', 'difficulty': '3.2', 'knowledge_point_id': '9001'},
    )

    assert response.status_code == 200
    assert [item['id'] for item in response.data['data']['items']] == [str(questions.matching.id)]


@pytest.mark.django_db
def test_course_remove_only_soft_deletes_link(api_client, course, node, knowledge_point_table):
    paper = ExamPaper.objects.create(title='Soft delete question', subject='physics')
    question = ExamQuestion.objects.create(
        paper=paper,
        question_no='soft-delete',
        question_type='single_choice',
        stem='Keep the question in the question bank',
    )
    CourseQuestionLink.objects.create(course=course, tree_node=node, question=question, source='manual')

    response = api_client.post(
        f'/api/v1/courses/{course.id}/questions/batch-delete/',
        {'question_ids': [str(question.id)], 'tree_node_id': str(node.id)},
        format='json',
    )

    assert response.status_code == 200
    assert ExamQuestion.objects.filter(id=question.id).exists()
    assert CourseQuestionLink.objects.get(course=course, question=question).is_deleted is True


@pytest.mark.django_db
def test_course_batch_mutations_only_change_links_in_the_supplied_source_node(api_client, course, node):
    paper = ExamPaper.objects.create(title='Scoped link mutations', subject='physics')
    question = ExamQuestion.objects.create(paper=paper, question_no='scoped-link', question_type='single_choice')
    source_link = CourseQuestionLink.objects.create(course=course, tree_node=node, question=question, source='manual')
    other_node = CourseTree.objects.create(course=course, name='Other source', sort_order=2)
    other_question = ExamQuestion.objects.create(paper=paper, question_no='other-link', question_type='single_choice')
    other_link = CourseQuestionLink.objects.create(course=course, tree_node=other_node, question=other_question, source='manual')

    delete_response = api_client.post(
        f'/api/v1/courses/{course.id}/questions/batch-delete/',
        {'question_ids': [str(question.id), str(other_question.id)], 'tree_node_id': str(node.id)},
        format='json',
    )

    assert delete_response.status_code == 200
    source_link.refresh_from_db()
    other_link.refresh_from_db()
    assert source_link.is_deleted is True
    assert other_link.is_deleted is False

    target = CourseTree.objects.create(course=course, name='Target', sort_order=3)
    move_response = api_client.post(
        f'/api/v1/courses/{course.id}/questions/batch-move/',
        {
            'question_ids': [str(other_question.id)],
            'tree_node_id': str(node.id),
            'target_node_id': str(target.id),
        },
        format='json',
    )

    assert move_response.status_code == 200
    other_link.refresh_from_db()
    assert other_link.tree_node_id == other_node.id


@pytest.mark.django_db
def test_course_batch_mutations_reject_a_source_node_from_another_course(api_client, course, teacher, node):
    paper = ExamPaper.objects.create(title='Foreign source node', subject='physics')
    question = ExamQuestion.objects.create(paper=paper, question_no='foreign-source', question_type='single_choice')
    link = CourseQuestionLink.objects.create(course=course, tree_node=node, question=question, source='manual')
    foreign_course = Course.objects.create(name='Foreign', subject='physics', grade_level='Grade 8', teacher=teacher)
    foreign_node = CourseTree.objects.create(course=foreign_course, name='Foreign node', sort_order=1)

    response = api_client.post(
        f'/api/v1/courses/{course.id}/questions/batch-delete/',
        {'question_ids': [str(question.id)], 'tree_node_id': str(foreign_node.id)},
        format='json',
    )

    assert response.status_code == 404
    link.refresh_from_db()
    assert link.is_deleted is False


@pytest.mark.django_db
def test_course_batch_mutations_reject_malformed_source_node_ids(api_client, course, node):
    paper = ExamPaper.objects.create(title='Malformed source node', subject='physics')
    question = ExamQuestion.objects.create(paper=paper, question_no='malformed-source', question_type='single_choice')
    link = CourseQuestionLink.objects.create(course=course, tree_node=node, question=question, source='manual')

    response = api_client.post(
        f'/api/v1/courses/{course.id}/questions/batch-delete/',
        {'question_ids': [str(question.id)], 'tree_node_id': 'not-a-uuid'},
        format='json',
    )

    assert response.status_code == 400
    link.refresh_from_db()
    assert link.is_deleted is False
