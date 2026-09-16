"""Asynchronous classroom feedback generation tasks."""
from __future__ import annotations

from celery import shared_task
from django.utils import timezone

from .ai import (
    CLASS_TASK,
    MODEL_NAME,
    STUDENT_TASK,
    class_fallback,
    generate_feedback,
    input_fingerprint,
    student_fallback,
)
from .models import ClassroomFeedbackReport, ClassroomFeedbackStudent


def _class_context(report):
    snapshot = report.input_snapshot or {}
    stats = snapshot.get('knowledge_stats') or []
    return {
        'mission_name': snapshot.get('mission_name') or report.mission.mission_name,
        'participant_count': report.participant_count,
        'question_count': report.question_count,
        'total_wrong_count': report.total_wrong_count,
        'average_wrong_count': float(report.average_wrong_count),
        'knowledge_points': [row.get('knowledge_name') for row in stats],
        'weak_knowledge_points': [row.get('knowledge_name') for row in stats if float(row.get('error_rate') or 0) >= 50],
        'good_knowledge_points': [row.get('knowledge_name') for row in stats if float(row.get('error_rate') or 0) < 30],
        'knowledge_stats': stats,
        'high_error_questions': sorted(
            snapshot.get('questions') or [],
            key=lambda row: (-float(row.get('wrong_rate') or 0), row.get('sort_no', 0)),
        )[:10],
    }


def _student_context(report, row: ClassroomFeedbackStudent):
    snapshot = report.input_snapshot or {}
    question_map = {
        str(item.get('question_id')): item for item in snapshot.get('questions') or []
    }
    wrong_questions = [question_map[str(value)] for value in row.wrong_question_ids if str(value) in question_map]
    return {
        'student_id': str(row.student_id),
        'student_name': row.student_name_snapshot,
        'mission_name': snapshot.get('mission_name') or report.mission.mission_name,
        'wrong_count': row.wrong_count,
        'wrong_rate': float(row.wrong_rate),
        'wrong_question_nos': row.wrong_question_nos or [],
        'knowledge_summary': row.knowledge_summary or [],
        'allowed_knowledge_points': sorted({
            str(item.get('knowledge_name'))
            for item in snapshot.get('knowledge_stats') or []
            if item.get('knowledge_name')
        } | {str(item) for item in row.knowledge_summary or []}),
        'review_arrangement': row.review_arrangement or [],
        'wrong_questions': wrong_questions,
        'class_knowledge_stats': snapshot.get('knowledge_stats') or [],
        'class_high_error_questions': sorted(
            snapshot.get('questions') or [],
            key=lambda item: (-float(item.get('wrong_rate') or 0), item.get('sort_no', 0)),
        )[:10],
        'required_tokens': tuple(
            [str(value) for value in row.wrong_question_nos]
            + [str(value) for value in row.knowledge_summary]
        ),
    }


def _set_status(report, status, **values):
    values.update(status=status, updated_at=timezone.now())
    ClassroomFeedbackReport.objects.filter(pk=report.pk).update(**values)


def _generate_student_row(report, row, used_texts):
    context = _student_context(report, row)
    context['input_fingerprint'] = input_fingerprint(context)
    row.ai_input_fingerprint = context['input_fingerprint']
    try:
        generated, model = generate_feedback(STUDENT_TASK, context)
        text = generated['feedback_text']
        if text in used_texts and row.wrong_count:
            context['uniqueness_hint'] = f"请突出本学生题号：{'、'.join(row.wrong_question_nos)}"
            generated, model = generate_feedback(STUDENT_TASK, context)
            text = generated['feedback_text']
        if text in used_texts and row.wrong_count:
            raise ValueError('AI 返回了重复的学生话术')
        row.feedback_text = text
        row.ai_status = 'succeeded'
        row.ai_model = model or MODEL_NAME
        row.ai_error_message = ''
        used_texts.add(text)
    except Exception as exc:
        row.feedback_text = student_fallback(context)
        row.ai_status = 'fallback'
        row.ai_model = MODEL_NAME
        row.ai_error_message = str(exc)[:1000]
        used_texts.add(row.feedback_text)
    row.save(update_fields=[
        'feedback_text', 'ai_status', 'ai_model', 'ai_error_message',
        'ai_input_fingerprint', 'updated_at',
    ])
    return row.ai_status


@shared_task(
    bind=True,
    name='apps.classroom_feedback.tasks.generate_classroom_feedback_report',
    max_retries=0,
)
def generate_classroom_feedback_report(self, report_id):
    try:
        report = ClassroomFeedbackReport.objects.select_related('mission').get(pk=report_id)
    except ClassroomFeedbackReport.DoesNotExist:
        return {'status': 'report_missing', 'report_id': str(report_id)}
    if report.status not in ('queued', 'running'):
        return {'status': report.status, 'report_id': str(report.id)}
    _set_status(report, 'running')
    report.refresh_from_db()
    class_context = _class_context(report)
    class_status = 'succeeded'
    try:
        generated, model = generate_feedback(CLASS_TASK, class_context)
        report.class_feedback_text = generated['feedback_text']
        report.model_name = model or MODEL_NAME
        report.error_message = ''
    except Exception as exc:
        report.class_feedback_text = class_fallback(class_context)
        report.model_name = MODEL_NAME
        report.error_message = str(exc)[:1000]
        class_status = 'fallback'
    report.save(update_fields=['class_feedback_text', 'model_name', 'error_message', 'updated_at'])

    used_texts = set()
    student_statuses = []
    for row in report.student_feedbacks.select_related('student').order_by('student_name_snapshot', 'id'):
        student_statuses.append(_generate_student_row(report, row, used_texts))
    partial = class_status != 'succeeded' or any(status != 'succeeded' for status in student_statuses)
    report.status = 'partial' if partial else 'ready'
    report.completed_at = timezone.now()
    report.save(update_fields=['status', 'completed_at', 'updated_at'])
    return {'status': report.status, 'report_id': str(report.id)}


@shared_task(
    bind=True,
    name='apps.classroom_feedback.tasks.generate_classroom_feedback_student',
    max_retries=0,
)
def generate_classroom_feedback_student(self, report_id, student_id):
    try:
        report = ClassroomFeedbackReport.objects.select_related('mission').get(pk=report_id)
        row = report.student_feedbacks.get(student_id=student_id)
    except (ClassroomFeedbackReport.DoesNotExist, ClassroomFeedbackStudent.DoesNotExist):
        return {'status': 'student_feedback_missing', 'report_id': str(report_id), 'student_id': str(student_id)}
    used = set(report.student_feedbacks.exclude(pk=row.pk).values_list('feedback_text', flat=True))
    status = _generate_student_row(report, row, used)
    return {'status': status, 'report_id': str(report.id), 'student_id': str(row.student_id)}
