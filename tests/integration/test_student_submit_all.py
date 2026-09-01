"""Regression tests for the student's batch whole-mission submission."""

import pytest

from apps.missions.models import LearningMission, MissionLevel, MissionQuestionRel
from apps.parser.models import ExamQuestion
from apps.study.models import AnswerAttempt, StudentMissionProgress


@pytest.mark.django_db
def test_whole_submit_persists_batch_answers_and_returns_results(
    student_client, student_user, sample_paper,
):
    mission = LearningMission.objects.create(
        mission_name='批量提交测试作业',
        status='published',
        assignment_mode='flat',
        creator_teacher_id=student_user,
    )
    level = MissionLevel.objects.create(
        mission=mission,
        level_no=1,
        level_name='作业题目',
        level_type='practice',
    )
    first = ExamQuestion.objects.create(
        paper=sample_paper, question_no='4', question_type='single_choice',
        subject='数学', stem='第一题', answer='A',
    )
    second = ExamQuestion.objects.create(
        paper=sample_paper, question_no='3', question_type='single_choice',
        subject='数学', stem='第二题', answer='B',
    )
    MissionQuestionRel.objects.create(
        mission=mission, level=level, question_id=first.id, sort_no=1,
    )
    MissionQuestionRel.objects.create(
        mission=mission, level=level, question_id=second.id, sort_no=2,
    )
    StudentMissionProgress.objects.create(
        mission=mission, student_user_id=student_user,
        progress_status='not_started', progress_percent=0,
    )

    first_payload = {
        'answers': [{
            'question_id': str(first.id),
            'level_id': str(level.id),
            'answer_content': {'selected_options': ['A']},
            'idempotency_key': 'batch-q1',
        }],
    }
    partial = student_client.post(
        f'/api/v1/student/missions/{mission.id}/submit',
        first_payload, format='json',
    )
    assert partial.status_code == 400
    assert partial.data['data']['missing_question_ids'] == [str(second.id)]
    assert AnswerAttempt.objects.filter(
        mission=mission, student_user_id=student_user,
    ).count() == 1
    assert StudentMissionProgress.objects.get(
        mission=mission, student_user_id=student_user,
    ).progress_status == 'in_progress'

    complete_payload = {
        'answers': [
            first_payload['answers'][0],
            {
                'question_id': str(second.id),
                'level_id': str(level.id),
                'answer_content': {'selected_options': ['B']},
                'idempotency_key': 'batch-q2',
            },
        ],
    }
    complete = student_client.post(
        f'/api/v1/student/missions/{mission.id}/submit',
        complete_payload, format='json',
    )
    assert complete.status_code == 200
    assert complete.data['data']['status'] == 'graded'
    assert len(complete.data['data']['results']) == 2
    assert all(item['is_correct'] for item in complete.data['data']['results'])
    assert [item['question_no'] for item in complete.data['data']['results']] == [1, 2]
    assert [item['source_question_no'] for item in complete.data['data']['results']] == ['3', '4']
    assert [item['question_id'] for item in complete.data['data']['results']] == [str(second.id), str(first.id)]

    result = student_client.get(f'/api/v1/student/missions/{mission.id}/results')
    assert result.status_code == 200
    assert len(result.data['data']['results']) == 2

    replay = student_client.post(
        f'/api/v1/student/missions/{mission.id}/submit',
        complete_payload, format='json',
    )
    assert replay.status_code == 200
    assert replay.data['data']['idempotent_replay'] is True
    assert AnswerAttempt.objects.filter(
        mission=mission, student_user_id=student_user,
    ).count() == 2
