"""Integration test: teacher creates mission -> student completes it."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from rest_framework.test import APIClient
from apps.accounts.models import UserAccount
from apps.missions.models import LearningMission, MissionLevel
from apps.parser.models import ExamQuestion
from apps.study.models import StudentMissionProgress, StudentLevelProgress, AnswerAttempt


def test_full_mission_flow():
    """End-to-end test: teacher publishes mission, student answers."""
    teacher_client = APIClient()
    student_client = APIClient()

    # Create users
    teacher = UserAccount.objects.create(
        role_type='teacher', mobile='13900000101', display_name='测试老师'
    )
    student = UserAccount.objects.create(
        role_type='student', mobile='13900000102', display_name='测试学生'
    )

    # Login
    teacher_client.force_authenticate(user=teacher)
    student_client.force_authenticate(user=student)

    # 1. Teacher creates mission
    resp = teacher_client.post('/api/v1/missions', {
        'mission_name': '测试任务',
        'goal_text': '测试目标',
    })
    assert resp.json()['code'] == 0, f"Create mission failed: {resp.json()}"
    mission_id = resp.json()['data']['id']
    print(f"1. Mission created (id={mission_id})")

    # 2. Teacher adds level
    resp = teacher_client.post(f'/api/v1/missions/{mission_id}/levels', {
        'level_no': 1,
        'level_name': '第一关',
        'level_type': 'practice',
        'mode_policy': 'block_a',
    })
    assert resp.json()['code'] == 0, f"Add level failed: {resp.json()}"
    level_id = resp.json()['data']['id']
    print(f"2. Level created (id={level_id})")

    # 3. Teacher publishes
    resp = teacher_client.post(f'/api/v1/missions/{mission_id}/publish')
    assert resp.json()['code'] == 0, f"Publish failed: {resp.json()}"
    print("3. Mission published")

    # 4. Student views level
    resp = student_client.get(f'/api/v1/student/levels/{level_id}')
    assert resp.json()['code'] == 0, f"Level detail failed: {resp.json()}"
    print("4. Student can view level")

    # 5. Student submits answer
    resp = student_client.post('/api/v1/student/attempts', {
        'question_id': 1,
        'answer_content': {'selected_options': ['A']},
        'level_id': level_id,
    })
    assert resp.json()['code'] == 0, f"Submit answer failed: {resp.json()}"
    data = resp.json()['data']
    assert 'is_correct' in data, "Missing is_correct in response"
    assert 'feedback' in data, "Missing feedback in response"
    print(f"5. Answer submitted (correct={data['is_correct']})")

    # 6. If wrong, start guidance
    if data.get('suggest_guidance'):
        resp = student_client.post('/api/v1/student/guidance/sessions', {
            'question_id': 1,
            'mode_type': 'B',
        })
        assert resp.json()['code'] == 0, f"Start guidance failed: {resp.json()}"
        session_id = resp.json()['data']['session_id']

        # Reply in guidance
        resp = student_client.post(
            f'/api/v1/student/guidance/sessions/{session_id}/reply',
            {'reply': '我认为选A'},
            content_type='application/json'
        )
        assert resp.json()['code'] == 0, f"Guidance reply failed: {resp.json()}"
        print("6. Guidance session started and replied")

    # 7. Check wrong book
    resp = student_client.get('/api/v1/student/wrong-book')
    assert resp.json()['code'] == 0, f"Wrong book list failed: {resp.json()}"
    print("7. Wrong book list accessible")

    # 8. Check growth
    resp = student_client.get('/api/v1/student/growth')
    assert resp.json()['code'] == 0, f"Growth summary failed: {resp.json()}"
    growth_data = resp.json()['data']
    assert 'total_attempts' in growth_data
    assert 'accuracy' in growth_data
    print(f"8. Growth summary: {growth_data['total_attempts']} attempts, {growth_data['accuracy']}% accuracy")

    # 9. Mission list for teacher
    resp = teacher_client.get('/api/v1/missions')
    assert resp.json()['code'] == 0, f"Mission list failed: {resp.json()}"
    missions = resp.json()['data']
    assert len(missions) > 0, "No missions found"
    print("9. Teacher mission list accessible")

    # 10. Profile
    resp = teacher_client.get('/api/v1/profile/me')
    assert resp.json()['code'] == 0, f"Profile failed: {resp.json()}"
    print("10. Profile accessible")

    print("\n=== ALL INTEGRATION TESTS PASSED ===")


if __name__ == '__main__':
    test_full_mission_flow()
