"""Presentation helpers for imported questions."""
from __future__ import annotations

from copy import deepcopy


DIFFICULTY_LABELS = {
    1: "基础巩固",
    2: "较易",
    3: "中等",
    4: "较难",
    5: "困难",
}


def difficulty_label(value) -> str:
    """Return a Chinese difficulty label; unset values are not shown as L."""
    if value is None or value == "":
        return "未评定"
    try:
        number = int(float(value))
    except (TypeError, ValueError, OverflowError):
        return "未评定"
    return DIFFICULTY_LABELS.get(number, "未评定")


def normalize_tables(tables) -> list:
    """Normalize extracted table cells without changing the stored JSON."""
    if not isinstance(tables, list):
        return []
    result = deepcopy(tables)
    for table in result:
        if not isinstance(table, dict):
            continue
        rows = table.get("rows")
        if not isinstance(rows, list):
            continue
        normalized_rows = []
        for row in rows:
            if not isinstance(row, list):
                normalized_rows.append(row)
                continue
            cells = ["" if cell is None else str(cell) for cell in row]
            # The source extractor repeats the first merged header cell in the
            # next column. Keep the grid width but clear the duplicate.
            if len(cells) >= 2 and cells[0].strip() and cells[0].strip() == cells[1].strip():
                cells[1] = ""
            normalized_rows.append(cells)

        # Word/table extraction can leave visual spacer rows as arrays of
        # empty cells. They are not question data and only create large blank
        # bands in the course-practice preview. Remove them for presentation;
        # the original JSON stored on ExamQuestion is left unchanged.
        normalized_rows = [
            row for row in normalized_rows
            if not isinstance(row, list) or any(str(cell).strip() for cell in row)
        ]

        # Extracted tables may contain one or more trailing empty cells for a
        # merged cell or an incomplete row. Those cells create a misleading
        # vertical divider in the practice-list preview. Remove only columns
        # that are empty for every row; meaningful internal empty cells remain
        # untouched so the source table alignment is preserved.
        width = max((len(row) for row in normalized_rows if isinstance(row, list)), default=0)
        while width > 1 and all(
            not (isinstance(row, list) and len(row) >= width and str(row[width - 1]).strip())
            for row in normalized_rows
        ):
            normalized_rows = [row[: width - 1] if isinstance(row, list) else row for row in normalized_rows]
            width -= 1
        table["rows"] = normalized_rows
    return result


def _table_cells(tables) -> list[str]:
    cells = []
    for table in tables or []:
        if not isinstance(table, dict):
            continue
        for row in table.get("rows") or []:
            if not isinstance(row, list):
                continue
            for cell in row:
                value = str(cell or "").strip()
                if value:
                    cells.append(value)
    return cells


def display_stem(stem, subquestions=None, tables=None) -> str:
    """Return a readable stem, falling back to child questions when needed."""
    text = str(stem or "").strip()
    table_cells = _table_cells(tables)

    # Some extracted records append a flattened table to the stem. Remove the
    # recognizable table suffix from the preview; raw_text remains untouched.
    if text and table_cells:
        for cell in table_cells:
            if len(cell) < 4:
                continue
            index = text.find(cell)
            if index > 24:
                text = text[:index].rstrip()
                break
    if text:
        return text

    parts = []
    for item in subquestions or []:
        if not isinstance(item, dict):
            continue
        child_stem = str(item.get("stem") or "").strip()
        if child_stem:
            parts.append(f"{str(item.get('label') or '').strip()} {child_stem}".strip())
    if parts:
        return "\n".join(parts)
    return "\n".join(table_cells)


def preview_text(stem, subquestions=None, tables=None, limit: int = 240) -> str:
    text = display_stem(stem, subquestions, tables)
    return text if len(text) <= limit else text[:limit].rstrip() + "..."
