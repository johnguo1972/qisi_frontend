import pytest
from rest_framework.test import APIClient

from apps.courses.models import Course, CourseClass, CourseHandout, CourseQuestionLink, CourseTree
from apps.handouts.models import Handout, HandoutQuestion
from apps.knowledge.models import KnowledgePoint, QuestionKnowledgeMatch
from apps.missions.models import LearningMission, MissionClassAssignment, MissionLevel, MissionQuestionRel
from apps.missions.pdf_service import _mission_questions
from apps.missions.services import ordered_mission_question_rels
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
def test_course_practice_generate_persists_source_dates_and_multiple_teacher_classes(
    teacher_user, sample_institution, sample_class, sample_question, monkeypatch,
):
    course = Course.objects.create(
        name='课堂练习生成课程', subject='math', grade_level='9',
        teacher=teacher_user, institution=sample_institution,
    )
    from apps.institutions.models import Class, ClassTeacher
    from apps.parser.models import ExamQuestion
    second_class = Class.objects.create(
        institution=sample_institution, class_name='教师第二班', creator_teacher=teacher_user,
    )
    ClassTeacher.objects.create(class_obj=second_class, teacher=teacher_user, role='owner')
    node = CourseTree.objects.create(course=course, name='第一章', sort_order=1)
    CourseQuestionLink.objects.create(course=course, tree_node=node, question=sample_question, source='manual')
    second_question = ExamQuestion.objects.create(
        paper=sample_question.paper, question_no='2', question_type=sample_question.question_type,
        subject=sample_question.subject, stem='第二道题', answer='B',
    )
    third_question = ExamQuestion.objects.create(
        paper=sample_question.paper, question_no='3', question_type=sample_question.question_type,
        subject=sample_question.subject, stem='未选择的题', answer='C',
    )
    CourseQuestionLink.objects.create(course=course, tree_node=node, question=second_question, source='manual')
    CourseQuestionLink.objects.create(course=course, tree_node=node, question=third_question, source='manual')

    client = APIClient()
    client.force_authenticate(user=teacher_user)
    response = client.post(f'/api/v1/courses/{course.id}/generate-mission/', {
        'node_ids': [str(node.id)],
        'mission_name': '课堂练习作业',
        'source_type': 'handout',
        'source_context': 'course_practice',
        'start_at': '2026-09-14T00:00:00+08:00',
        'end_at': '2026-09-20T23:59:59+08:00',
        'class_ids': [str(sample_class.id), str(second_class.id)],
        'question_ids': [str(second_question.id), str(sample_question.id)],
    }, format='json')

    assert response.status_code == 201, response.json()
    mission = LearningMission.objects.get(id=response.data['data']['mission_id'])
    assert mission.status == 'draft'
    assert mission.source_type == 'handout'
    assert mission.start_at.isoformat().startswith('2026-09-13T16:00:00')
    assert mission.end_at.isoformat().startswith('2026-09-20T15:59:59')
    assert set(MissionClassAssignment.objects.filter(mission=mission).values_list('class_obj_id', flat=True)) == {
        sample_class.id, second_class.id,
    }
    selected_relations = list(MissionQuestionRel.objects.filter(mission=mission).order_by('sort_no'))
    assert [relation.question_id for relation in selected_relations] == [second_question.id, sample_question.id]
    assert [relation.question_id for relation in ordered_mission_question_rels(mission)] == [second_question.id, sample_question.id]
    assert all(relation.source_type == 'course_selected' for relation in selected_relations)
    assert not MissionQuestionRel.objects.filter(mission=mission, question_id=third_question.id).exists()
    assert mission.source_context == 'course_practice'
    assert mission.source_node_ids == [str(node.id)]

    editor_response = client.get(f'/api/v1/missions/{mission.id}/handout-edit/')
    assert editor_response.status_code == 200, editor_response.json()
    editor_data = editor_response.data['data']
    assert editor_data['source_context'] == 'course_practice'
    assert editor_data['node_ids'] == [str(node.id)]
    assert editor_data['question_ids'] == [str(second_question.id), str(sample_question.id)]
    assert {item['id'] for item in editor_data['questions']} == {str(second_question.id), str(sample_question.id)}
    assert editor_data['nodes'][0]['question_count'] == 3

    update_response = client.put(f'/api/v1/missions/{mission.id}/handout-edit/', {
        'mission_name': '课堂练习作业（已编辑）',
        'goal_text': '只更新课堂练习专用编辑器',
        'level_type': 'review',
        'pass_rule': {'correct_rate': 0.8},
        'source_type': 'handout',
        'source_context': 'course_practice',
        'node_ids': [str(node.id)],
        'question_ids': [str(sample_question.id), str(second_question.id)],
        'class_ids': [str(sample_class.id), str(second_class.id)],
        'start_at': '2026-09-14T00:00:00+08:00',
        'end_at': '2026-09-22T23:59:59+08:00',
    }, format='json')
    assert update_response.status_code == 200, update_response.json()
    mission.refresh_from_db()
    assert mission.mission_name == '课堂练习作业（已编辑）'
    assert mission.source_context == 'course_practice'
    assert mission.source_node_ids == [str(node.id)]
    assert mission.levels.get().level_type == 'review'
    assert mission.levels.get().pass_rule_json == {'correct_rate': 0.8}
    assert [relation.question_id for relation in MissionQuestionRel.objects.filter(mission=mission).order_by('sort_no')] == [sample_question.id, second_question.id]
    assert mission.end_at.isoformat().startswith('2026-09-22T15:59:59')

    question_list_response = client.get(f'/api/v1/courses/{course.id}/questions/?page=1&page_size=100')
    assert question_list_response.status_code == 200
    question_items = question_list_response.data['data']['items']
    question_item = next(item for item in question_items if str(item['id']) == str(sample_question.id))
    assert str(node.id) in question_item['tree_node_ids']
    assert str(question_item['tree_node_id']) == str(node.id)

    list_response = client.get('/api/v1/missions/')
    assert list_response.status_code == 200
    listed = next(item for item in list_response.data['data'] if str(item['id']) == str(mission.id))
    assert listed['source_type'] == 'handout'
    assert set(listed['class_ids']) == {str(sample_class.id), str(second_class.id)}
    assert listed['class_names']
    assert listed['start_at']
    assert listed['end_at']

    detail_response = client.get(f'/api/v1/missions/{mission.id}/')
    assert detail_response.status_code == 200
    detail = detail_response.data['data']
    assert detail['source_type'] == 'handout'
    assert set(detail['class_ids']) == {str(sample_class.id), str(second_class.id)}
    assert detail['class_names']
    assert detail['start_at']
    assert detail['end_at']

    publish_response = client.post(f'/api/v1/courses/{course.id}/generate-mission-and-publish/', {
        'node_ids': [str(node.id)],
        'mission_name': '课堂练习自动发布作业',
        'source_type': 'handout',
        'start_at': '2026-09-14T00:00:00+08:00',
        'end_at': '2026-09-20T23:59:59+08:00',
        'class_ids': [str(sample_class.id), str(second_class.id)],
        'question_ids': [str(second_question.id), str(sample_question.id)],
    }, format='json')

    assert publish_response.status_code == 201, publish_response.json()
    assert publish_response.data['message'] == '创建作业并发布成功'
    published_mission = LearningMission.objects.get(id=publish_response.data['data']['mission_id'])
    assert published_mission.status == 'published'
    assert published_mission.source_type == 'handout'
    assert published_mission.start_at
    assert published_mission.end_at
    assert set(MissionClassAssignment.objects.filter(mission=published_mission).values_list('class_obj_id', flat=True)) == {
        sample_class.id, second_class.id,
    }

    # If publication fails after generation, the one-click endpoint must not
    # leave a draft mission behind.
    from rest_framework.response import Response

    def fail_publish(request, mission_id):
        return Response({'code': 400, 'message': '模拟发布失败', 'data': None}, status=400)

    monkeypatch.setattr('apps.missions.views.mission_publish', fail_publish)
    rollback_response = client.post(f'/api/v1/courses/{course.id}/generate-mission-and-publish/', {
        'node_ids': [str(node.id)],
        'mission_name': '课堂练习自动发布回滚作业',
        'source_type': 'handout',
        'start_at': '2026-09-14T00:00:00+08:00',
        'end_at': '2026-09-20T23:59:59+08:00',
        'class_ids': [str(sample_class.id)],
        'question_ids': [str(sample_question.id)],
    }, format='json')

    assert rollback_response.status_code == 400
    assert not LearningMission.objects.filter(mission_name='课堂练习自动发布回滚作业').exists()


@pytest.mark.django_db
def test_course_practice_generate_supports_multiple_handouts_in_selected_order(
    teacher_user, sample_institution, sample_class, sample_question,
):
    from apps.parser.models import ExamQuestion

    course = Course.objects.create(
        name='multi-handout-course', subject='math', grade_level='9',
        teacher=teacher_user, institution=sample_institution,
    )
    CourseClass.objects.create(course=course, class_obj=sample_class, status='active')
    first_question = sample_question
    second_question = ExamQuestion.objects.create(
        paper=sample_question.paper, question_no='2', question_type=sample_question.question_type,
        subject=sample_question.subject, stem='second handout question', answer='B',
    )
    first_handout = Handout.objects.create(
        name='first handout', subject='math', creator_teacher=teacher_user,
        course=course, status='published',
    )
    second_handout = Handout.objects.create(
        name='second handout', subject='math', creator_teacher=teacher_user,
        course=course, status='published',
    )
    HandoutQuestion.objects.create(
        handout=first_handout, question=first_question, sort_no=1,
        display_snapshot={'id': str(first_question.id), 'stem': first_question.stem},
    )
    HandoutQuestion.objects.create(
        handout=second_handout, question=second_question, sort_no=1,
        display_snapshot={'id': str(second_question.id), 'stem': second_question.stem},
    )

    client = APIClient()
    client.force_authenticate(user=teacher_user)
    response = client.post(f'/api/v1/courses/{course.id}/generate-mission/', {
        'handout_ids': [str(second_handout.id), str(first_handout.id)],
        'class_id': str(sample_class.id),
        'question_ids': [str(second_question.id), str(first_question.id)],
    }, format='json')

    assert response.status_code == 201, response.json()
    mission = LearningMission.objects.get(id=response.data['data']['mission_id'])
    relations = list(MissionQuestionRel.objects.filter(mission=mission).order_by('sort_no'))
    assert [relation.question_id for relation in relations] == [second_question.id, first_question.id]
    assert all(relation.source_type == 'handout_selected' for relation in relations)
    assert mission.levels.get().level_name == 'second handout、first handout'


@pytest.mark.django_db
def test_handout_editor_does_not_accept_other_mission_sources(teacher_user):
    mission = LearningMission.objects.create(
        mission_name='普通题库作业',
        creator_teacher_id=teacher_user,
        source_type='question_bank',
    )
    client = APIClient()
    client.force_authenticate(user=teacher_user)
    response = client.get(f'/api/v1/missions/{mission.id}/handout-edit/')
    assert response.status_code == 400


@pytest.mark.django_db
def test_course_level_mission_cannot_publish_without_deadline_or_class(
    teacher_user, sample_institution,
):
    course = Course.objects.create(
        name='课程作业发布校验', subject='math', grade_level='9',
        teacher=teacher_user, institution=sample_institution,
    )
    mission = LearningMission.objects.create(
        mission_name='未完成课程作业', creator_teacher_id=teacher_user,
        course=course, status='draft', assignment_mode='levels',
    )
    response = APIClient()
    response.force_authenticate(user=teacher_user)

    publish_response = response.post(f'/api/v1/missions/{mission.id}/publish/', {}, format='json')

    assert publish_response.status_code == 400
    assert '完成日期' in publish_response.json()['message']


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
