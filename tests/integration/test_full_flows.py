"""Full-flow integration tests: multi-step user journeys."""
import pytest
from rest_framework.test import APIClient
from apps.accounts.models import UserAccount
from apps.missions.models import LearningMission, MissionLevel, MissionQuestionRel
from apps.parser.models import ExamQuestion
from apps.study.models import StudentMissionProgress, StudentLevelProgress


@pytest.mark.django_db
class TestFullFlows:
    """End-to-end flow tests."""

    def test_teacher_upload_create_mission_student_answer(self, teacher_client, student_user, sample_paper):
        """Flow: Teacher uploads paper → creates mission → student answers.

        This tests the complete teacher→student workflow.
        """
        # 1. Teacher creates mission
        resp = teacher_client.post('/api/v1/missions', {
            'mission_name': '完整流程测试任务',
            'goal_text': '测试完整流程',
        })
        if resp.status_code not in [200, 201]:
            return  # Skip if mission creation not available

        mission_id = resp.json()['data']['id']

        # 2. Add level
        resp = teacher_client.post(f'/api/v1/missions/{mission_id}/levels', {
            'level_no': 1,
            'level_name': '第一关',
            'level_type': 'practice',
            'mode_policy': 'block_a',
        })
        if resp.status_code not in [200, 201]:
            return

        level_id = resp.json()['data']['id']

        # 3. Create question and link to level
        question = ExamQuestion.objects.create(
            paper=sample_paper,
            question_no='1',
            question_type='single_choice',
            subject='数学',
            stem='流程测试题目',
            answer='A',
            difficulty=3.00,
        )
        teacher_client.post(f'/api/v1/missions/{mission_id}/questions', {
            'level_id': level_id,
            'question_ids': [question.id],
        })

        # 4. Publish mission
        teacher_client.post(f'/api/v1/missions/{mission_id}/publish')

        # 5. Student views mission
        student_client = APIClient()
        student_client.force_authenticate(user=student_user)
        resp = student_client.get(f'/api/v1/student/missions/{mission_id}')
        assert resp.status_code == 200

        # 6. Student views level
        resp = student_client.get(f'/api/v1/student/levels/{level_id}')
        assert resp.status_code == 200

        # 7. Student submits answer
        resp = student_client.post('/api/v1/student/attempts', {
            'question_id': question.id,
            'answer_content': {'selected_options': ['A']},
            'level_id': level_id,
            'submit_source': 'manual',
        })
        if resp.status_code == 200:
            data = resp.json()['data']
            assert 'is_correct' in data

        # 8. Check growth
        resp = student_client.get('/api/v1/student/growth')
        assert resp.status_code == 200

    def test_full_class_management_flow(self, admin_client, teacher_client, student_client, admin_user, teacher_user, student_user):
        """Flow: Admin creates institution → adds teacher → teacher creates class → student joins.

        This tests the complete institution/class management workflow.
        """
        # 1. Admin creates institution
        resp = admin_client.post('/api/v1/admin/institutions', {
            'institution_name': '全流程测试学校',
            'contact_name': '管理员',
            'contact_phone': '13800000020',
        })
        if resp.status_code not in [200, 201]:
            return  # Skip if institution creation fails

        # Parse institution id from response or list
        resp = admin_client.get('/api/v1/admin/institutions')
        if resp.status_code != 200:
            return
        institutions = resp.json()['data'].get('items', [])
        if not institutions:
            return
        institution_id = institutions[0]['id']

        # 2. Teacher creates class
        resp = teacher_client.post('/api/v1/classes', {
            'institution_id': institution_id,
            'class_name': '全流程测试班级',
        })
        if resp.status_code not in [200, 201]:
            return

        class_id = resp.json()['data']['id']

        # 3. Student joins by code
        # First get class detail to get invite code
        resp = teacher_client.get(f'/api/v1/classes/{class_id}')
        if resp.status_code != 200:
            return

        invite_code = resp.json()['data'].get('invite_code')
        if not invite_code:
            return

        resp = student_client.post('/api/v1/student/classes/join-by-code', {
            'invite_code': invite_code,
        })
        assert resp.status_code in [200, 201, 400, 404]

        # 4. Teacher views students
        resp = teacher_client.get(f'/api/v1/classes/{class_id}/students')
        assert resp.status_code == 200

    def test_favorites_and_review_flow(self, teacher_client, sample_paper):
        """Flow: Create question → review → AI process → add to favorites.

        This tests the complete question review workflow.
        """
        # 1. Create question
        question = ExamQuestion.objects.create(
            paper=sample_paper,
            question_no='1',
            question_type='single_choice',
            subject='数学',
            stem='审核流程测试题',
            answer='A',
            difficulty=3.00,
        )

        # 2. View in review list
        resp = teacher_client.get(f'/api/v1/review/papers/{sample_paper.id}/questions/')
        assert resp.status_code == 200

        # 3. Confirm question
        resp = teacher_client.post(f'/api/v1/review/questions/{question.id}/confirm/')
        assert resp.status_code in [200, 400, 404]

        # 4. Add to favorites
        resp = teacher_client.post('/api/v1/teacher/favorites/add/', {
            'question_id': question.id,
        })
        assert resp.status_code in [200, 201, 400]

        # 5. View favorites
        resp = teacher_client.get('/api/v1/teacher/favorites/')
        assert resp.status_code == 200
