"""Common utilities."""
import json
import re
import uuid
import os


def generate_task_id() -> str:
    """Generate a unique task ID."""
    return str(uuid.uuid4())


def repair_json_string(raw: str) -> str:
    """Repair common JSON issues from AI responses."""
    text = raw.strip()

    # Remove markdown code block wrappers
    text = re.sub(r'^```(?:json)?\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'\s*```$', '', text, flags=re.MULTILINE)
    text = text.strip()

    # Extract JSON object
    first_brace = text.find('{')
    last_brace = text.rfind('}')
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        text = text[first_brace:last_brace + 1]

    # Fix invalid/ambiguous backslash escapes inside JSON string values.
    # Valid JSON escapes: \\, \", \/, \b, \f, \n, \r, \t, \uXXXX
    # But LaTeX uses \f in \frac, \b in \beta, \n in \notin, etc.
    # These are ambiguous. Detect LaTeX patterns and double the backslash.
    # LaTeX patterns: \word (e.g. \frac, \cdot, \sqrt, \alpha, etc.)
    # We detect \ followed by a letter (a-z, A-Z) that is NOT one of b, f, n, r, t
    # OR is one of those but followed by a letter (like \frac -> f+r+a+c, not just \f).

    valid_escapes = set('"/\\')

    def fix_string_value(match):
        s = match.group(0)  # e.g. '"formula \frac{1}{3}"'
        fixed = []
        i = 0
        while i < len(s):
            ch = s[i]
            if ch == '\\' and i + 1 < len(s):
                nc = s[i + 1]
                # Standard valid JSON escapes
                if nc in valid_escapes:
                    fixed.append(ch)
                    i += 1
                    continue
                # \uXXXX
                if nc == 'u' and i + 5 < len(s):
                    fixed.append(ch)
                    i += 1
                    continue
                # \b, \f, \n, \r, \t - valid JSON escapes BUT could be LaTeX prefix
                # If \X followed by 2+ more letters (total 3+) it's LaTeX like \frac
                # If \X followed by 0-1 more letters, it's a real JSON escape
                if nc in 'bfnrt':
                    extra_letters = 0
                    j = i + 2
                    while j < len(s) and s[j].isalpha():
                        extra_letters += 1
                        j += 1
                    if extra_letters >= 2:
                        # LaTeX: \f+r+a+c → double the backslash
                        fixed.append('\\\\')
                        i += 1
                        continue
                    # Real JSON escape: \n, \t, etc. → keep single
                    fixed.append(ch)
                    i += 1
                    continue
                # Any other \X is invalid → double it
                fixed.append('\\\\')
                i += 1
                continue
            elif ch == '“' or ch == '”':
                fixed.append('\\"')
            elif ch == '‘':
                fixed.append("'")
            elif ch == '’':
                fixed.append("'")
            else:
                fixed.append(ch)
            i += 1
        return ''.join(fixed)

    text = re.sub(r'"(?:[^"\\]|\\.)*"', fix_string_value, text)

    # Remove trailing commas before } or ]
    text = re.sub(r',\s*([}\]])', r'\1', text)

    # Fix missing commas between key-value pairs
    text = re.sub(r'(")\s*\n\s*(")', r'\1,\n\2', text)

    return text


def expand_bbox(bbox, page_width, page_height, padding=10):
    """Expand a bbox by padding pixels, clamping to page boundaries."""
    if not bbox or len(bbox) != 4:
        return bbox
    x1, y1, x2, y2 = bbox
    return [
        max(0, x1 - padding),
        max(0, y1 - padding),
        min(page_width, x2 + padding),
        min(page_height, y2 + padding),
    ]
