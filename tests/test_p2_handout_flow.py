import pytest
from rest_framework.test import APIClient

from apps.courses.models import Course, CourseClass, CourseHandout
from apps.handouts.models import Handout, HandoutQuestion
from apps.knowledge.models import KnowledgePoint, QuestionKnowledgeMatch
from apps.missions.models import LearningMission, MissionLevel, MissionQuestionRel
from apps.missions.pdf_service import _mission_questions
from apps.study.models import AnswerAttempt, StudentMissionProgress


@pytest.mark.django_db
def test_question_matching_preview_rebuild_and_confirm(teacher_user, sample_question):
    client = APIClient()
    client.force_authenticate(user=teacher_user)
    point = KnowledgePoint.objects.create(
        subject='math', stage='junior', grade_index=9, grade_name='9', term='up',
        chapter='一元一次方程', module='解方程', node_type='method', content='移项',
    )
    sample_question.stem = '请使用解方程的方法完成下列计算。'
    sample_question.save(update_fields=['stem'])
    response = client.post('/api/v1/questions/knowledge-matches/preview', {'question_ids': [str(sample_question.id)]}, format='json')
    assert response.status_code == 200
    assert response.data['code'] == 0
    assert response.data['meta'] == {}
    assert response.data['trace_id']
    assert response.data['data'][0]['matches'][0]['knowledge_point']['id'] == point.id
    response = client.post(f'/api/v1/questions/{sample_question.id}/knowledge-matches/rebuild', {}, format='json')
    assert response.status_code == 200
    match = QuestionKnowledgeMatch.objects.get(question=sample_question)
    response = client.post('/api/v1/questions/knowledge-matches/batch-confirm', {'matches': [{'id': str(match.id), 'status': 'confirmed'}]}, format='json')
    assert response.status_code == 200
    match.refresh_from_db()
    sample_question.refresh_from_db()
    assert match.status == 'confirmed'
    assert any(str(item.get('id')) == str(point.id) for item in sample_question.knowledge_points)


@pytest.mark.django_db
def test_handout_snapshot_publish_and_pdf_export(teacher_user, sample_question, sample_institution, tmp_path, settings):
    sample_question.review_status = 'confirmed'
    sample_question.save(update_fields=['review_status'])
    course = Course.objects.create(name='P2 课程', subject='math', grade_level='9', teacher=teacher_user, institution=sample_institution)
    client = APIClient()
    client.force_authenticate(user=teacher_user)
    response = client.post('/api/v1/handouts/', {'name': '一次方程讲义', 'subject': 'math', 'grade': '9', 'course': str(course.id)}, format='json')
    assert response.status_code == 201
    handout_id = response.data['data']['id']
    response = client.post(f'/api/v1/handouts/{handout_id}/questions/replace/', {'question_ids': [str(sample_question.id)]}, format='json')
    assert response.status_code == 200
    original_stem = HandoutQuestion.objects.get(handout_id=handout_id).display_snapshot['stem']
    sample_question.stem = '后来题目发生了修改。'
    sample_question.save(update_fields=['stem'])
    response = client.get(f'/api/v1/handouts/{handout_id}/preview/')
    assert response.status_code == 200
    assert response.data['data']['questions'][0]['display_snapshot']['stem'] == original_stem
    response = client.post(f'/api/v1/handouts/{handout_id}/publish/', {}, format='json')
    assert response.status_code == 200
    settings.MEDIA_ROOT = tmp_path
    response = client.post(f'/api/v1/handouts/{handout_id}/export-pdf/', {}, format='json')
    assert response.status_code == 200
    assert '_handout_' not in response.data['data']['pdf_file_path']
    assert (tmp_path / response.data['data']['pdf_file_path']).exists()


@pytest.mark.django_db
def test_course_supports_multiple_classes_and_handouts(teacher_user, sample_institution, sample_class, sample_question):
    course = Course.objects.create(name='多班级课程', subject='math', grade_level='9', teacher=teacher_user, institution=sample_institution)
    from apps.institutions.models import Class, ClassTeacher
    second_class = Class.objects.create(institution=sample_institution, class_name='第二班', creator_teacher=teacher_user)
    ClassTeacher.objects.create(class_obj=second_class, teacher=teacher_user, role='owner')
    client = APIClient()
    client.force_authenticate(user=teacher_user)
    for cls in (sample_class, second_class):
        response = client.post(f'/api/v1/courses/{course.id}/classes/', {'class_id': str(cls.id)}, format='json')
        assert response.status_code == 201
    assert CourseClass.objects.filter(course=course, status='active').count() == 2
    sample_question.review_status = 'confirmed'
    sample_question.save(update_fields=['review_status'])
    handout = Handout.objects.create(name='多班级讲义', subject='math', creator_teacher=teacher_user, course=course)
    HandoutQuestion.objects.create(handout=handout, question=sample_question, sort_no=1, display_snapshot={'stem': sample_question.stem})
    response = client.post(f'/api/v1/courses/{course.id}/handouts/', {'handout_id': str(handout.id)}, format='json')
    assert response.status_code == 201
    assert CourseHandout.objects.filter(course=course, handout=handout, status='active').exists()
    response = client.get(f'/api/v1/courses/{course.id}/classes/')
    assert response.status_code == 200
    assert len(response.data['data']) == 2


@pytest.mark.django_db
def test_published_handout_mission_keeps_question_snapshot(teacher_user, sample_institution, sample_class, sample_question):
    from apps.missions.models import LearningMission, MissionQuestionRel
    course = Course.objects.create(name='任务课程', subject='math', grade_level='9', teacher=teacher_user, institution=sample_institution)
    client = APIClient()
    client.force_authenticate(user=teacher_user)
    client.post(f'/api/v1/courses/{course.id}/classes/', {'class_id': str(sample_class.id)}, format='json')
    handout = Handout.objects.create(name='发布讲义', subject='math', creator_teacher=teacher_user, course=course, status='published')
    snapshot = {'id': str(sample_question.id), 'stem': '发布时的题干', 'question_type': sample_question.question_type, 'options_html': [], 'image_items': []}
    HandoutQuestion.objects.create(handout=handout, question=sample_question, sort_no=1, display_snapshot=snapshot)
    response = client.post(f'/api/v1/courses/{course.id}/generate-mission/', {
        'handout_id': str(handout.id), 'class_id': str(sample_class.id),
    }, format='json')
    assert response.status_code == 201
    relation = MissionQuestionRel.objects.get(mission_id=response.data['data']['mission_id'])
    assert relation.source_type == 'handout_snapshot'
    assert relation.question_snapshot['stem'] == '发布时的题干'

    # An explicit empty image snapshot must stay empty even when the source
    # question gains a new image after publication.
    from apps.parser.models import QuestionImage
    QuestionImage.objects.create(
        paper=sample_question.paper, question=sample_question,
        file_path='uploads/added-after-publish.png', image_type='illustration',
    )
    pdf_question = _mission_questions(relation.mission)[0]
    assert pdf_question['image_items'] == []
    assert pdf_question['image_urls'] == []


@pytest.mark.django_db
def test_published_mission_snapshot_is_used_for_student_display_and_draft_grading(
    student_client, student_user, sample_question, sample_class,
):
    from apps.institutions.models import ClassStudent

    ClassStudent.objects.create(
        class_obj=sample_class, student=student_user, join_type='manual', status='active',
    )
    mission = LearningMission.objects.create(
        mission_name='快照作业', status='published', class_obj=sample_class,
        creator_teacher_id=sample_question.paper.uploaded_by,
    )
    level = MissionLevel.objects.create(
        mission=mission, level_no=1, level_name='快照关卡', level_type='practice',
    )
    MissionQuestionRel.objects.create(
        mission=mission, level=level, question_id=sample_question.id,
        source_type='handout_snapshot',
        question_snapshot={
            'id': str(sample_question.id), 'stem': '发布时题干',
            'question_type': 'single_choice', 'answer': 'A',
            'options_html': [{'label': 'A', 'content': '发布时选项'}],
            'image_items': [],
        },
    )
    StudentMissionProgress.objects.create(mission=mission, student_user_id=student_user)

    # The source question changes after publication. Both read and grade must
    # continue to use the immutable A-answer snapshot.
    sample_question.stem = '后来修改的题干'
    sample_question.answer = 'B'
    sample_question.save(update_fields=['stem', 'answer'])

    detail = student_client.get(f'/api/v1/student/levels/{level.id}')
    assert detail.status_code == 200
    assert detail.data['data']['questions'][0]['stem'] == '发布时题干'
    assert detail.data['data']['questions'][0]['options'][0]['content'] == '发布时选项'

    start = student_client.post('/api/v1/student/attempts/start', {
        'question_id': str(sample_question.id), 'mission_id': str(mission.id),
        'level_id': str(level.id),
    }, format='json')
    assert start.status_code == 200
    submit = student_client.post(
        f"/api/v1/student/attempts/{start.data['data']['attempt_id']}/submit",
        {'answer_content': {'selected_options': ['A']}}, format='json',
    )
    assert submit.status_code == 200
    assert submit.data['data']['is_correct'] is True
    assert AnswerAttempt.objects.get(pk=start.data['data']['attempt_id']).is_correct is True


@pytest.mark.django_db
def test_knowledge_matching_filters_exact_paper_grade(teacher_user, sample_question):
    from apps.knowledge.matching import suggest_matches

    point8 = KnowledgePoint.objects.create(
        subject='math', stage='junior', grade_index=8, grade_name='8', term='up',
        chapter='一次方程', module='解方程', node_type='method', content='移项',
    )
    point9 = KnowledgePoint.objects.create(
        subject='math', stage='junior', grade_index=9, grade_name='9', term='up',
        chapter='一次方程', module='解方程', node_type='method', content='移项',
    )
    sample_question.stem = '请使用解方程的方法完成计算。'
    sample_question.save(update_fields=['stem'])
    matches = suggest_matches(sample_question, ('junior',))
    assert [item['knowledge_point'].id for item in matches] == [point9.id]


@pytest.mark.django_db
def test_p2_validation_errors_keep_the_documented_api_envelope(teacher_user):
    client = APIClient()
    client.force_authenticate(user=teacher_user)

    response = client.post('/api/v1/handouts/', {}, format='json')
    assert response.status_code == 400
    assert response.data['code'] == 400
    assert response.data['data'] is None
    assert response.data['meta'] == {}
    assert response.data['trace_id']

    response = client.post('/api/v1/questions/knowledge-matches/rebuild', {'limit': 'bad'}, format='json')
    assert response.status_code == 400
    assert response.data['code'] == 400
    assert response.data['data'] is None
    assert response.data['trace_id']
