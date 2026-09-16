import json

import pytest
from django.core.cache import cache
from django.test import override_settings
from rest_framework.test import APIClient

from apps.accounts.models import StudentParentBind, UserAccount
from apps.accounts.roles import grant_user_role
from apps.accounts.services import generate_tokens
from apps.classroom_feedback.models import ClassroomFeedbackReport
from apps.classroom_feedback.services import build_feedback_snapshot, create_feedback_report
from apps.classroom_feedback import tasks
from apps.classroom_feedback.ai import _validate_result
from apps.missions.classroom_wrongbook_service import prepare_classroom_matrix
from apps.missions.tests.test_classroom_wrongbook import _fixture


pytestmark = pytest.mark.django_db


def test_ai_feedback_accepts_knowledge_points_inferred_from_question_content():
    result = _validate_result(
        {
            'feedback_text': '本次重点复习内能和比热容的概念，并订正第3题。',
            'focus_points': ['内能', '比热容'],
            'strengths': [], 'action_suggestions': [], 'confidence': 0.9,
        },
        {'待归类题目'},
        required_tokens=('3', '待归类题目'),
    )
    assert result['focus_points'] == ['内能', '比热容']


def _teacher_client(teacher):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {generate_tokens(teacher, 'teacher')['access_token']}")
    return client


def test_feedback_snapshot_uses_question_content_and_class_stats():
    teacher, student, class_obj, _node, question, mission, _relation = _fixture()
    question.knowledge_points = ['内能']
    question.analysis = '根据热量计算式分析。'
    question.save(update_fields=['knowledge_points', 'analysis', 'updated_at'])
    _mission, matrix, _ = prepare_classroom_matrix(mission.id, teacher, class_obj.id)
    snapshot = build_feedback_snapshot(mission, matrix)
    assert snapshot['participant_count'] == 1
    assert snapshot['total_wrong_count'] == 1
    assert snapshot['questions'][0]['knowledge_points'] == ['内能']
    assert snapshot['questions'][0]['analysis'] == '根据热量计算式分析。'
    assert snapshot['students'][0]['wrong_questions'][0]['question_no'] == '1'


def test_feedback_endpoints_create_report_and_return_teacher_payload(monkeypatch):
    teacher, _student, class_obj, _node, _question, mission, _relation = _fixture()
    client = _teacher_client(teacher)
    url = f'/api/v1/missions/{mission.id}/classroom-feedback'
    detail = client.get(f'{url}?class_id={class_obj.id}')
    assert detail.status_code == 200
    data = detail.data['data']
    assert data['current_summary']['total_wrong_count'] == 1
    assert data['overview']['question_count'] == 1
    monkeypatch.setattr(tasks.generate_classroom_feedback_report, 'apply_async', lambda *args, **kwargs: None)
    response = client.post(f'{url}/generate', {
        'class_id': str(class_obj.id),
        'matrix_version': data['current_matrix_version'],
        'idempotency_key': 'feedback-test-1',
    }, format='json')
    assert response.status_code == 202
    report_id = response.data['data']['report']['id']
    report = ClassroomFeedbackReport.objects.get(pk=report_id)
    assert report.input_snapshot['students'][0]['wrong_question_nos'] == ['1']
    tasks.generate_classroom_feedback_report.run(str(report.id))
    payload = client.get(f'{url}?class_id={class_obj.id}').data['data']['report']
    assert payload['status'] == 'ready'
    assert payload['students'][0]['feedback_text']
    assert payload['students'][0]['ai_model'] == 'qwen3.7-flash'
    assert '1' in payload['students'][0]['feedback_text']
    assert payload['students'][0]['wrong_questions'][0]['question_no'] == '1'
    assert payload['high_error_questions'][0]['wrong_count'] > 0


def test_feedback_generation_uses_separate_student_inputs(monkeypatch):
    teacher, _student, class_obj, _node, _question, mission, _relation = _fixture()
    _mission, matrix, _ = prepare_classroom_matrix(mission.id, teacher, class_obj.id)
    report = create_feedback_report(mission, matrix, teacher, 'separate-inputs')
    captured = []

    def fake_generate(task_key, context, **_kwargs):
        captured.append((task_key, json.loads(json.dumps(context, ensure_ascii=False))))
        if task_key == tasks.CLASS_TASK:
            return ({'feedback_text': '班级整体反馈已生成。', 'focus_points': [], 'strengths': [], 'action_suggestions': [], 'confidence': 0.9}, 'qwen3.7-flash')
        return ({'feedback_text': f"{context['student_name']}请订正第{context['wrong_question_nos'][0]}题。", 'focus_points': [], 'strengths': [], 'action_suggestions': [], 'confidence': 0.9}, 'qwen3.7-flash')

    monkeypatch.setattr(tasks, 'generate_feedback', fake_generate)
    tasks.generate_classroom_feedback_report.run(str(report.id))
    student_calls = [item for item in captured if item[0] == tasks.STUDENT_TASK]
    assert len(student_calls) == 1
    assert student_calls[0][1]['wrong_question_nos'] == ['1']
    saved_row = report.student_feedbacks.get()
    assert len(saved_row.ai_input_fingerprint) == 64
    assert ClassroomFeedbackReport.objects.get(pk=report.id).status == 'ready'


def test_parent_feedback_is_limited_to_selected_child(monkeypatch):
    teacher, student, class_obj, _node, _question, mission, _relation = _fixture()
    parent = UserAccount.objects.create(role_type='parent', mobile='13990000003', display_name='家长')
    grant_user_role(parent, 'parent')
    StudentParentBind.objects.create(parent_user_id=parent, student_user_id=student, relation_type='guardian', bind_status='active')
    cache.set(f'parent_context:{parent.id}', str(student.id), timeout=600)
    _mission, matrix, _ = prepare_classroom_matrix(mission.id, teacher, class_obj.id)
    report = create_feedback_report(mission, matrix, teacher, 'parent-isolation')

    def fake_generate(task_key, context, **_kwargs):
        text = '班级反馈已生成。' if task_key == tasks.CLASS_TASK else f"{context['student_name']}请订正第{context['wrong_question_nos'][0]}题。"
        return ({'feedback_text': text, 'focus_points': [], 'strengths': [], 'action_suggestions': [], 'confidence': 0.9}, 'qwen3.7-flash')

    monkeypatch.setattr(tasks, 'generate_feedback', fake_generate)
    tasks.generate_classroom_feedback_report.run(str(report.id))
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {generate_tokens(parent, 'parent')['access_token']}")
    response = client.get(f'/api/v1/parent/missions/{mission.id}/classroom-feedback')
    assert response.status_code == 200
    data = response.data['data']
    assert data['student_feedback']['student_id'] == str(student.id)
    assert 'students' not in data
    assert 'pdf_download_url' not in data
    assert data['knowledge_stats']
    assert data['question_stats']
    assert data['high_error_questions']
    cache.clear()


@override_settings(MEDIA_ROOT=None)
def test_feedback_pdf_is_rendered_from_report_snapshot(tmp_path, monkeypatch):
    from django.conf import settings
    from apps.classroom_feedback.pdf_service import generate_feedback_pdf

    settings.MEDIA_ROOT = tmp_path
    teacher, _student, class_obj, _node, _question, mission, _relation = _fixture()
    _mission, matrix, _ = prepare_classroom_matrix(mission.id, teacher, class_obj.id)
    report = create_feedback_report(mission, matrix, teacher, 'pdf-test')
    monkeypatch.setattr(tasks, 'generate_feedback', lambda task_key, context, **kwargs: ({
        'feedback_text': '班级或学生反馈已生成。', 'focus_points': [], 'strengths': [], 'action_suggestions': [], 'confidence': 0.9,
    }, 'qwen3.7-flash'))
    tasks.generate_classroom_feedback_report.run(str(report.id))
    report.refresh_from_db()
    relative = generate_feedback_pdf(report)
    assert relative.startswith('exports/classroom_feedback/')
    assert (tmp_path / relative).exists()
