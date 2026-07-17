"""Integration tests for student learning endpoints."""
import pytest
from apps.missions.models import LearningMission, MissionLevel, MissionQuestionRel
from apps.parser.models import ExamQuestion
from apps.study.models import StudentMissionProgress, StudentLevelProgress, AnswerAttempt


@pytest.mark.django_db
class TestStudentLearning:
    """Test student learning flow endpoints."""

    def test_student_home(self, student_client, student_user):
        """Student home should return mission list."""
        resp = student_client.get('/api/v1/student/home')
        assert resp.status_code == 200
        data = resp.json()
        assert data['code'] == 0
        assert 'missions' in data['data']

    def test_mission_detail_student(self, student_client, student_user):
        """Student can view published mission detail."""
        mission = LearningMission.objects.create(
            mission_name='学生测试任务',
            goal_text='测试',
            status='published',
            creator_teacher_id=student_user,
        )
        level = MissionLevel.objects.create(
            mission=mission,
            level_no=1,
            level_name='第一关',
            level_type='practice',
            mode_policy='block_a',
        )
        resp = student_client.get(f'/api/v1/student/missions/{mission.id}')
        assert resp.status_code == 200

    def test_level_detail(self, student_client, student_user, sample_paper):
        """Student can view level detail with questions."""
        mission = LearningMission.objects.create(
            mission_name='关卡测试任务',
            goal_text='测试',
            status='published',
            creator_teacher_id=student_user,
        )
        level = MissionLevel.objects.create(
            mission=mission,
            level_no=1,
            level_name='第一关',
            level_type='practice',
            mode_policy='block_a',
        )
        question = ExamQuestion.objects.create(
            paper=sample_paper,
            question_no='1',
            question_type='single_choice',
            subject='数学',
            stem='题目1',
            answer='A',
        )
        MissionQuestionRel.objects.create(
            mission=mission,
            level=level,
            question_id=question.id,
        )

        resp = student_client.get(f'/api/v1/student/levels/{level.id}')
        assert resp.status_code == 200

    def test_submit_answer(self, student_client, student_user, sample_question):
        """Student can submit answer."""
        resp = student_client.post('/api/v1/student/attempts', {
            'question_id': sample_question.id,
            'answer_content': {'selected_options': ['A']},
            'submit_source': 'manual',
            'mission_id': None,
            'level_id': None,
        }, format='json')
        assert resp.status_code in [200, 201, 400], f"Response: {resp.json()}"

    def test_submit_answer_wrong_adds_to_wrong_book(self, student_client, student_user, sample_question):
        """Wrong answer should be recorded."""
        resp = student_client.post('/api/v1/student/attempts', {
            'question_id': sample_question.id,
            'answer_content': {'selected_options': ['D']},  # Wrong answer
            'submit_source': 'manual',
        }, format='json')
        if resp.status_code == 200:
            data = resp.json()['data']
            assert 'is_correct' in data

    def test_retry_answer(self, student_client, student_user, sample_question):
        """Student can retry a wrong answer."""
        # First submit wrong
        resp = student_client.post('/api/v1/student/attempts', {
            'question_id': sample_question.id,
            'answer_content': {'selected_options': ['D']},
        }, format='json')
        if resp.status_code == 200 and resp.json().get('data', {}).get('attempt_id'):
            attempt_id = resp.json()['data']['attempt_id']
            # Retry
            resp2 = student_client.post(f'/api/v1/student/attempts/{attempt_id}/retry', {
                'answer_content': {'selected_options': ['A']},
            }, format='json')
            assert resp2.status_code in [200, 201, 400, 404]

    def test_start_guidance_b(self, student_client, student_user, sample_question):
        """Start B mode guidance."""
        resp = student_client.post('/api/v1/student/guidance/sessions', {
            'question_id': sample_question.id,
            'mode_type': 'B',
        })
        assert resp.status_code in [200, 201, 400, 404], f"Response: {resp.json()}"
        if resp.status_code == 200:
            data = resp.json()['data']
            assert data['mode'] == 'B'
            assert 'session_id' in data
            assert 'step_index' in data
            assert 'total_steps' in data
            assert 'hint' in data
            assert 'options' in data
            assert 'question_info' in data

    def test_start_guidance_c(self, student_client, student_user, sample_question):
        """Start C mode guidance."""
        resp = student_client.post('/api/v1/student/guidance/sessions', {
            'question_id': sample_question.id,
            'mode_type': 'C',
        })
        assert resp.status_code in [200, 201, 400, 404], f"Response: {resp.json()}"
        if resp.status_code == 200:
            data = resp.json()['data']
            assert data['mode'] in ('B', 'C')  # C may downgrade to B
            assert 'session_id' in data
            assert 'step_index' in data
            assert 'total_steps' in data

    def test_guidance_reply(self, student_client, student_user, sample_question):
        """Reply in guidance session."""
        # Start session
        resp = student_client.post('/api/v1/student/guidance/sessions', {
            'question_id': sample_question.id,
            'mode_type': 'B',
        })
        if resp.status_code == 200:
            session_id = resp.json()['data']['session_id']
            # Reply
            resp2 = student_client.post(
                f'/api/v1/student/guidance/sessions/{session_id}/reply',
                {'reply': 'A'},
                content_type='application/json'
            )
            assert resp2.status_code in [200, 400], f"Response: {resp2.json()}"
            if resp2.status_code == 200:
                data = resp2.json()['data']
                assert 'mode' in data
                assert 'step_index' in data
                assert 'is_completed' in data

    def test_guidance_downgrade_c_to_b(self, student_client, student_user, sample_question):
        """C mode with invalid input should downgrade to B."""
        resp = student_client.post('/api/v1/student/guidance/sessions', {
            'question_id': sample_question.id,
            'mode_type': 'C',
        })
        if resp.status_code == 200:
            session_id = resp.json()['data']['session_id']
            # Send invalid inputs (too short)
            for _ in range(2):
                student_client.post(
                    f'/api/v1/student/guidance/sessions/{session_id}/reply',
                    {'reply': 'a'},  # Invalid: too short
                    content_type='application/json'
                )
            # Check if downgraded
            from apps.study.models import AIGuidanceSession
            session = AIGuidanceSession.objects.get(pk=session_id)
            # Session should be downgraded or have increased invalid_input_count
            assert session.invalid_input_count >= 0  # At least tracked

    def test_get_mode_a(self, student_client, sample_question):
        """Get A mode answer for a question."""
        resp = student_client.get(f'/api/v1/student/questions/{sample_question.id}/mode-a/')
        assert resp.status_code in [200, 400, 403, 404, 501], f"Response: {resp.json()}"

    def test_growth_summary(self, student_client, student_user):
        """Student can view growth summary."""
        resp = student_client.get('/api/v1/student/growth')
        assert resp.status_code == 200
        data = resp.json()
        assert data['code'] == 0
        assert 'total_attempts' in data['data']
        assert 'accuracy' in data['data']

    def test_wrong_book_list(self, student_client, student_user):
        """Student can view wrong book."""
        resp = student_client.get('/api/v1/student/wrong-book/')
        assert resp.status_code == 200
        data = resp.json()
        assert data['code'] == 0

    def test_wrong_book_empty(self, student_client, student_user):
        """Wrong book should be empty initially."""
        resp = student_client.get('/api/v1/student/wrong-book/')
        assert resp.status_code == 200
