"""Cross-page question merge service."""
import logging
import re
from apps.common import status as const

logger = logging.getLogger(__name__)

# Keywords indicating a question is incomplete
INCOMPLETE_INDICATORS = ['（ ）', '( )', '【答案】', '】']
# Pattern for question numbers
QNO_PATTERN = re.compile(r'^[（(]?(\d+)[）)]?[、.\s]?')


def _is_incomplete_question(q: dict) -> bool:
    """Check if a question appears incomplete (e.g., only stem without options)."""
    stem = q.get('stem', '')
    options = q.get('options', [])
    question_type = q.get('question_type', '')

    # Choice question without options is incomplete
    if question_type in (const.QT_SINGLE_CHOICE, const.QT_MULTIPLE_CHOICE) and not options:
        return True

    # Stem ends with bracket suggesting options should follow
    if stem.rstrip().endswith('（ ）') or stem.rstrip().endswith('( )'):
        return True

    return False


def _questions_match(q1: dict, q2: dict) -> bool:
    """Determine if two questions from different pages are the same question."""
    qno1 = q1.get('question_no', '')
    qno2 = q2.get('question_no', '')
    section1 = q1.get('section_title', '')
    section2 = q2.get('section_title', '')

    # Same question number and same section
    if qno1 == qno2 and section1 == section2:
        return True

    # Same question number, and one is incomplete (likely stem-only vs options-only)
    if qno1 == qno2:
        if _is_incomplete_question(q1) or _is_incomplete_question(q2):
            return True

    return False


def merge_cross_page_questions(page_results: list) -> list:
    """Merge questions that span across pages.

    Uses multiple strategies:
    1. Qwen's page_end field (if reliable)
    2. Same question_no across consecutive pages
    3. Incomplete question detection (stem on one page, options on next)

    Args:
        page_results: List of page parse results, each containing
                      {'page_no': int, 'questions': [...]}

    Returns:
        Merged list of all questions.
    """
    all_questions = []

    for page in page_results:
        for q in page.get('questions', []):
            q['page_no'] = page['page_no']
            q['page_end'] = q.get('page_end', page['page_no'])
            all_questions.append(q)

    # Strategy 1: Merge based on page_end from Qwen
    # Strategy 2: Merge based on question_no matching across pages
    merged_indices = set()

    for i in range(len(all_questions)):
        if i in merged_indices:
            continue
        current = all_questions[i]
        current_page = current['page_no']

        # Strategy 1: page_end based merge
        reported_end = current.get('page_end', current_page)
        if reported_end > current_page:
            qno = current.get('question_no', '')
            for j in range(i + 1, len(all_questions)):
                if j in merged_indices:
                    continue
                next_q = all_questions[j]
                if next_q['page_no'] > reported_end:
                    break
                if next_q.get('question_no') == qno and next_q['page_no'] > current_page:
                    _merge_content(current, next_q)
                    merged_indices.add(j)

        # Strategy 2: question_no + incompleteness based merge
        # Look at next page's questions for matching number
        for j in range(i + 1, len(all_questions)):
            if j in merged_indices:
                continue
            next_q = all_questions[j]
            # Only look within 2 pages ahead
            if next_q['page_no'] > current_page + 2:
                break
            # Skip if same page (already handled by Qwen's logic)
            if next_q['page_no'] <= current_page:
                continue
            # Check if they match
            if _questions_match(current, next_q):
                _merge_content(current, next_q)
                merged_indices.add(j)

    # Build final list
    result = []
    for i, q in enumerate(all_questions):
        if i not in merged_indices:
            result.append(q)

    logger.info(f"Merged cross-page questions: {len(result)} total ({len(merged_indices)} merged)")
    return result


def _merge_content(target: dict, source: dict):
    """Merge source question content into target."""
    # Merge stem: only add if source has unique content
    if source.get('stem') and source['stem'] not in target.get('stem', ''):
        target['stem'] = (target.get('stem', '') + ' ' + source['stem']).strip()

    # Merge options: prefer source options if target has none
    if source.get('options') and not target.get('options'):
        target['options'] = source['options']
    elif source.get('options') and target.get('options'):
        # Merge only non-duplicate options
        existing_labels = {opt.get('label') for opt in target['options']}
        for opt in source['options']:
            if opt.get('label') not in existing_labels:
                target['options'].append(opt)

    # Merge images
    if source.get('images'):
        target['images'] = (target.get('images', []) + source['images'])

    # Merge answer/analysis if target is missing them
    if not target.get('answer') and source.get('answer'):
        target['answer'] = source['answer']
    if not target.get('analysis') and source.get('analysis'):
        target['analysis'] = source['analysis']
    if not target.get('solution') and source.get('solution'):
        target['solution'] = source['solution']

    # Update page_end to the furthest page
    target['page_end'] = max(
        target.get('page_end', target['page_no']),
        source.get('page_end', source['page_no'])
    )

    # Mark for review
    target['need_review_reason'] = (
        target.get('need_review_reason', '') +
        f'[跨页P{source["page_no"]}] '
    )
