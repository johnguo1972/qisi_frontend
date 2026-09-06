from datetime import timedelta
from pathlib import Path

import pytest
from django.core.management import CommandError, call_command
from django.utils import timezone

from apps.papers.models import ExamPaper
from apps.parser.question_identity import build_content_fingerprint
from apps.parser.models import (
    ExamQuestion,
    QuestionContentFingerprint,
    QuestionImage,
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
def test_apply_skips_formula_assets_when_custom_key_and_identity_are_ambiguous(tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path / 'media'
    question = create_question(
        question_no='formula',
        stem='计算 [[formula:custom_formula_key]]',
    )
    relative_path = Path('exams') / 'historical' / 'source_formula_01.png'
    asset_path = settings.MEDIA_ROOT / relative_path
    asset_path.parent.mkdir(parents=True)
    asset_path.write_bytes(b'formula-image')
    QuestionImage.objects.create(
        paper=question.paper,
        question=question,
        image_type='formula',
        file_path=relative_path.as_posix(),
        original_file_path=relative_path.as_posix(),
        # An import with both recognized_text and alt_text stores only this
        # alt value, so it cannot prove the content-v1 formula identity.
        description='alternative text',
    )

    call_command('backfill_question_fingerprints', '--apply')

    assert not QuestionContentFingerprint.objects.exists()


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


@pytest.mark.django_db
def test_dry_run_cleanup_does_not_delete_stale_reservations():
    stale = QuestionContentFingerprint.objects.create(fingerprint='c' * 64)
    old_time = timezone.now() - timedelta(hours=2)
    QuestionContentFingerprint.objects.filter(pk=stale.pk).update(created_at=old_time)

    call_command(
        'backfill_question_fingerprints',
        '--dry-run',
        '--cleanup-stale-reservations-hours=1',
    )

    assert QuestionContentFingerprint.objects.filter(pk=stale.pk).exists()


@pytest.mark.django_db
def test_apply_corrects_an_existing_registry_to_the_earliest_question():
    earliest = create_question(question_no='early', stem='已有登记题')
    later = create_question(question_no='late', stem='已有登记题')
    now = timezone.now()
    ExamQuestion.objects.filter(pk=earliest.pk).update(created_at=now - timedelta(days=2))
    ExamQuestion.objects.filter(pk=later.pk).update(created_at=now - timedelta(days=1))
    fingerprint = build_content_fingerprint(
        stem='已有登记题', options=[], formula_texts=[], image_hashes=[]
    )
    registry = QuestionContentFingerprint.objects.create(
        fingerprint=fingerprint,
        canonical_question=later,
        state=QuestionContentFingerprint.State.ACTIVE,
    )

    call_command('backfill_question_fingerprints', '--apply')

    registry.refresh_from_db()
    assert registry.canonical_question_id == earliest.id


@pytest.mark.django_db
def test_apply_leaves_a_concurrent_reservation_to_its_owner(monkeypatch):
    create_question(question_no='conflict', stem='并发登记题')
    from apps.study.management.commands import backfill_question_fingerprints

    def concurrent_reservation(_fingerprint):
        return QuestionContentFingerprint(
            fingerprint='d' * 64,
            state=QuestionContentFingerprint.State.RESERVING,
        ), False

    monkeypatch.setattr(
        backfill_question_fingerprints,
        'reserve_content_fingerprint',
        concurrent_reservation,
    )

    call_command('backfill_question_fingerprints', '--apply')

    assert not QuestionContentFingerprint.objects.exists()


def test_command_rejects_dry_run_and_apply_together():
    with pytest.raises(CommandError):
        call_command('backfill_question_fingerprints', '--dry-run', '--apply')
