"""Small dependency-free XLSX reader shared by teacher import flows."""
from __future__ import annotations

import posixpath
import zipfile
from dataclasses import dataclass
from xml.etree import ElementTree


MAIN_NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
REL_NS = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
PKG_REL_NS = 'http://schemas.openxmlformats.org/package/2006/relationships'
NS = {'x': MAIN_NS, 'r': REL_NS, 'pr': PKG_REL_NS}


@dataclass(frozen=True)
class XlsxSheet:
    title: str
    rows: list[list[str]]


def _column_number(reference: str) -> int:
    number = 0
    for char in reference:
        if char.isalpha():
            number = number * 26 + ord(char.upper()) - 64
    return number


def _shared_strings(archive: zipfile.ZipFile) -> list[str]:
    path = 'xl/sharedStrings.xml'
    if path not in archive.namelist():
        return []
    root = ElementTree.fromstring(archive.read(path))
    return [
        ''.join(node.text or '' for node in item.iter(f'{{{MAIN_NS}}}t'))
        for item in root.findall('.//x:si', NS)
    ]


def _cell_value(cell, shared: list[str]) -> str:
    cell_type = cell.attrib.get('t', '')
    if cell_type == 'inlineStr':
        return ''.join(node.text or '' for node in cell.iter(f'{{{MAIN_NS}}}t'))
    value = cell.find('x:v', NS)
    raw = value.text if value is not None else ''
    if cell_type == 's' and raw != '':
        try:
            return shared[int(raw)]
        except (IndexError, ValueError):
            return ''
    if cell_type == 'b':
        return 'TRUE' if raw == '1' else 'FALSE'
    return raw or ''


def _read_sheet(archive: zipfile.ZipFile, path: str, shared: list[str]) -> list[list[str]]:
    root = ElementTree.fromstring(archive.read(path))
    rows: list[list[str]] = []
    for row in root.findall('.//x:sheetData/x:row', NS):
        values: dict[int, str] = {}
        for cell in row.findall('x:c', NS):
            reference = cell.attrib.get('r', '')
            column = _column_number(reference)
            if column:
                values[column] = _cell_value(cell, shared)
        if values:
            rows.append([values.get(index, '') for index in range(1, max(values) + 1)])
        else:
            rows.append([])
    return rows


def read_xlsx_sheets(upload) -> list[XlsxSheet]:
    """Read all worksheets in workbook order without requiring openpyxl."""
    upload.seek(0)
    with zipfile.ZipFile(upload) as archive:
        names = set(archive.namelist())
        workbook = ElementTree.fromstring(archive.read('xl/workbook.xml'))
        relationships = {}
        rel_path = 'xl/_rels/workbook.xml.rels'
        if rel_path in names:
            rel_root = ElementTree.fromstring(archive.read(rel_path))
            for rel in rel_root.findall('pr:Relationship', NS):
                relationships[rel.attrib.get('Id')] = rel.attrib.get('Target', '')

        shared = _shared_strings(archive)
        sheets: list[XlsxSheet] = []
        for sheet in workbook.findall('.//x:sheets/x:sheet', NS):
            title = sheet.attrib.get('name', '')
            relation_id = sheet.attrib.get(f'{{{REL_NS}}}id', '')
            target = relationships.get(relation_id, '')
            if target.startswith('/'):
                path = target.lstrip('/')
            else:
                path = posixpath.normpath(posixpath.join('xl', target))
            if path not in names:
                raise ValueError(f'工作表文件不存在: {title}')
            sheets.append(XlsxSheet(title=title, rows=_read_sheet(archive, path, shared)))
        if not sheets:
            raise ValueError('XLSX 文件没有工作表')
        return sheets
