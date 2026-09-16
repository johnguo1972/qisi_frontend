"""Read-only classroom feedback aggregation and report snapshots."""
from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.institutions.models import ClassStudent
from apps.common.media import media_url
from apps.missions.classroom_wrongbook_service import (
    VALID_CELL_STATUSES,
    classroom_statistics_payload,
    is_classroom_practice,
    prepare_classroom_matrix,
)
from apps.missions.models import LearningMission, TeacherWrongBookMatrix

from .models import (
    ClassroomFeedbackKnowledgeStat,
    ClassroomFeedbackQuestionStat,
    ClassroomFeedbackReport,
    ClassroomFeedbackStudent,
)


PROMPT_VERSION = 'classroom-feedback-v1'
MODEL_NAME = 'qwen3.7-flash'
MASTERY_THRESHOLD_VERSION = 'v1'
KNOWLEDGE_UNCLASSIFIED = '待归类题目'


def _text(value, limit: int | None = None) -> str:
    result = re.sub(r'\s+', ' ', str(value or '')).strip()
    return result[:limit] if limit else result


def _number(value) -> str:
    return _text(value).replace('第', '').strip()


def _labels(snapshot: dict) -> list[str]:
    raw = snapshot.get('knowledge_points') or snapshot.get('knowledge_labels') or []
    if isinstance(raw, str):
        raw = re.split(r'[,，、;；]', raw)
    labels = []
    for value in raw if isinstance(raw, list) else []:
        if isinstance(value, dict):
            value = value.get('module') or value.get('name') or value.get('label')
        value = _text(value, 255)
        if value and value not in labels:
            labels.append(value)
    return labels or [KNOWLEDGE_UNCLASSIFIED]


def _knowledge_key(name: str) -> str:
    return 'kp-' + hashlib.sha1(name.encode('utf-8')).hexdigest()[:16]


def _question_context(row: dict) -> dict:
    snapshot = row.get('snapshot') or {}
    return {
        'question_id': str(row.get('question_id') or ''),
        'question_no': _number(row.get('question_no') or row.get('node_question_no')),
        'node_id': str(row.get('node_id') or ''),
        'node_name': _text(row.get('node_name'), 200),
        'node_sort_no': int(row.get('node_sort_no') or 0),
        'stem': _text(snapshot.get('stem') or snapshot.get('stem_html'), 1200),
        'answer': _text(snapshot.get('answer'), 600),
        'analysis': _text(snapshot.get('analysis') or snapshot.get('solution'), 1200),
        'question_type': _text(snapshot.get('question_type'), 80),
        'knowledge_points': _labels(snapshot),
        'wrong_count': int(row.get('wrong_count') or 0),
        'wrong_rate': float(row.get('wrong_rate') or 0),
        'sort_no': int(row.get('sort_no') or 0),
    }


def prepare_feedback_scope(mission_id, teacher, class_id=None):
    """Resolve a teacher-visible classroom matrix using the existing scope rules."""
    return prepare_classroom_matrix(mission_id, teacher, class_id)


def build_feedback_snapshot(mission: LearningMission, matrix: TeacherWrongBookMatrix) -> dict:
    """Build one immutable input snapshot; no feedback table is changed here."""
    raw = classroom_statistics_payload(mission, matrix)
    questions = [_question_context(row) for row in raw.get('questions', [])]
    question_by_id = {row['question_id']: row for row in questions}
    students = []
    for row in raw.get('students', []):
        wrong_questions = []
        for cell in row.get('cells', []):
            if cell.get('wrong') and cell.get('source_question_id') in question_by_id:
                wrong_questions.append(question_by_id[cell['source_question_id']])
        wrong_questions.sort(key=lambda item: item['sort_no'])
        students.append({
            'student_id': str(row.get('student_id') or ''),
            'student_name': _text(row.get('student_name'), 100),
            'student_no': _text(row.get('student_no'), 100),
            'class_id': str(row.get('class_id') or matrix.class_obj_id or ''),
            'class_name': _text(getattr(getattr(matrix, 'class_obj', None), 'class_name', ''), 200),
            'wrong_count': len(wrong_questions),
            'wrong_rate': float(row.get('wrong_rate') or 0),
            'wrong_question_nos': [item['question_no'] for item in wrong_questions],
            'knowledge_summary': sorted({label for item in wrong_questions for label in item['knowledge_points']}),
            'wrong_questions': wrong_questions,
        })

    knowledge = defaultdict(lambda: {
        'knowledge_key': '', 'knowledge_name': '', 'question_ids': set(),
        'question_count': 0, 'wrong_count': 0,
    })
    question_wrong = {row['question_id']: row['wrong_count'] for row in questions}
    for question in questions:
        for label in question['knowledge_points']:
            item = knowledge[_knowledge_key(label)]
            item['knowledge_key'] = _knowledge_key(label)
            item['knowledge_name'] = label
            item['question_ids'].add(question['question_id'])
            item['question_count'] += 1
            item['wrong_count'] += question_wrong.get(question['question_id'], 0)
    participant_count = len(students)
    for item in knowledge.values():
        item['denominator'] = participant_count * item['question_count']
        item['error_rate'] = round(item['wrong_count'] / item['denominator'] * 100, 2) if item['denominator'] else 0
        item['mastery_level'] = (
            'good' if item['error_rate'] < 30 else
            'attention' if item['error_rate'] < 50 else 'weak'
        )
        item['question_ids'] = sorted(item['question_ids'])
    knowledge_stats = sorted(knowledge.values(), key=lambda item: (-item['error_rate'], item['knowledge_name']))
    for index, item in enumerate(knowledge_stats, 1):
        item['sort_no'] = index

    summary = raw.get('summary') or {}
    return {
        'mission_id': str(mission.id),
        'class_id': str(matrix.class_obj_id or ''),
        'mission_name': mission.mission_name,
        'participant_count': participant_count,
        'question_count': len(questions),
        'total_wrong_count': int(summary.get('accumulated_wrong_count') or 0),
        'average_wrong_count': float(summary.get('average_wrong_count') or 0),
        'questions': questions,
        'knowledge_stats': knowledge_stats,
        'threshold_version': MASTERY_THRESHOLD_VERSION,
        'students': students,
    }


def aggregate_question_stats(snapshot: dict) -> list[dict]:
    return list(snapshot.get('questions') or [])


def aggregate_knowledge_stats(snapshot: dict) -> list[dict]:
    return list(snapshot.get('knowledge_stats') or [])


def _review_arrangement(wrong_questions: list[dict]) -> list[str]:
    if not wrong_questions:
        return ['保持复习习惯，继续巩固本节课内容。']
    labels = []
    for question in wrong_questions:
        for label in question['knowledge_points']:
            if label not in labels and label != KNOWLEDGE_UNCLASSIFIED:
                labels.append(label)
    question_nos = '、'.join(question['question_no'] for question in wrong_questions)
    result = [f'订正第{question_nos}题，写清错误原因和正确解题依据。']
    if labels:
        result.append('重点复习：' + '、'.join(labels[:5]) + '。')
    else:
        result.append('对照题干、解析和答案，完成待归类题目的订正。')
    return result


@transaction.atomic
def create_feedback_report(mission, matrix, teacher, idempotency_key=''):
    snapshot = build_feedback_snapshot(mission, matrix)
    if not snapshot['participant_count'] or not snapshot['question_count']:
        raise ValueError('课堂没有可统计的学生或题目')
    key = _text(idempotency_key, 100)
    if key:
        existing = ClassroomFeedbackReport.objects.filter(
            mission=mission, class_obj_id=matrix.class_obj_id,
            source_matrix_version=matrix.version, idempotency_key=key,
        ).first()
        if existing:
            return existing
    generation_no = ClassroomFeedbackReport.objects.filter(
        mission=mission, class_obj_id=matrix.class_obj_id,
    ).count() + 1
    report = ClassroomFeedbackReport.objects.create(
        mission=mission, class_obj_id=matrix.class_obj_id, source_matrix=matrix,
        source_matrix_version=matrix.version, generation_no=generation_no,
        idempotency_key=key, participant_count=snapshot['participant_count'],
        question_count=snapshot['question_count'], total_wrong_count=snapshot['total_wrong_count'],
        average_wrong_count=Decimal(str(snapshot['average_wrong_count'])),
        class_summary_json={
            'threshold_version': MASTERY_THRESHOLD_VERSION,
            'knowledge_stats': snapshot['knowledge_stats'],
        },
        input_snapshot=snapshot, created_by=teacher, model_name=MODEL_NAME,
        prompt_version=PROMPT_VERSION,
    )
    ClassroomFeedbackQuestionStat.objects.bulk_create([
        ClassroomFeedbackQuestionStat(
            report=report, source_question_id=row['question_id'],
            node_id=row.get('node_id') or None, node_name_snapshot=row.get('node_name', ''),
            node_sort_no=row.get('node_sort_no', 0), question_no=row['question_no'],
            wrong_count=row['wrong_count'], wrong_rate=row['wrong_rate'],
            knowledge_labels=row['knowledge_points'], question_snapshot={
                key: row.get(key, '') for key in ('stem', 'answer', 'analysis', 'question_type', 'knowledge_points')
            }, sort_no=row['sort_no'],
        ) for row in snapshot['questions']
    ])
    ClassroomFeedbackKnowledgeStat.objects.bulk_create([
        ClassroomFeedbackKnowledgeStat(
            report=report, knowledge_key=row['knowledge_key'], knowledge_name=row['knowledge_name'],
            question_count=row['question_count'], wrong_count=row['wrong_count'],
            denominator=row['denominator'], error_rate=row['error_rate'],
            mastery_level=row['mastery_level'], question_ids=row['question_ids'], sort_no=row['sort_no'],
        ) for row in snapshot['knowledge_stats']
    ])
    ClassroomFeedbackStudent.objects.bulk_create([
        ClassroomFeedbackStudent(
            report=report, student_id=row['student_id'], student_name_snapshot=row['student_name'],
            student_no_snapshot=row['student_no'], class_name_snapshot=row['class_name'],
            wrong_question_ids=[item['question_id'] for item in row['wrong_questions']],
            wrong_question_nos=[item['question_no'] for item in row['wrong_questions']],
            wrong_count=row['wrong_count'], wrong_rate=row['wrong_rate'],
            knowledge_summary=sorted({label for item in row['wrong_questions'] for label in item['knowledge_points']}),
            review_arrangement=_review_arrangement(row['wrong_questions']),
            ai_model=MODEL_NAME, prompt_version=PROMPT_VERSION,
        ) for row in snapshot['students']
    ])
    return report


def mark_stale_reports(mission, matrix):
    return ClassroomFeedbackReport.objects.filter(
        mission=mission, class_obj_id=matrix.class_obj_id,
        source_matrix_version__lt=matrix.version,
        status__in=('queued', 'running', 'ready', 'partial'),
    ).update(status='stale', updated_at=timezone.now())


def _question_payload(row):
    return {
        'source_question_id': str(row.source_question_id),
        'question_no': row.question_no,
        'node_name': row.node_name_snapshot,
        'wrong_count': row.wrong_count,
        'wrong_rate': float(row.wrong_rate),
        'knowledge_points': row.knowledge_labels or [],
        'question_snapshot': row.question_snapshot or {},
    }


def report_payload(report, *, include_students=True, student=None):
    if report is None:
        return None
    questions = list(report.question_stats.all())
    knowledge = list(report.knowledge_stats.all())
    rows = list(report.student_feedbacks.select_related('student'))
    question_by_id = {str(row.source_question_id): row for row in questions}
    if student is not None:
        rows = [row for row in rows if str(row.student_id) == str(student.id)]
    student_payload = [{
        'student_id': str(row.student_id),
        'student_name': row.student_name_snapshot,
        'wrong_question_nos': row.wrong_question_nos or [],
        'wrong_questions': [{
            'question_no': question_by_id[str(question_id)].question_no,
            'node_name': question_by_id[str(question_id)].node_name_snapshot,
        } for question_id in row.wrong_question_ids if str(question_id) in question_by_id],
        'wrong_count': row.wrong_count,
        'wrong_rate': float(row.wrong_rate),
        'knowledge_summary': row.knowledge_summary or [],
        'review_arrangement': row.review_arrangement or [],
        'feedback_text': row.feedback_text,
        'ai_status': row.ai_status,
        'ai_model': row.ai_model,
    } for row in rows]
    result = {
        'id': str(report.id), 'status': report.status,
        'mission_id': str(report.mission_id), 'class_id': str(report.class_obj_id),
        'mission_name': report.mission.mission_name,
        'class_name': report.class_obj.class_name,
        'source_matrix_version': report.source_matrix_version,
        'participant_count': report.participant_count, 'question_count': report.question_count,
        'total_wrong_count': report.total_wrong_count, 'average_wrong_count': float(report.average_wrong_count),
        'threshold_version': (report.class_summary_json or {}).get(
            'threshold_version', MASTERY_THRESHOLD_VERSION,
        ),
        'class_feedback_text': report.class_feedback_text,
        'knowledge_stats': [{
            'knowledge_key': row.knowledge_key, 'knowledge_name': row.knowledge_name,
            'question_count': row.question_count, 'wrong_count': row.wrong_count,
            'denominator': row.denominator, 'error_rate': float(row.error_rate),
            'mastery_level': row.mastery_level, 'question_ids': row.question_ids or [],
        } for row in knowledge],
        'question_stats': [_question_payload(row) for row in questions],
        'high_error_questions': [_question_payload(row) for row in sorted(
            (item for item in questions if item.wrong_count > 0),
            key=lambda item: (-float(item.wrong_rate), item.sort_no),
        )[:10]],
        'students': student_payload if include_students else [],
        'updated_at': report.updated_at,
        'completed_at': report.completed_at,
        'error_message': report.error_message,
        'pdf_download_url': media_url(report.pdf_file_path) if report.pdf_file_path else None,
    }
    if student is not None:
        result['student_feedback'] = student_payload[0] if student_payload else None
        result.pop('students', None)
    return result


def latest_report(mission_id, class_id):
    return ClassroomFeedbackReport.objects.filter(
        mission_id=mission_id, class_obj_id=class_id,
    ).select_related('mission', 'class_obj').prefetch_related(
        'question_stats', 'knowledge_stats', 'student_feedbacks',
    ).first()


def parent_feedback_available(mission, student):
    if not is_classroom_practice(mission):
        return False, None
    class_ids = ClassStudent.objects.filter(
        student=student, class_obj__mission_assignments__mission=mission,
        class_obj__mission_assignments__status='active', status='active',
    ).values_list('class_obj_id', flat=True).distinct()
    for class_id in class_ids:
        report = latest_report(mission.id, class_id)
        if report and report.status in ('ready', 'partial'):
            return True, report.status
    if mission.class_obj_id and ClassStudent.objects.filter(
        student=student, class_obj_id=mission.class_obj_id, status='active',
    ).exists():
        report = latest_report(mission.id, mission.class_obj_id)
        if report and report.status in ('ready', 'partial'):
            return True, report.status
    return False, None
