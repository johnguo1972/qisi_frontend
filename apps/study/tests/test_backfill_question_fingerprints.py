from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.papers.models import ExamPaper
from apps.parser.question_identity import build_content_fingerprint
from apps.parser.models import (
    ExamQuestion,
    QuestionContentFingerprint,
    QuestionOption,
)


def create_question(*, question_no, stem, options=()):
    paper = ExamPaper.objects.create(
        title=f'Backfill paper {question_no}',
        subject='math',
        source_file_path=f'backfill-{question_no}.pdf',
    )
    question = ExamQuestion.objects.create(
        paper=paper,
        question_no=question_no,
        question_type='single_choice',
        stem=stem,
    )
    for sort_order, content in enumerate(options):
        QuestionOption.objects.create(
            question=question,
            option_label=chr(65 + sort_order),
            content=content,
            sort_order=sort_order,
        )
    return question


@pytest.mark.django_db
def test_dry_run_reports_candidates_without_creating_fingerprint_registry():
    create_question(question_no='1', stem='1 + 1 = ?', options=('1', '2'))

    call_command('backfill_question_fingerprints', '--dry-run')

    assert QuestionContentFingerprint.objects.count() == 0


@pytest.mark.django_db
def test_apply_preserves_duplicate_questions_and_uses_the_earliest_as_canonical():
    earliest = create_question(question_no='1', stem='同一道题', options=('甲', '乙'))
    later = create_question(question_no='2', stem='同一道题', options=('甲', '乙'))
    now = timezone.now()
    ExamQuestion.objects.filter(pk=earliest.pk).update(created_at=now - timedelta(days=2))
    ExamQuestion.objects.filter(pk=later.pk).update(created_at=now - timedelta(days=1))

    call_command('backfill_question_fingerprints', '--apply')

    registry = QuestionContentFingerprint.objects.get()
    assert ExamQuestion.objects.filter(pk__in=(earliest.pk, later.pk)).count() == 2
    assert registry.fingerprint == build_content_fingerprint(
        stem='同一道题',
        options=['甲', '乙'],
        formula_texts=[],
        image_hashes=[],
    )
    assert registry.canonical_question_id == earliest.id
    assert registry.state == QuestionContentFingerprint.State.ACTIVE


@pytest.mark.django_db
def test_cleanup_removes_only_old_unlinked_reservations_and_never_active_records():
    active_question = create_question(question_no='active', stem='保留活动指纹')
    active_fingerprint = build_content_fingerprint(
        stem=active_question.stem,
        options=[],
        formula_texts=[],
        image_hashes=[],
    )
    active = QuestionContentFingerprint.objects.create(
        fingerprint=active_fingerprint,
        canonical_question=active_question,
        state=QuestionContentFingerprint.State.ACTIVE,
    )
    stale = QuestionContentFingerprint.objects.create(fingerprint='a' * 64)
    fresh = QuestionContentFingerprint.objects.create(fingerprint='b' * 64)
    old_time = timezone.now() - timedelta(hours=2)
    QuestionContentFingerprint.objects.filter(pk__in=(active.pk, stale.pk)).update(
        created_at=old_time,
        updated_at=old_time,
    )

    call_command(
        'backfill_question_fingerprints',
        '--apply',
        '--cleanup-stale-reservations-hours=1',
    )

    assert not QuestionContentFingerprint.objects.filter(pk=stale.pk).exists()
    assert QuestionContentFingerprint.objects.filter(pk=active.pk).exists()
    assert QuestionContentFingerprint.objects.filter(pk=fresh.pk).exists()
