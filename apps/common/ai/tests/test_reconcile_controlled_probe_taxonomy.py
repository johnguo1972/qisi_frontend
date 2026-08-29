from unittest.mock import patch

import pytest
from django.core.management import call_command

from apps.parser.models import ExamPaper, ExamQuestion


def _question(*, tags, probe=None, knowledge=None, difficulty=None, level=None):
    paper = ExamPaper.objects.create(title='Controlled reconcile', subject='physics')
    return ExamQuestion.objects.create(
        paper=paper,
        stem='Controlled probe question',
        question_type='single_choice',
        subject='physics',
        tags=tags,
        ai_probe_result=probe,
        ai_knowledge_enrichment=knowledge,
        difficulty=difficulty,
        difficulty_level=level,
    )


@pytest.mark.django_db
def test_reconcile_command_queues_only_tagged_questions_missing_controlled_probe():
    tag = 'controlled-taxonomy-fixture'
    missing = _question(tags=[tag])
    _question(
        tags=[tag],
        probe={
            'subject': 'physics',
            'question_type': 'single_choice',
            'normalized_text': 'Controlled probe question',
            'difficulty_level': 'L3',
            'taxonomy': {'scope': {'topic_id': 'physics-junior-mechanics'}},
        },
        knowledge={
            'knowledge_modules': ['Speed and motion'],
            'difficulty_level': 'L3',
        },
        difficulty='3.20',
        level='L3',
    )

    with patch(
        'apps.review.tasks.single_probe_ai_process_question.delay'
    ) as enqueue:
        call_command(
            'reconcile_controlled_probe_taxonomy',
            tag=tag,
        )

    enqueue.assert_called_once_with(str(missing.id), model=None)
