"""Backfill content-v1 fingerprint registrations for historical questions."""

from __future__ import annotations

import hashlib
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Prefetch
from django.utils import timezone

from apps.parser.models import ExamQuestion, QuestionContentFingerprint, QuestionImage, QuestionOption
from apps.parser.question_identity import build_content_fingerprint
from apps.study.formula_assets import FORMULA_PLACEHOLDER_RE, formula_key_from_path


def _non_negative_int(value: str) -> int:
    try:
        hours = int(value)
    except ValueError as exc:
        raise CommandError('cleanup-stale-reservations-hours must be an integer') from exc
    if hours < 0:
        raise CommandError('cleanup-stale-reservations-hours must not be negative')
    return hours


def _question_order_key(question: ExamQuestion) -> tuple[object, str]:
    return question.created_at, str(question.pk)


def _asset_sha256(image: QuestionImage) -> str:
    stored_path = str(image.original_file_path or image.file_path or '').strip()
    if not stored_path:
        raise ValueError('image has no stored file path')
    path = Path(stored_path)
    if not path.is_absolute():
        path = Path(settings.MEDIA_ROOT) / path
    if not path.is_file():
        raise ValueError(f'image file is unavailable: {stored_path}')
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _content_v1_fingerprint(question: ExamQuestion) -> str:
    """Build the importer-compatible fingerprint from prefetched question content."""
    options = list(question.options.all())
    images = list(question.images.all())
    illustrations = [image for image in images if image.image_type != 'formula']
    formulas = [image for image in images if image.image_type == 'formula']

    image_hashes = [_asset_sha256(image) for image in [*illustrations, *formulas]]
    formula_identities: dict[str, str] = {}
    formula_texts: list[str] = []
    for image, image_hash in zip(formulas, image_hashes[len(illustrations):]):
        source_path = image.original_file_path or image.file_path
        formula_key = formula_key_from_path(source_path, question.pk)
        description = str(image.description or '').strip()
        identity = image_hash if not description or description == formula_key else description
        formula_texts.append(identity)
        formula_identities[formula_key] = identity
        if description:
            formula_identities.setdefault(description, identity)

    def normalize_formulas(value: object) -> str:
        return FORMULA_PLACEHOLDER_RE.sub(
            lambda match: f'[[formula:{formula_identities.get(match.group(1), match.group(1))}]]',
            str(value or ''),
        )

    return build_content_fingerprint(
        stem=normalize_formulas(question.stem),
        options=[normalize_formulas(option.content) for option in options],
        formula_texts=formula_texts,
        image_hashes=image_hashes,
    )


class Command(BaseCommand):
    help = 'Backfill content-v1 fingerprint registrations without changing historical questions.'

    def add_arguments(self, parser):
        mode = parser.add_mutually_exclusive_group()
        mode.add_argument('--dry-run', action='store_true', help='Report candidates without writing registry rows.')
        mode.add_argument('--apply', action='store_true', help='Create and repair registry rows.')
        parser.add_argument(
            '--cleanup-stale-reservations-hours',
            type=_non_negative_int,
            help='Remove unlinked reserving rows older than this many hours when applying.',
        )

    def handle(self, *args, **options):
        should_apply = bool(options['apply'])
        cleanup_hours = options.get('cleanup_stale_reservations_hours')
        stats = {
            'questions': 0,
            'candidates': 0,
            'created': 0,
            'canonical_repaired': 0,
            'existing': 0,
            'reserved': 0,
            'errors': 0,
            'stale_candidates': 0,
            'stale_deleted': 0,
        }

        if cleanup_hours is not None:
            cutoff = timezone.now() - timedelta(hours=cleanup_hours)
            stale_reservations = QuestionContentFingerprint.objects.filter(
                state=QuestionContentFingerprint.State.RESERVING,
                canonical_question__isnull=True,
                created_at__lt=cutoff,
            )
            stats['stale_candidates'] = stale_reservations.count()
            if should_apply:
                stats['stale_deleted'] = stale_reservations.delete()[0]

        questions = ExamQuestion.objects.order_by('created_at', 'id').prefetch_related(
            Prefetch('options', queryset=QuestionOption.objects.order_by('sort_order', 'id')),
            Prefetch('images', queryset=QuestionImage.objects.order_by('sort_order', 'id')),
        )
        for question in questions.iterator(chunk_size=100):
            stats['questions'] += 1
            try:
                fingerprint = _content_v1_fingerprint(question)
            except (OSError, ValueError) as exc:
                stats['errors'] += 1
                self.stderr.write(f'question={question.pk} skipped: {exc}')
                continue

            stats['candidates'] += 1
            if not should_apply:
                continue

            registry = QuestionContentFingerprint.objects.select_related(
                'canonical_question'
            ).filter(fingerprint=fingerprint).first()
            if registry is None:
                QuestionContentFingerprint.objects.create(
                    fingerprint=fingerprint,
                    canonical_question=question,
                    state=QuestionContentFingerprint.State.ACTIVE,
                )
                stats['created'] += 1
                continue

            if (
                registry.state == QuestionContentFingerprint.State.RESERVING
                and registry.canonical_question_id is None
            ):
                stats['reserved'] += 1
                continue
            if registry.state != QuestionContentFingerprint.State.ACTIVE or not registry.canonical_question_id:
                stats['reserved'] += 1
                continue

            stats['existing'] += 1
            canonical = registry.canonical_question
            if _question_order_key(question) < _question_order_key(canonical):
                registry.canonical_question = question
                registry.save(update_fields=['canonical_question', 'updated_at'])
                stats['canonical_repaired'] += 1

        mode = 'APPLIED' if should_apply else 'DRY-RUN'
        self.stdout.write(
            f'{mode} questions={stats["questions"]} candidates={stats["candidates"]} '
            f'created={stats["created"]} existing={stats["existing"]} '
            f'canonical_repaired={stats["canonical_repaired"]} reserved={stats["reserved"]} '
            f'errors={stats["errors"]} stale_candidates={stats["stale_candidates"]} '
            f'stale_deleted={stats["stale_deleted"]}'
        )
