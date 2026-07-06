"""LaTeX formula validation and repair."""
import logging
import re

logger = logging.getLogger(__name__)

# LaTeX inline math delimiters
LATEX_INLINE_PATTERN = re.compile(r'(?<!\$)\$(?!\$)(.+?)(?<!\$)\$(?!\$)')
LATEX_DISPLAY_PATTERN = re.compile(r'\$\$(.+?)\$\$', re.DOTALL)

# Common LaTeX commands
LATEX_COMMANDS = {
    'frac', 'sqrt', 'sum', 'prod', 'int', 'lim', 'sin', 'cos', 'tan',
    'log', 'ln', 'exp', 'pm', 'cdot', 'times', 'div', 'in', 'notin',
    'subset', 'supset', 'cup', 'cap', 'forall', 'exists', 'nabla',
    'partial', 'infty', 'alpha', 'beta', 'gamma', 'delta', 'epsilon',
    'theta', 'lambda', 'mu', 'pi', 'sigma', 'phi', 'omega',
}


def validate_latex(text: str) -> tuple[bool, list[str]]:
    """Check if LaTeX formulas in text are well-formed.

    Returns:
        (is_valid, list_of_errors)
    """
    errors = []

    # Check balanced $...$
    dollar_count = text.count('$')
    if dollar_count % 2 != 0:
        errors.append(f"Unbalanced inline math delimiters ($): found {dollar_count}")

    # Check balanced $$...$$
    display_count = len(LATEX_DISPLAY_PATTERN.findall(text))
    display_opens = text.count('$$')
    if display_opens % 2 != 0:
        errors.append("Unbalanced display math delimiters ($$)")

    # Check balanced braces in math mode
    for match in LATEX_INLINE_PATTERN.finditer(text):
        content = match.group(1)
        if content.count('{') != content.count('}'):
            errors.append(f"Unbalanced braces in formula: {content[:50]}...")

    if not errors:
        return True, []

    return False, errors


def check_formula_need_review(text: str) -> bool:
    """Check if text contains potentially problematic formulas."""
    if not text:
        return False

    is_valid, errors = validate_latex(text)
    if not is_valid:
        return True

    # Check for very long formulas (might be parsing errors)
    for match in LATEX_INLINE_PATTERN.finditer(text):
        if len(match.group(1)) > 500:
            return True

    for match in LATEX_DISPLAY_PATTERN.finditer(text):
        if len(match.group(1)) > 500:
            return True

    return False
