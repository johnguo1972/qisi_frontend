"""Paper and question code generation utilities."""
import re
from django.db import IntegrityError, transaction


# Subject first letter mapping
SUBJECT_FIRST_LETTER = {
    '数学': 'M',
    '物理': 'P',
    '化学': 'H',
    '生物': 'S',
    '语文': 'Y',
    '英语': 'E',
}

# Grade character mapping: grade text -> single char
GRADE_CHAR_MAP = {
    '1': '1', '2': '2', '3': '3', '4': '4', '5': '5',
    '6': '6', '7': '7', '8': '8', '9': '9',
    '一年级': '1', '二年级': '2', '三年级': '3',
    '四年级': '4', '五年级': '5', '六年级': '6',
    '七年级': '7', '八年级': '8', '九年级': '9',
    '高一': 'A', '高二': 'B', '高三': 'C',
    '10': 'A', '11': 'B', '12': 'C',
}

# Chinese numeral to integer mapping (sorted by length desc for greedy match)
CHINESE_NUMERAL_TO_INT = [
    ('十二', 12), ('十一', 11), ('十', 10),
    ('九', 9), ('八', 8), ('七', 7), ('六', 6),
    ('五', 5), ('四', 4), ('三', 3), ('二', 2), ('一', 1),
]


def _resolve_grade_char(grade: str | None) -> str:
    """Map a free-text grade string to a single character."""
    if not grade:
        return 'X'
    grade = grade.strip()
    if grade in GRADE_CHAR_MAP:
        return GRADE_CHAR_MAP[grade]
    # Try extracting trailing digit
    match = re.search(r'(\d+)', grade)
    if match:
        num = int(match.group(1))
        if 1 <= num <= 9:
            return str(num)
        elif num == 10:
            return 'A'
        elif num == 11:
            return 'B'
        elif num == 12:
            return 'C'
    return 'X'


def generate_paper_code(subject: str, grade: str | None = None) -> str:
    """Generate a unique paper code.

    Format: SubjectLetter + GradeChar + 4-digit zero-padded sequence.
    Example: 数学+九年级 -> M90001, 物理+高一 -> PA0002.

    Uses a DB-level counter table with select_for_update for atomicity.
    """
    from apps.papers.models import PaperCodeCounter

    letter = SUBJECT_FIRST_LETTER.get(subject or '', 'X')
    grade_char = _resolve_grade_char(grade)

    with transaction.atomic():
        counter, _ = PaperCodeCounter.objects.select_for_update().get_or_create(
            letter=letter,
            grade_char=grade_char,
            defaults={'next_seq': 1},
        )
        seq = counter.next_seq
        counter.next_seq += 1
        counter.save(update_fields=['next_seq'])

    return f'{letter}{grade_char}{seq:04d}'


def _resolve_subject_letter(subject: str) -> str:
    """Map subject to a single-letter prefix for system IDs.

    Supports both Chinese (数学/M) and single-letter (M) subjects.
    """
    if not subject:
        return 'X'
    # Single-letter subject (e.g., 'M', 'P') — use directly
    if subject in SUBJECT_FIRST_LETTER.values():
        return subject
    # Chinese subject (e.g., '数学', '物理') — look up mapping
    return SUBJECT_FIRST_LETTER.get(subject, 'X')


def _max_existing_question_sequence(letter: str, question_model) -> int:
    """Return the largest valid five-hex-digit sequence for one ID prefix."""
    # All valid values are fixed-width uppercase hexadecimal strings, so
    # reverse lexical order is also reverse numeric order.  This avoids
    # scanning every existing question for every row in a large import.
    for system_id in question_model.objects.filter(
        system_id__gte=f'{letter}00000',
        system_id__lte=f'{letter}FFFFF',
    ).order_by('-system_id').values_list('system_id', flat=True).iterator():
        if not system_id or len(system_id) != 6 or system_id[0] != letter:
            continue
        try:
            return int(system_id[1:], 16)
        except ValueError:
            continue
    return 0


def _get_locked_question_counter(subject: str, counter_model, *, create: bool = True):
    """Fetch the per-subject counter while retaining a row lock for this transaction."""
    try:
        return counter_model.objects.select_for_update().get(subject=subject)
    except counter_model.DoesNotExist:
        if not create:
            return None
        # The savepoint keeps a concurrent unique-key race from poisoning the
        # surrounding allocation transaction.
        try:
            with transaction.atomic():
                counter_model.objects.create(subject=subject, next_seq=1)
        except IntegrityError:
            pass
        return counter_model.objects.select_for_update().get(subject=subject)


def reconcile_question_id_counter(subject: str, *, apply: bool = False) -> dict:
    """Report or persist the minimum safe next sequence for one subject.

    Callers that mutate must use this helper inside a transaction so the
    counter row stays locked until the next ID is reserved.
    """
    from apps.parser.models import ExamQuestion
    from apps.papers.models import QuestionIDCounter

    normalized_subject = subject or ''
    letter = _resolve_subject_letter(normalized_subject)
    counter = _get_locked_question_counter(
        normalized_subject,
        QuestionIDCounter,
        create=apply,
    )
    highest_existing = _max_existing_question_sequence(letter, ExamQuestion)
    previous_next_seq = counter.next_seq if counter else 1
    safe_next_seq = max(previous_next_seq, highest_existing + 1)
    if apply and safe_next_seq != previous_next_seq:
        if counter is None:
            counter = _get_locked_question_counter(normalized_subject, QuestionIDCounter)
        counter.next_seq = safe_next_seq
        counter.save(update_fields=['next_seq'])
    return {
        'subject': normalized_subject,
        'letter': letter,
        'previous_next_seq': previous_next_seq,
        'highest_existing': highest_existing,
        'next_seq': safe_next_seq,
        'changed': safe_next_seq != previous_next_seq,
    }


def generate_question_system_id(subject: str) -> str:
    """Generate a globally unique question system ID.

    Format: SubjectLetter + 5-digit hex sequence (zero-padded).
    Example: M00001, M00002, ..., M0FFFF (max 1,048,575 per subject).

    Uses a DB-level counter table with select_for_update for atomicity.

    Before reserving an ID, reconciles a stale counter with the highest valid
    existing ID for the same prefix.  Counter locking serializes allocation,
    including after a rolled-back import transaction.
    """
    letter = _resolve_subject_letter(subject or '')
    from apps.parser.models import ExamQuestion

    with transaction.atomic():
        reconciliation = reconcile_question_id_counter(subject or '', apply=True)
        seq = reconciliation['next_seq']
        while seq <= 0xFFFFF:
            system_id = f'{letter}{seq:05X}'
            if not ExamQuestion.objects.filter(system_id=system_id).exists():
                # The reconciliation helper saved the safe value.  Advance it
                # only after this exact value is selected for this transaction.
                from apps.papers.models import QuestionIDCounter
                counter = QuestionIDCounter.objects.select_for_update().get(subject=subject or '')
                counter.next_seq = seq + 1
                counter.save(update_fields=['next_seq'])
                return system_id
            seq += 1

    raise RuntimeError(f'Question system ID sequence exhausted for subject={subject}')


def extract_major_section_no(section_title: str | None) -> int:
    """Extract the leading Chinese numeral from a section title.

    "一、选择题" -> 1, "二、填空题" -> 2, "" -> 0.
    """
    if not section_title:
        return 0
    for numeral, value in CHINESE_NUMERAL_TO_INT:
        if section_title.startswith(numeral):
            return value
    # Fallback: try Arabic numeral at start
    match = re.match(r'^(\d+)', section_title)
    if match:
        return int(match.group(1))
    return 0


def batch_compute_paper_question_nos(paper, questions: list) -> list[str]:
    """Compute paper_question_no for a batch of questions before save.

    Format: paper_code-major_section_no-minor_question_no
    Example: M90001-1-3.

    Args:
        paper: ExamPaper instance (must have paper_code set).
        questions: List of question dicts (each with section_title),
                   ordered by sort_order.

    Returns:
        List of paper_question_no strings, same order as input.
    """
    paper_code = paper.paper_code or f'P{paper.id}'
    section_counters = {}  # section_title -> next_minor_no
    result = []

    for q in questions:
        section_title = q.get('section_title', '')
        major_no = extract_major_section_no(section_title)

        if section_title not in section_counters:
            section_counters[section_title] = 1
        minor_no = section_counters[section_title]
        section_counters[section_title] += 1

        result.append(f'{paper_code}-{major_no}-{minor_no}')

    return result
