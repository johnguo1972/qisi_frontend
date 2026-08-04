from pathlib import Path

import pytest
from django.urls import Resolver404, resolve

ROOT = Path(__file__).resolve().parents[1]
TASK_NAMES = (
    "apps.parser.tasks.parse_paper_task",
    "apps.parser.tasks.reparse_page_task",
    "apps.parser.tasks.reparse_question_task",
)


@pytest.mark.parametrize("url", [
    "/api/v1/papers/00000000-0000-0000-0000-000000000001/parse/",
    "/api/v1/papers/00000000-0000-0000-0000-000000000001/stop-parse/",
    "/api/v1/papers/00000000-0000-0000-0000-000000000001/reparse/",
    "/api/v1/papers/00000000-0000-0000-0000-000000000001/progress/",
    "/api/v1/questions/import-batches",
])
def test_removed_paper_parsing_urls_do_not_resolve(url):
    with pytest.raises(Resolver404):
        resolve(url)


@pytest.mark.parametrize(("url", "url_name"), [
    (
        "/api/v1/papers/00000000-0000-0000-0000-000000000001/",
        "delete-paper",
    ),
    ("/api/v1/questions/import-json-package", "import-json-package"),
])
def test_retained_paper_data_urls_still_resolve(url, url_name):
    assert resolve(url).url_name == url_name


@pytest.mark.parametrize("url", [
    "/upload-modal/",
    "/papers/upload/",
    "/papers/00000000-0000-0000-0000-000000000001/progress/",
    "/papers/00000000-0000-0000-0000-000000000001/reparse-htmx/",
    "/review/question/00000000-0000-0000-0000-000000000001/reparse-htmx/",
    "/review/question/00000000-0000-0000-0000-000000000001/reparse-progress/",
])
def test_removed_htmx_parsing_urls_do_not_resolve(url):
    with pytest.raises(Resolver404):
        resolve(url, urlconf="apps.review.htmx_urls")


def test_retained_htmx_paper_detail_still_resolves():
    match = resolve(
        "/papers/00000000-0000-0000-0000-000000000001/",
        urlconf="apps.review.htmx_urls",
    )
    assert match.url_name == "paper-detail-htmx"


def test_removed_tasks_and_beat_are_absent_from_production_sources():
    sources = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "apps").rglob("*.py")
        if "tests" not in path.parts and path.name != "models.py"
    )
    for task_name in TASK_NAMES:
        assert task_name not in sources
        assert task_name.rsplit(".", 1)[-1] not in sources
    settings_source = (ROOT / "config/settings.py").read_text(encoding="utf-8")
    assert "periodic_stale_task_check" not in settings_source


def test_teacher_import_page_is_removed():
    assert not (ROOT / "uniapp/src/pages/teacher/import.vue").exists()


def test_teacher_parsing_api_helpers_are_removed():
    api_source = (ROOT / "uniapp/src/api/questions.ts").read_text(encoding="utf-8")
    for name in (
        "importFile",
        "importBatches",
        "importBatchDetail",
        "stopParse",
        "reparsePaper",
        "getParseProgress",
        "deletePaper",
    ):
        assert name not in api_source


@pytest.mark.parametrize(
    "relative_path",
    (
        "uniapp/src/pages.json",
        "uniapp/src/components/TeacherSidebar.vue",
        "uniapp/src/components/AddMenuModal.vue",
    ),
)
def test_teacher_navigation_has_no_paper_import_route(relative_path):
    source = (ROOT / relative_path).read_text(encoding="utf-8")
    assert "pages/teacher/import" not in source
