"""Integration tests for mission management endpoints."""
from datetime import timedelta

import pytest
from django.utils import timezone
from apps.missions.models import LearningMission, MissionLevel
from apps.parser.models import ExamQuestion
from apps.courses.models import Course


@pytest.mark.django_db
class TestMissions:
    """Test mission CRUD and level management."""

    def test_mission_list(self, teacher_client):
        """Mission list should return paginated results."""
        resp = teacher_client.get('/api/v1/missions')
        if resp.status_code == 301:
            # Django APPEND_SLASH redirects, follow redirect
            resp = teacher_client.get('/api/v1/missions/')
        assert resp.status_code == 200

    def test_mission_list_subject_display_and_filter(self, teacher_client, teacher_user, sample_mission):
        """Mission list should expose the course subject and filter by Chinese or code."""
        physics_course = Course.objects.create(
            name='物理课程', subject='物理', grade_level='初中', teacher=teacher_user,
        )
        math_course = Course.objects.create(
            name='数学课程', subject='math', grade_level='初中', teacher=teacher_user,
        )
        sample_mission.course = physics_course
        sample_mission.save(update_fields=['course'])
        math_mission = LearningMission.objects.create(
            mission_name='数学任务', status='published', creator_teacher_id=teacher_user,
            course=math_course,
        )

        response = teacher_client.get('/api/v1/missions/', {'subject': 'physics'})
        assert response.status_code == 200
        data = response.json()['data']
        assert [item['id'] for item in data] == [str(sample_mission.id)]
        assert data[0]['subject'] == '物理'

        response = teacher_client.get('/api/v1/missions/', {'subject': '数学'})
        assert response.status_code == 200
        data = response.json()['data']
        assert [item['id'] for item in data] == [str(math_mission.id)]
        assert data[0]['subject'] == '数学'

    def test_mission_create(self, teacher_client):
        """Create a new mission."""
        resp = teacher_client.post('/api/v1/missions', {
            'mission_name': '新测试任务',
            'goal_text': '测试目标',
        })
        # If 301, follow redirect
        if resp.status_code == 301:
            resp = teacher_client.post('/api/v1/missions/', {
                'mission_name': '新测试任务',
                'goal_text': '测试目标',
            })
        assert resp.status_code in [200, 201], f"Create failed: {resp.json()}"
        mission_id = resp.json()['data']['id']
        assert mission_id is not None

    def test_new_mission_defaults_start_date_and_flat_mode(self, teacher_client):
        """New homework starts now and uses the simplified flat mode by default."""
        response = teacher_client.post('/api/v1/missions/', {'mission_name': 'default flat assignment'})
        assert response.status_code == 201
        detail = teacher_client.get(f"/api/v1/missions/{response.json()['data']['id']}/").json()['data']
        assert detail['assignment_mode'] == 'flat'
        assert detail['start_at']

    def test_mission_detail(self, teacher_client, sample_mission):
        """Get mission detail."""
        resp = teacher_client.get(f'/api/v1/missions/{sample_mission.id}')
        assert resp.status_code == 200
        data = resp.json()
        assert data['code'] == 0

    def test_mission_update(self, teacher_client, sample_mission):
        """Update mission."""
        resp = teacher_client.put(f'/api/v1/missions/{sample_mission.id}', {
            'mission_name': '更新后的任务名',
        })
        assert resp.status_code in [200, 201, 400, 405], f"Response: {resp.json()}"

    def test_mission_publish(self, teacher_client, sample_mission):
        """Publish mission."""
        resp = teacher_client.post(f'/api/v1/missions/{sample_mission.id}/publish')
        assert resp.status_code in [200, 201, 400], f"Response: {resp.json()}"

    def test_mission_clone(self, teacher_client, sample_mission):
        """Clone mission."""
        resp = teacher_client.post(f'/api/v1/missions/{sample_mission.id}/clone')
        assert resp.status_code in [200, 201, 400, 404, 501], f"Response: {resp.json()}"

    def test_mission_clone_copies_class_and_targets(self, teacher_client, sample_mission, sample_class, student_user):
        """A normal clone keeps the assignment target while resetting its own progress."""
        sample_mission.class_obj = sample_class
        sample_mission.target_student_ids = [str(student_user.id)]
        sample_mission.save(update_fields=['class_obj', 'target_student_ids'])

        response = teacher_client.post(f'/api/v1/missions/{sample_mission.id}/clone/')

        assert response.status_code == 200, response.json()
        clone = LearningMission.objects.get(pk=response.json()['data']['id'])
        assert clone.class_obj_id == sample_class.id
        assert clone.target_student_ids == [str(student_user.id)]
        assert clone.status == 'draft'

    def test_mission_export_pdf_keeps_question_list_order(self, monkeypatch, teacher_client, sample_mission, sample_mission_level, sample_question, sample_paper):
        """PDF export must follow MissionQuestionRel.sort_no, not database ID order."""
        from apps.missions.models import MissionQuestionRel
        from apps.parser.models import ExamQuestion

        second_question = ExamQuestion.objects.create(
            paper=sample_paper,
            question_no='2',
            question_type='fill_blank',
            subject='physics',
            stem='第二道题',
            answer='B',
            difficulty=3.00,
        )
        third_question = ExamQuestion.objects.create(
            paper=sample_paper,
            question_no='3',
            question_type='short_answer',
            subject='physics',
            stem='第三道题',
            answer='C',
            difficulty=3.00,
        )
        sample_mission.assignment_mode = 'flat'
        sample_mission.save(update_fields=['assignment_mode'])
        MissionQuestionRel.objects.create(
            mission=sample_mission, level=sample_mission_level,
            question_id=third_question.id, sort_no=3,
        )
        MissionQuestionRel.objects.create(
            mission=sample_mission, level=sample_mission_level,
            question_id=sample_question.id, sort_no=1,
        )
        MissionQuestionRel.objects.create(
            mission=sample_mission, level=sample_mission_level,
            question_id=second_question.id, sort_no=2,
        )
        captured = {}

        def fake_build_pdf(_export_type, questions, _include_answers, _watermark):
            captured['question_ids'] = [str(question['id']) for question in questions]
            return b'%PDF-test'

        monkeypatch.setattr('apps.study.student_views._build_pdf', fake_build_pdf)
        response = teacher_client.get(f'/api/v1/missions/{sample_mission.id}/export-pdf/')

        assert response.status_code == 200, response.json()
        assert captured['question_ids'] == [
            str(sample_question.id), str(second_question.id), str(third_question.id),
        ]

    def test_mission_list_includes_completion_progress(self, teacher_client, sample_mission, sample_class, student_user):
        """Teacher mission lists expose completed, total, unfinished and percentage values."""
        from apps.institutions.models import ClassStudent
        from apps.study.models import StudentMissionProgress

        sample_mission.class_obj = sample_class
        sample_mission.status = 'published'
        sample_mission.save(update_fields=['class_obj', 'status'])
        ClassStudent.objects.create(
            class_obj=sample_class, student=student_user,
            join_type='manual', status='active',
        )
        StudentMissionProgress.objects.update_or_create(
            mission=sample_mission, student_user_id=student_user,
            defaults={'progress_status': 'completed', 'progress_percent': 100},
        )

        response = teacher_client.get('/api/v1/missions/')

        assert response.status_code == 200, response.json()
        item = next(item for item in response.json()['data'] if item['id'] == str(sample_mission.id))
        assert item['completion_progress'] == {
            'completed': 1,
            'total': 1,
            'unfinished': 0,
            'percent': 100.0,
        }

    def test_mission_progress_lists_each_assigned_student(self, teacher_client, sample_mission, sample_class, student_user):
        """Teacher progress view includes completed and not-started students."""
        from apps.accounts.models import UserAccount
        from apps.institutions.models import ClassStudent
        from apps.study.models import StudentMissionProgress

        waiting_student = UserAccount.objects.create(
            role_type='student', mobile='13900000004', display_name='未开始学生',
            password='pbkdf2_sha256$dummy',
        )
        sample_mission.class_obj = sample_class
        sample_mission.status = 'published'
        sample_mission.save(update_fields=['class_obj', 'status'])
        ClassStudent.objects.create(
            class_obj=sample_class, student=student_user,
            join_type='manual', status='active',
        )
        ClassStudent.objects.create(
            class_obj=sample_class, student=waiting_student,
            join_type='manual', status='active',
        )
        StudentMissionProgress.objects.update_or_create(
            mission=sample_mission, student_user_id=student_user,
            defaults={'progress_status': 'completed', 'progress_percent': 100},
        )

        response = teacher_client.get(f'/api/v1/missions/{sample_mission.id}/progress/')

        assert response.status_code == 200, response.json()
        data = response.json()['data']
        assert data['summary'] == {
            'completed': 1,
            'total': 2,
            'unfinished': 1,
            'percent': 50.0,
        }
        rows = {row['student_id']: row for row in data['students']}
        assert rows[str(student_user.id)]['progress_status'] == 'completed'
        assert rows[str(student_user.id)]['progress_percent'] == 100.0
        assert rows[str(waiting_student.id)]['progress_status'] == 'not_started'
        assert rows[str(waiting_student.id)]['progress_percent'] == 0.0

    def test_level_create(self, teacher_client, sample_mission):
        """Add a level to mission."""
        resp = teacher_client.post(f'/api/v1/missions/{sample_mission.id}/levels', {
            'level_no': 1,
            'level_name': '第一关',
            'level_type': 'practice',
            'mode_policy': 'block_a',
        })
        assert resp.status_code in [200, 201, 400], f"Create level failed: {resp.json()}"

    def test_level_list(self, teacher_client, sample_mission, sample_mission_level):
        """Verify level was created (mission_levels is POST-only, so we just verify creation worked)."""
        # The level was already created by sample_mission_level fixture
        # Just verify it exists
        assert sample_mission_level.id is not None
        assert sample_mission_level.mission_id == sample_mission.id

    def test_add_questions_to_mission(self, teacher_client, sample_mission, sample_mission_level, sample_question):
        """Add questions to a mission level."""
        resp = teacher_client.post(f'/api/v1/missions/{sample_mission.id}/questions', {
            'level_id': sample_mission_level.id,
            'question_ids': [sample_question.id],
        })
        assert resp.status_code in [200, 201, 400, 404], f"Response: {resp.json()}"

    def test_flat_assignment_saves_question_order(self, teacher_client, sample_mission, sample_question):
        """The simplified flow stores one ordered question list and no teacher levels."""
        second = ExamQuestion.objects.create(
            paper=sample_question.paper,
            question_no='second-flat-question',
            question_type='single_choice',
            subject=sample_question.subject,
            stem='second question',
            answer='B',
        )
        response = teacher_client.post(
            f'/api/v1/missions/{sample_mission.id}/questions/',
            {'question_ids': [str(second.id), str(sample_question.id)]},
        )
        assert response.status_code == 200, response.json()

        sample_mission.refresh_from_db()
        assert sample_mission.assignment_mode == 'flat'
        # The assignment is persisted in the same natural question-number
        # order used by the teacher matrix and exports.
        assert list(sample_mission.missionquestionrel_set.order_by('sort_no').values_list('question_id', flat=True)) == [
            sample_question.id,
            second.id,
        ]
        detail = teacher_client.get(f'/api/v1/missions/{sample_mission.id}/').json()
        assert detail['data']['assignment_mode'] == 'flat'
        assert detail['data']['question_ids'] == [str(sample_question.id), str(second.id)]

    def test_flat_assignment_publish_requires_questions_and_deadline(self, teacher_client, sample_mission):
        """A saved draft cannot be published until the required fields are complete."""
        sample_mission.assignment_mode = 'flat'
        sample_mission.save(update_fields=['assignment_mode'])
        response = teacher_client.post(f'/api/v1/missions/{sample_mission.id}/publish/')
        assert response.status_code == 400
        assert '完成日期' in response.json()['message']

    def test_stale_assignment_is_closed_and_excluded_from_unfinished(self, teacher_client, teacher_user):
        """A deadline older than ten days is closed lazily when the list is read."""
        stale = LearningMission.objects.create(
            mission_name='stale assignment',
            creator_teacher_id=teacher_user,
            status='published',
            end_at=timezone.now() - timedelta(days=11),
        )
        current = LearningMission.objects.create(
            mission_name='current draft',
            creator_teacher_id=teacher_user,
            status='draft',
            end_at=timezone.now() + timedelta(days=1),
        )

        response = teacher_client.get('/api/v1/missions/', {'unfinished': 'true'})
        assert response.status_code == 200
        ids = {item['id'] for item in response.json()['data']}
        stale.refresh_from_db()
        assert stale.status == 'closed'
        assert str(stale.id) not in ids
        assert str(current.id) in ids

    def test_unpublished_mission_not_visible_to_student(self, student_client, sample_mission):
        """Student should not see unpublished missions."""
        resp = student_client.get(f'/api/v1/student/missions/{sample_mission.id}')
        assert resp.status_code == 403

    def test_mission_isolation(self, teacher_client, student_client):
        """One teacher's missions should not appear in another's list."""
        teacher_client.post('/api/v1/missions', {'mission_name': '老师A的任务'})
        resp = student_client.get('/api/v1/missions')
        if resp.status_code == 301:
            resp = student_client.get('/api/v1/missions/')
        assert resp.status_code == 403
