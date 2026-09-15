import io
import zipfile

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from apps.accounts.roles import grant_user_role
from apps.accounts.services import generate_tokens
from apps.accounts.models import UserAccount
from apps.courses.models import Course, CourseQuestionLink, CourseTree
from apps.institutions.models import Class, ClassStudent, ClassTeacher, Institution
from apps.missions.models import (
    LearningMission, MissionClassAssignment, MissionLevel, MissionQuestionRel,
    TeacherWrongBookCell, TeacherWrongBookMatrixAudit,
)
from apps.parser.models import ExamPaper, ExamQuestion
from apps.study.models import AnswerAttempt


pytestmark = pytest.mark.django_db


def _xlsx(node_name, student_name):
    def cell(ref, value):
        escaped = str(value).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        return f'<c r="{ref}" t="inlineStr"><is><t>{escaped}</t></is></c>'

    sheet = (
        f'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
        f'<row r="1">{cell("A1", node_name)}</row>'
        f'<row r="2">{cell("A2", "姓名")}{cell("B2", "1")}</row>'
        f'<row r="3">{cell("A3", student_name)}{cell("B3", "1")}</row>'
        '</sheetData></worksheet>'
    )
    workbook = '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="%s" sheetId="1" r:id="rId1"/></sheets></workbook>' % node_name
    rels = '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>'
    content = '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>'
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w') as archive:
        archive.writestr('[Content_Types].xml', content)
        archive.writestr('xl/workbook.xml', workbook)
        archive.writestr('xl/_rels/workbook.xml.rels', rels)
        archive.writestr('xl/worksheets/sheet1.xml', sheet)
    return SimpleUploadedFile('wrongbook.xlsx', stream.getvalue(), content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')


def _fixture():
    teacher = UserAccount.objects.create(role_type='teacher', mobile='13990000001', display_name='老师', password='x')
    grant_user_role(teacher, 'teacher')
    student = UserAccount.objects.create(role_type='student', mobile='13990000002', display_name='学生甲', password='x')
    grant_user_role(student, 'student')
    institution = Institution.objects.create(institution_name='课堂统计测试', created_by=teacher)
    class_obj = Class.objects.create(institution=institution, creator_teacher=teacher, class_name='测试班')
    ClassTeacher.objects.create(class_obj=class_obj, teacher=teacher, role='owner')
    ClassStudent.objects.create(class_obj=class_obj, student=student, join_type='manual', status='active')
    course = Course.objects.create(name='测试课程', subject='math', grade_level='junior', teacher=teacher, institution=institution)
    node = CourseTree.objects.create(course=course, name='错题地图第1讲', sort_order=1)
    paper = ExamPaper.objects.create(title='测试试卷', subject='math', stage='junior', source_file_path='test.pdf')
    question = ExamQuestion.objects.create(paper=paper, question_no='9', question_type='single_choice', subject='math', stem='1+1=?', answer='A')
    CourseQuestionLink.objects.create(course=course, tree_node=node, question=question, source='manual')
    mission = LearningMission.objects.create(
        creator_teacher_id=teacher, course=course, mission_name='课堂练习', status='published',
        source_type='handout', source_context='course_practice', source_node_ids=[str(node.id)],
    )
    MissionClassAssignment.objects.create(mission=mission, class_obj=class_obj, status='active')
    level = MissionLevel.objects.create(mission=mission, level_no=1, level_name=node.name, level_type='practice', source_node_id=node.id)
    relation = MissionQuestionRel.objects.create(
        mission=mission, level=level, question_id=question.id, sort_no=1,
        source_node_id=node.id, source_node_name_snapshot=node.name, node_question_no='1',
    )
    AnswerAttempt.objects.create(
        student_user_id=student, mission=mission, level=level, question_id=question.id,
        answer_content={'selected_options': ['B']}, is_correct=False, is_subjective_pending=False,
        submit_source='manual',
    )
    return teacher, student, class_obj, node, question, mission, relation


def _client(user):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {generate_tokens(user, 'teacher')['access_token']}")
    return client


def test_classroom_statistics_syncs_online_answer_and_preserves_node_number():
    teacher, student, class_obj, node, question, mission, _ = _fixture()
    response = _client(teacher).get(f'/api/v1/missions/{mission.id}/classroom-wrongbook-statistics?class_id={class_obj.id}')
    assert response.status_code == 200
    data = response.data['data']
    assert data['summary']['accumulated_wrong_count'] == 1
    assert data['students'][0]['data_source'] == 'online'
    assert data['students'][0]['cells'][0]['wrong'] is True
    assert data['students'][0]['cells'][0]['mark_source'] == 'online'
    assert data['questions'][0]['node_question_no'] == '1'
    node.name = '课程目录改名后'
    node.save(update_fields=['name'])
    refreshed = _client(teacher).get(f'/api/v1/missions/{mission.id}/classroom-wrongbook-statistics?class_id={class_obj.id}')
    assert refreshed.data['data']['nodes'][0]['node_name'] == '错题地图第1讲'


def test_classroom_import_marks_offline_student_and_records_failed_batch():
    teacher, student, class_obj, node, question, mission, _ = _fixture()
    AnswerAttempt.objects.filter(mission=mission).delete()
    client = _client(teacher)
    initial = client.get(f'/api/v1/missions/{mission.id}/classroom-wrongbook-statistics?class_id={class_obj.id}').data['data']
    upload = client.post(
        f'/api/v1/missions/{mission.id}/classroom-wrongbook-statistics/import',
        {'file': _xlsx(node.name, student.display_name), 'class_id': str(class_obj.id), 'version': initial['version']},
        format='multipart',
    )
    assert upload.status_code == 200
    assert upload.data['data']['matrix']['students'][0]['cells'][0]['mark_source'] == 'import'
    assert TeacherWrongBookCell.objects.filter(mark_source='import', status='marked').exists()

    bad_upload = client.post(
        f'/api/v1/missions/{mission.id}/classroom-wrongbook-statistics/import',
        {'file': SimpleUploadedFile('wrongbook.xlsx', b'not-xlsx'), 'class_id': str(class_obj.id), 'version': upload.data['data']['matrix']['version']},
        format='multipart',
    )
    assert bad_upload.status_code == 400
    assert bad_upload.data['data']['errors'][0]['reason_code'] == 'INVALID_XLSX'
    assert TeacherWrongBookMatrixAudit.objects.filter(action='import_failed').exists()


def test_classroom_manual_marks_use_version_and_can_be_cancelled():
    teacher, student, class_obj, node, question, mission, _ = _fixture()
    AnswerAttempt.objects.filter(mission=mission).delete()
    client = _client(teacher)
    url = f'/api/v1/missions/{mission.id}/classroom-wrongbook-statistics'
    initial = client.get(f'{url}?class_id={class_obj.id}').data['data']
    saved = client.patch(url, {
        'class_id': str(class_obj.id), 'version': initial['version'],
        'cells': [{'student_id': str(student.id), 'source_question_id': str(question.id), 'wrong': True}],
    }, format='json')
    assert saved.status_code == 200
    assert saved.data['data']['students'][0]['cells'][0]['mark_source'] == 'manual'
    cancelled = client.patch(url, {
        'class_id': str(class_obj.id), 'version': saved.data['data']['version'],
        'cells': [{'student_id': str(student.id), 'source_question_id': str(question.id), 'wrong': False}],
    }, format='json')
    assert cancelled.status_code == 200
    assert cancelled.data['data']['students'][0]['cells'][0]['wrong'] is False
    conflict = client.patch(url, {
        'class_id': str(class_obj.id), 'version': initial['version'], 'cells': [],
    }, format='json')
    assert conflict.status_code == 409


def test_multi_class_statistics_returns_class_options_and_defaults_to_first_class():
    teacher, student, class_obj, node, question, mission, _ = _fixture()
    institution = class_obj.institution
    second_class = Class.objects.create(
        institution=institution, creator_teacher=teacher, class_name='第二测试班',
    )
    ClassTeacher.objects.create(class_obj=second_class, teacher=teacher, role='owner')
    MissionClassAssignment.objects.create(mission=mission, class_obj=second_class, status='active')

    response = _client(teacher).get(
        f'/api/v1/missions/{mission.id}/classroom-wrongbook-statistics',
    )

    assert response.status_code == 200
    data = response.data['data']
    assert data['class_id'] == str(class_obj.id)
    assert data['class_options'] == [
        {'class_id': str(class_obj.id), 'class_name': class_obj.class_name},
        {'class_id': str(second_class.id), 'class_name': second_class.class_name},
    ]

    second_response = _client(teacher).get(
        f'/api/v1/missions/{mission.id}/classroom-wrongbook-statistics?class_id={second_class.id}',
    )
    assert second_response.status_code == 200
    assert second_response.data['data']['class_id'] == str(second_class.id)
