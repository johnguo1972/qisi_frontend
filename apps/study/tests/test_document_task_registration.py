def test_standard_study_tasks_module_exports_document_import_task():
    """Celery autodiscovery loads the document-import task from the standard tasks module."""
    from apps.study.tasks import process_document_import_task

    assert process_document_import_task.name == (
        "apps.study.document_import_tasks.process_document_import_task"
    )
