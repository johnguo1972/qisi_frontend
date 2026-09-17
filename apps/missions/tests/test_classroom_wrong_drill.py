from pathlib import Path
import io
import zipfile

import pytest
import fitz
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import resolve

from apps.missions.classroom_wrong_drill_service import _mapping_rows, generate_wrong_drill_batch, import_number_mapping, save_mapping_upload
from apps.missions.classroom_wrongbook_service import prepare_classroom_matrix
from apps.missions.models import (
    ClassroomWrongDrillNumberMapping, ClassroomWrongDrillSourceQuestion,
    ClassroomWrongDrillSourceSet, ClassroomWrongDrillMappingImport, MissionQuestionRel,
)
from apps.parser.models import ExamQuestion

from .test_classroom_wrongbook import _client, _fixture
from apps.accounts.services import generate_tokens
from rest_framework.test import APIClient


pytestmark = pytest.mark.django_db


def test_singular_wrong_drill_source_route_is_compatible():
    match = resolve(
        '/api/v1/missions/01a09ea6-abe5-7572-8547-de655c39ebf8/'
        'classroom-wrongbook-statistics/wrong-drill/source'
    )
    assert match.url_name == 'classroom-wrong-drill-source'


def _mapping_xlsx():
    def cell(ref, value):
        return f'<c r="{ref}" t="inlineStr"><is><t>{value}</t></is></c>'
    sheet = (
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
        f'<row r="1">{cell("A1", "错题练习题号")}{cell("B1", "针对练习册题号")}</row>'
        f'<row r="2">{cell("A2", "5")}{cell("B2", "1")}</row>'
        '</sheetData></worksheet>'
    )
    workbook = '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="映射" sheetId="1" r:id="rId1"/></sheets></workbook>'
    rels = '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>'
    content = '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/xml"/></Types>'
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w') as archive:
        archive.writestr('[Content_Types].xml', content)
        archive.writestr('xl/workbook.xml', workbook)
        archive.writestr('xl/_rels/workbook.xml.rels', rels)
        archive.writestr('xl/worksheets/sheet1.xml', sheet)
    return SimpleUploadedFile('mapping.xlsx', stream.getvalue())


def _two_column_xlsx(first_header, second_header, first_value='1', second_value='5'):
    def cell(ref, value):
        return f'<c r="{ref}" t="inlineStr"><is><t>{value}</t></is></c>'
    sheet = (
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
        f'<row r="1">{cell("A1", "映射关系")}</row>'
        f'<row r="2">{cell("A2", first_header)}{cell("B2", second_header)}</row>'
        f'<row r="3">{cell("A3", first_value)}{cell("B3", second_value)}</row>'
        '</sheetData></worksheet>'
    )
    workbook = '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="mapping" sheetId="1" r:id="rId1"/></sheets></workbook>'
    rels = '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>'
    content = '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/xml"/></Types>'
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w') as archive:
        archive.writestr('[Content_Types].xml', content)
        archive.writestr('xl/workbook.xml', workbook)
        archive.writestr('xl/_rels/workbook.xml.rels', rels)
        archive.writestr('xl/worksheets/sheet1.xml', sheet)
    return SimpleUploadedFile('nonstandard-mapping.xlsx', stream.getvalue())


def test_fixed_mapping_generates_one_personal_mission_and_pdf(tmp_path, settings):
    teacher, student, class_obj, node, workbook_question, mission, _ = _fixture()
    matrix = prepare_classroom_matrix(mission.id, teacher, class_obj.id)[1]
    drill = ExamQuestion.objects.create(
        paper=workbook_question.paper, question_no='5', question_type='single_choice',
        subject='math', stem='同类精练题', answer='A', analysis='解析',
    )
    source_set = ClassroomWrongDrillSourceSet.objects.create(
        source_mission=mission, source_node_id=node.id, source_node_name=node.name,
        created_by=teacher, status='ready', number_mapping_version=1,
    )
    source_question = ClassroomWrongDrillSourceQuestion.objects.create(
        source_set=source_set, question=drill, wrong_question_no='5',
        question_snapshot={'id': str(drill.id), 'stem': drill.stem, 'answer': 'A', 'options_html': []},
        answer_snapshot='A', analysis_snapshot='解析', sort_no=1,
    )
    mapping = ClassroomWrongDrillNumberMapping.objects.create(
        source_set=source_set, source_question=source_question,
        wrong_question_no='5', workbook_question_no='1',
        workbook_question_id=workbook_question.id, sort_no=1,
    )

    batch = generate_wrong_drill_batch(
        mission=mission, matrix=matrix, teacher=teacher,
        source_set_id=source_set.id, version=None,
    )

    assert batch.status == 'generated', batch.errors
    package = batch.packages.get(student=student)
    assert package.mission.mission_name == '课堂练习-讲义(第1讲)-错题精练题'
    assert package.mission.mission_kind == 'wrongbook_personal'
    assert package.mission.source_type == 'wrongbook_drill'
    rel = MissionQuestionRel.objects.get(mission=package.mission)
    assert rel.question_id == drill.id
    assert rel.source_wrong_question_id == workbook_question.id
    assert rel.source_mapping_id == mapping.id
    assert rel.source_wrong_question_no == '1'
    assert rel.source_drill_question_no == '5'
    assert package.file_name.endswith('--错题精练题.pdf')
    assert package.file_name.startswith('课堂练习-讲义(第1讲)-')
    assert (Path(settings.MEDIA_ROOT) / package.pdf_file_path).exists()
    with fitz.open(Path(settings.MEDIA_ROOT) / package.pdf_file_path) as document:
        text = '\n'.join(page.get_text() for page in document)
    assert '错题重练' in text
    assert '答案' in text
    student_client = APIClient()
    student_client.credentials(HTTP_AUTHORIZATION=f"Bearer {generate_tokens(student, 'student')['access_token']}")
    detail = student_client.get(f'/api/v1/student/missions/{package.mission_id}')
    assert detail.status_code == 200
    assert detail.data['data']['source_type'] == 'wrongbook_drill'
    assert detail.data['data']['mission_name'] == '课堂练习-讲义(第1讲)-错题精练题'
    level = package.mission.levels.first()
    questions = student_client.get(f'/api/v1/student/levels/{level.id}').data['data']['questions']
    assert questions[0]['answer'] == ''
    export = _client(teacher).post(
        f'/api/v1/missions/{mission.id}/classroom-wrongbook-statistics/wrong-drill/batches/{batch.id}/bulk-export',
        {'class_id': str(class_obj.id), 'student_ids': [str(student.id)]}, format='json',
    )
    assert export.status_code == 200
    assert export.data['data']['download_url'].endswith('.zip')


def test_no_mapping_does_not_create_empty_package(settings):
    teacher, student, class_obj, node, workbook_question, mission, _ = _fixture()
    matrix = prepare_classroom_matrix(mission.id, teacher, class_obj.id)[1]
    source_set = ClassroomWrongDrillSourceSet.objects.create(
        source_mission=mission, source_node_id=node.id, source_node_name=node.name,
        created_by=teacher, status='ready', number_mapping_version=1,
    )
    batch = generate_wrong_drill_batch(
        mission=mission, matrix=matrix, teacher=teacher,
        source_set_id=source_set.id, version=None,
    )
    assert batch.status == 'failed'
    assert batch.packages.count() == 0
    assert batch.errors[0]['reason_code'] == 'NO_MAPPED_DRILL'


def test_mapping_file_uses_wrongbook_number_to_workbook_number_direction():
    teacher, student, class_obj, node, workbook_question, mission, _ = _fixture()
    source_set = ClassroomWrongDrillSourceSet.objects.create(
        source_mission=mission, source_node_id=node.id, source_node_name=node.name,
        created_by=teacher, status='pending',
    )
    drill = ExamQuestion.objects.create(
        paper=workbook_question.paper, question_no='5', question_type='single_choice',
        subject='math', stem='drill', answer='A',
    )
    source_question = ClassroomWrongDrillSourceQuestion.objects.create(
        source_set=source_set, question=drill, wrong_question_no='5',
        answer_snapshot='A', sort_no=1,
    )
    upload = _mapping_xlsx()
    mapping_import = ClassroomWrongDrillMappingImport.objects.create(
        source_set=source_set, file_path=save_mapping_upload(upload, source_set_id=source_set.id),
        file_name=upload.name, created_by=teacher,
    )
    import_number_mapping(source_set, mapping_import)
    row = source_set.number_mappings.get()
    assert row.wrong_question_no == '5'
    assert row.workbook_question_no == '1'
    assert row.workbook_question_id == workbook_question.id
    assert source_set.status == 'ready'


def test_mapping_file_uses_first_two_columns_when_headers_are_nonstandard():
    teacher, _, _, node, _, mission, _ = _fixture()
    source_set = ClassroomWrongDrillSourceSet.objects.create(
        source_mission=mission, source_node_id=node.id, source_node_name=node.name,
        created_by=teacher, status='pending',
    )
    upload = _two_column_xlsx('练习册题号', '错题练习册')
    mapping_import = ClassroomWrongDrillMappingImport.objects.create(
        source_set=source_set, file_path=save_mapping_upload(upload, source_set_id=source_set.id),
        file_name=upload.name, created_by=teacher,
    )

    rows, parsing = _mapping_rows(mapping_import)

    assert parsing['mode'] == 'position'
    assert rows == [{'sheet': 'mapping', 'row': 3, 'wrong': '5', 'target': '1'}]


def test_original_mapping_keeps_workbook_question_content_and_reuses_drill_number():
    teacher, student, class_obj, node, workbook_question, mission, _ = _fixture()
    matrix = prepare_classroom_matrix(mission.id, teacher, class_obj.id)[1]
    drill = ExamQuestion.objects.create(
        paper=workbook_question.paper, question_no='5', question_type='single_choice',
        subject='math', stem='replacement drill', answer='A',
    )
    source_set = ClassroomWrongDrillSourceSet.objects.create(
        source_mission=mission, source_node_id=node.id, created_by=teacher,
        status='ready', number_mapping_version=1,
    )
    source_question = ClassroomWrongDrillSourceQuestion.objects.create(
        source_set=source_set, question=drill, wrong_question_no='5',
        question_snapshot={'stem': drill.stem, 'question_type': drill.question_type}, answer_snapshot='A',
    )
    # Reusing the same drill question is valid when it is placed at different
    # workbook positions.  The original row keeps the workbook question itself.
    ClassroomWrongDrillNumberMapping.objects.create(
        source_set=source_set, source_question=source_question, wrong_question_no='5',
        workbook_question_no='2', workbook_question_id=workbook_question.id, sort_no=1,
    )
    original_mapping = ClassroomWrongDrillNumberMapping.objects.create(
        source_set=source_set, mapping_type='original', original_question=workbook_question,
        wrong_question_no='原题', workbook_question_no='1', workbook_question_id=workbook_question.id,
        display_question_no='1', sort_no=2,
    )

    batch = generate_wrong_drill_batch(
        mission=mission, matrix=matrix, teacher=teacher, source_set_id=source_set.id,
    )

    item = batch.packages.get(student=student).items.get(mapping=original_mapping)
    assert item.mapping_type == 'original'
    assert item.source_question is None
    assert item.drill_question_id == workbook_question.id
    assert item.content_snapshot['stem'] == workbook_question.stem
    assert item.drill_question_no == '1'
