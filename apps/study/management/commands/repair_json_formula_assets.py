"""Repair formula placeholders left by historical JSON question imports."""

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.common.media import media_url
from apps.parser.models import ExamQuestion
from apps.study.formula_assets import (
    WEB_IMAGE_SUFFIXES,
    FormulaAssetConversionError,
    convert_formula_asset,
    formula_key_from_path,
    render_formula_placeholders,
)


class Command(BaseCommand):
    help = 'Convert imported formula assets and replace [[formula:key]] placeholders.'

    def add_arguments(self, parser):
        parser.add_argument('--paper-id', required=True)
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Persist converted paths and rendered HTML. Without this flag, only inspect.',
        )

    def handle(self, *args, **options):
        paper_id = options['paper_id']
        should_apply = options['apply']
        questions = ExamQuestion.objects.filter(paper_id=paper_id).prefetch_related(
            'images', 'options'
        )
        if not questions.exists():
            raise CommandError(f'No questions found for paper {paper_id}')

        stats = {
            'questions': 0,
            'repaired': 0,
            'converted': 0,
            'unresolved': 0,
            'errors': 0,
        }
        for question in questions.iterator(chunk_size=50):
            stats['questions'] += 1
            formula_urls = {}
            question_failed = False
            for image in question.images.all():
                if image.image_type != 'formula':
                    continue
                current_rel = str(image.file_path or '').replace('\\', '/')
                original_rel = str(image.original_file_path or current_rel).replace('\\', '/')
                key = image.description or formula_key_from_path(original_rel, question.id)
                display_rel = current_rel
                current_suffix = Path(current_rel).suffix.lower()
                if current_suffix not in WEB_IMAGE_SUFFIXES:
                    source = Path(settings.MEDIA_ROOT) / original_rel
                    if not source.exists():
                        self.stderr.write(f'{question.id}: missing formula file {original_rel}')
                        stats['errors'] += 1
                        question_failed = True
                        continue
                    prospective = source.with_suffix('.png')
                    if should_apply:
                        try:
                            prospective = convert_formula_asset(source, prospective)
                        except FormulaAssetConversionError as exc:
                            self.stderr.write(f'{question.id}: {exc}')
                            stats['errors'] += 1
                            question_failed = True
                            continue
                        display_rel = prospective.relative_to(settings.MEDIA_ROOT).as_posix()
                        image.file_path = display_rel
                        image.description = key
                        image.save(update_fields=['file_path', 'description'])
                        stats['converted'] += 1
                    else:
                        display_rel = prospective.relative_to(settings.MEDIA_ROOT).as_posix()
                formula_urls[key] = media_url(display_rel)

            if question_failed and not formula_urls:
                continue

            stem_html, missing = render_formula_placeholders(question.stem, formula_urls)
            answer_html, answer_missing = render_formula_placeholders(question.answer, formula_urls)
            analysis_html, analysis_missing = render_formula_placeholders(
                question.analysis, formula_urls
            )
            all_missing = [*missing, *answer_missing, *analysis_missing]
            rendered_options = []
            for option in question.options.all():
                option_html, option_missing = render_formula_placeholders(
                    option.content, formula_urls
                )
                rendered_options.append((option, option_html))
                all_missing.extend(option_missing)

            stats['unresolved'] += len(set(all_missing))
            has_placeholder = any(
                '[[formula:' in str(value or '')
                for value in (question.stem, question.answer, question.analysis)
            ) or any('[[formula:' in str(option.content or '') for option, _ in rendered_options)
            if has_placeholder:
                stats['repaired'] += 1
            if should_apply:
                with transaction.atomic():
                    question.stem_html = stem_html
                    question.answer = answer_html
                    question.analysis = analysis_html
                    question.formula_need_review = bool(all_missing)
                    question.save(update_fields=[
                        'stem_html', 'answer', 'analysis', 'formula_need_review', 'updated_at'
                    ])
                    for option, option_html in rendered_options:
                        option.content_html = option_html
                        option.save(update_fields=['content_html', 'updated_at'])

        mode = 'APPLIED' if should_apply else 'DRY-RUN'
        self.stdout.write(
            f'{mode} paper={paper_id} questions={stats["questions"]} '
            f'repaired={stats["repaired"]} converted={stats["converted"]} '
            f'unresolved={stats["unresolved"]} errors={stats["errors"]}'
        )
        if should_apply and stats['errors']:
            raise CommandError(f'Formula repair completed with {stats["errors"]} errors')
