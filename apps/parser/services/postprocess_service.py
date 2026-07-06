"""Postprocessing service: type normalization, answer separation, formula validation."""
import logging
import re
from apps.parser.services.merge_service import merge_cross_page_questions
from apps.parser.services.formula_service import check_formula_need_review
from apps.common import status as const

logger = logging.getLogger(__name__)


def _fix_question_numbers(questions: list, word_question_numbers: list = None) -> list:
    """Fix duplicate or out-of-order question numbers."""
    seen = set()
    has_duplicates = False
    for q in questions:
        qno = str(q.get('question_no', ''))
        if qno in seen:
            has_duplicates = True
            break
        seen.add(qno)

    if not has_duplicates:
        return questions

    # Renumber using word question numbers as reference
    if word_question_numbers:
        for i, q in enumerate(questions):
            if i < len(word_question_numbers):
                q['question_no'] = word_question_numbers[i]
    else:
        # Simple sequential renumbering
        for i, q in enumerate(questions):
            q['question_no'] = str(i + 1)

    return questions


# Section title to question type mapping
SECTION_TYPE_MAP = {
    '一': const.QT_SINGLE_CHOICE,      # 一、选择题
    '二': const.QT_MULTIPLE_CHOICE,    # 二、多项选择题
    '三': const.QT_FILL_BLANK,         # 三、填空题
    '四': const.QT_SHORT_ANSWER,       # 四、简答题
    '五': const.QT_ESSAY,              # 五、作文题
    '六': const.QT_COMPUTATION,        # 六、计算题
}

SECTION_KEYWORDS = {
    '多项选择': const.QT_MULTIPLE_CHOICE,   # must come before '选择题'
    '多选题': const.QT_MULTIPLE_CHOICE,
    '单选题': const.QT_SINGLE_CHOICE,
    '选择题': const.QT_SINGLE_CHOICE,
    '填空题': const.QT_FILL_BLANK,
    '简答题': const.QT_SHORT_ANSWER,
    '解答题': const.QT_SHORT_ANSWER,
    '判断题': const.QT_TRUE_FALSE,
    '计算题': const.QT_COMPUTATION,
    '证明题': const.QT_PROOF,
    '作文': const.QT_ESSAY,
    '应用题': const.QT_SHORT_ANSWER,
}


def normalize_question_type(section_title: str, question_type: str) -> str:
    """Override AI-detected question type based on section title."""
    if not section_title:
        return question_type

    # Check Chinese numeral prefix (一、二、三...)
    for numeral, qt in SECTION_TYPE_MAP.items():
        if section_title.startswith(numeral):
            return qt

    # Check keywords in section title
    for keyword, qt in SECTION_KEYWORDS.items():
        if keyword in section_title:
            return qt

    return question_type


def separate_answer_fields(question: dict) -> dict:
    """Extract 【答案】【解析】from stem and populate answer/analysis fields."""
    stem = question.get('stem', '')

    # Extract 【答案】
    answer_match = re.search(r'【答案】(.*?)(?=【|$)', stem)
    if answer_match:
        question['answer'] = answer_match.group(1).strip()
        stem = stem[:answer_match.start()] + stem[answer_match.end():]

    # Extract 【解析】
    analysis_match = re.search(r'【解析】(.*?)(?=【|$)', stem)
    if analysis_match:
        question['analysis'] = analysis_match.group(1).strip()
        stem = stem[:analysis_match.start()] + stem[analysis_match.end():]

    # Extract 【解答】
    solution_match = re.search(r'【解答】(.*?)(?=【|$)', stem)
    if solution_match:
        question['solution'] = solution_match.group(1).strip()
        stem = stem[:solution_match.start()] + stem[solution_match.end():]

    question['stem'] = stem.strip()
    return question


def validate_images(question: dict, word_image_refs: list | None = None) -> bool:
    """Check if question references images but none were detected."""
    stem = question.get('stem', '')
    has_images = bool(question.get('images'))

    # Keywords that suggest an image should exist
    image_keywords = ['如图', '见图', '观察下图', '下图所示', '坐标系', '统计图']

    needs_image = any(kw in stem for kw in image_keywords)

    # Cross-reference with Word preprocessing: if Word says this question references images
    if word_image_refs:
        qno = question.get('question_no', '')
        for ref in word_image_refs:
            if ref.get('question_no') == qno:
                needs_image = True
                break

    if needs_image and not has_images:
        question['need_review_reason'] = (
            question.get('need_review_reason', '') + '题目提及图片但未检测到 '
        )
        return False

    return True


def supplement_images_from_word(questions: list, word_images: list, word_image_refs: list) -> list:
    """Attach Word-extracted images to questions that reference them but have none.

    Args:
        questions: List of question dicts.
        word_images: List of image dicts from WordPreprocessor.
        word_image_refs: List of {question_no, sort_order} from WordPreprocessor.

    Returns:
        Updated questions list with supplemented images.
    """
    if not word_images or not word_image_refs:
        return questions

    # Build mapping: question_no -> list of word image paths
    qno_images: dict[str, list] = {}
    for ref in word_image_refs:
        qno = ref.get('question_no', '')
        img_idx = ref.get('_image_index', 0)
        if img_idx < len(word_images):
            qno_images.setdefault(qno, []).append(word_images[img_idx])

    for q in questions:
        qno = q.get('question_no', '')
        if not q.get('images') and qno in qno_images:
            # Supplement missing images from Word extraction
            q['images'] = [
                {
                    'image_type': img.get('type', 'diagram'),
                    'file_path': img.get('rel_path', ''),
                    'description': f'Word文档提取图片 #{img.get("index", "")}',
                    'source': 'word_extracted',
                }
                for img in qno_images[qno]
            ]
            q['need_review_reason'] = (
                q.get('need_review_reason', '') + '[Word补图] '
            )

    return questions


def append_guxuan_to_solution(question: dict) -> dict:
    """Append '故选：{answer}' to solution if answer exists but solution doesn't end with it."""
    answer = question.get('answer', '').strip()
    solution = question.get('solution', '').strip()

    if not answer or not solution:
        return question

    # Check if solution already ends with answer-related content
    guxuan_patterns = ['故选', '故答案为', '因此答案为', '答案：' + answer, '答案: ' + answer]
    if any(solution.endswith(p) or solution.endswith(p + '。') or solution.endswith(p + '.') for p in guxuan_patterns):
        return question

    # Check if solution already contains the answer at the end
    if answer in solution[-20:]:
        return question

    # Append '故选：{answer}'
    question['solution'] = solution + '\n故选：' + answer
    return question


def postprocess_questions(page_results: list, word_preprocess_result: dict | None = None) -> list:
    """Full postprocessing pipeline.

    Args:
        page_results: List of page parse results from AI.
        word_preprocess_result: Optional dict from WordPreprocessor.run().

    Returns:
        Processed list of questions ready for DB save.
    """
    word_images = []
    word_image_refs = []
    word_question_numbers = []
    if word_preprocess_result:
        word_images = word_preprocess_result.get('images', [])
        word_image_refs = word_preprocess_result.get('image_refs', [])
        word_question_numbers = word_preprocess_result.get('question_numbers', [])

    # Step 1: Merge cross-page questions
    questions = merge_cross_page_questions(page_results)

    # Step 2: Normalize and clean up each question
    for q in questions:
        # Normalize question type based on section title
        section_title = q.get('section_title', '')
        q['question_type'] = normalize_question_type(section_title, q.get('question_type', 'unknown'))

        # Separate answer fields from stem
        separate_answer_fields(q)

        # Append '故选：{answer}' to solution if missing
        append_guxuan_to_solution(q)

        # Check for missing images (cross-reference with Word)
        validate_images(q, word_image_refs=word_image_refs)

        # Check formula validity
        combined_text = f"{q.get('stem', '')} {q.get('answer', '')} {q.get('analysis', '')}"
        q['formula_need_review'] = check_formula_need_review(combined_text)

        # Set need_review flag
        need_review = (
            q.get('need_review_reason', '') != '' or
            q.get('confidence', 1.0) < 0.7 or
            q.get('formula_need_review', False)
        )
        q['need_review'] = need_review

    # Step 3: Supplement missing images from Word extraction
    questions = supplement_images_from_word(questions, word_images, word_image_refs)

    # Fix duplicate/out-of-order question numbers
    questions = _fix_question_numbers(
        questions,
        word_preprocess_result.get('question_numbers', []) if word_preprocess_result else []
    )

    logger.info(f"Postprocessed {len(questions)} questions from {len(page_results)} pages")
    return questions
