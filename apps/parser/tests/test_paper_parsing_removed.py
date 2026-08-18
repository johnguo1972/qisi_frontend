from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_paper_parsing_celery_module_and_dispatch_references_are_removed():
    task_module = ROOT / "apps/parser/tasks.py"
    assert task_module.exists()
    task_source = task_module.read_text(encoding="utf-8")

    for relative_path in (
        "apps/parser/tasks.py",
        "apps/papers/views.py",
        "apps/study/import_views.py",
        "apps/review/htmx_urls.py",
        "config/settings.py",
    ):
        source = task_source if relative_path == "apps/parser/tasks.py" else (ROOT / relative_path).read_text(encoding="utf-8")
        assert "parse_paper_task" not in source
        assert "reparse_question_task" not in source
        assert "reparse_page_task" not in source
        assert "periodic_stale_task_check" not in source
