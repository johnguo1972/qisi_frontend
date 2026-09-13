# Course PDF DOCX Import Implementation Plan

> For agentic workers: REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking.

Goal: Allow a course teacher to upload a PDF or DOCX paper, asynchronously structure it with Qwen, import or deduplicate questions, and immediately link resolved questions to the selected course node.

Architecture: Add a course-scoped document upload API and a document.import Celery task. The worker extracts per-question document fragments, structures each through Qwen, then delegates paper creation, media persistence, content fingerprints and course links to a shared ingestion service also used by JSON import.

Tech Stack: Django REST Framework, PostgreSQL, Celery/Redis, PyMuPDF, python-docx, existing Qwen client, Vue 3/UniApp, Vitest, pytest.

Spec: docs/superpowers/specs/2026-09-13-course-pdf-docx-import-design.md

## Global Constraints

- Accept PDF and DOCX only; reject legacy DOC.
- Reject a file larger than 100 MB or more than 100 pages before dispatch. For DOCX, compute equivalent pages as ceiling(non-whitespace characters / 1600) plus ceiling(table count / 2) plus image count; it is a processing limit, not print pagination.
- Require course context and validate optional course tree node; never use a question-bank-only fallback.
- Do not recreate duplicate questions, but do create the requested course link.
- Use qwen3.7-plus as final structural model and return only redacted diagnostics.
- Route heavy work to document.import; production concurrency is one or two.

---

## File Structure

- Create apps/study/document_import_models.py: persistent task state.
- Create apps/study/document_import_service.py: MIME checks, PDF/DOCX extraction and candidate slicing.
- Create apps/study/structured_ingestion.py: shared normalized ingestion.
- Create apps/study/document_structure_ai.py: strict Qwen adapter.
- Create apps/study/document_import_tasks.py: Celery orchestration.
- Create apps/study/document_import_views.py: upload/status handlers.
- Modify apps/study/models.py, apps/study/json_import_views.py, apps/courses/views.py, apps/courses/urls.py, config/settings.py, the Python dependency manifest, uniapp/src/api/questions.ts, uniapp/src/pages/teacher/course-practice.vue, and uniapp/src/components/QuestionIngestionHistoryModal.vue.

### Task 1: Persistent state and safe document extraction

Files:
- Modify: apps/study/models.py, QuestionIngestionBatch.SourceType
- Create: apps/study/document_import_models.py
- Create: apps/study/migrations/0008_questiondocumentimporttask.py
- Create: apps/study/document_import_service.py
- Test: apps/study/tests/test_document_import_models.py
- Test: apps/study/tests/test_document_import_service.py

Interfaces:
- QuestionDocumentImportTask has one-to-one batch, course, source path/type/MIME/page count, stage, progress, Celery ID, linked count and bounded error summary.
- Stages are queued, extracting, structuring, importing, success, partial_success, failed.
- validate_document_upload(uploaded_file) returns ValidatedDocument.
- extract_document(source_path) returns ExtractedDocument; each fragment has question number, text, tables, page range and asset references.

- [ ] Step 1: Write failing model, validation and extraction tests

    def test_document_task_starts_queued(teacher, course):
        batch = QuestionIngestionBatch.objects.create(
            actor=teacher, course=course, source_type='document_import', source_name='paper.pdf'
        )
        task = QuestionDocumentImportTask.objects.create(
            batch=batch, course=course, source_file='imports/paper.pdf',
            detected_mime='application/pdf', document_type='pdf', page_count=2,
        )
        assert task.stage == 'queued'

    def test_validate_document_rejects_docx_named_pdf():
        upload = make_upload('fake.docx', b'%PDF-1.7', 'application/pdf')
        with pytest.raises(DocumentValidationError, match='文件内容与扩展名不一致'):
            validate_document_upload(upload)

    def test_extract_pdf_slices_questions_and_binds_assets(pdf_fixture):
        document = extract_document(pdf_fixture)
        assert [item.question_no for item in document.fragments] == ['1', '2']
        assert document.fragments[0].asset_refs

- [ ] Step 2: Run tests to verify failure

Run: python -m pytest apps/study/tests/test_document_import_models.py apps/study/tests/test_document_import_service.py -q
Expected: FAIL because models and extractor do not exist.

- [ ] Step 3: Implement the minimum data and extraction layer

    ALLOWED_DOCUMENT_TYPES = {'.pdf': 'application/pdf', '.docx': DOCX_MIME}
    MAX_DOCUMENT_BYTES = 100 * 1024 * 1024
    MAX_DOCUMENT_PAGES = 100

    def extract_document(path: Path) -> ExtractedDocument:
        return extract_pdf_document(path) if path.suffix.lower() == '.pdf' else extract_docx_document(path)

Add document_import to source types and create the model/migration. Use PyMuPDF blocks, images and coordinates for PDFs; reject PDFs above 100 pages. Use python-docx paragraphs, tables and relationship images for DOCX; reject a DOCX when ceiling(non-whitespace characters / 1600) plus ceiling(table count / 2) plus image count exceeds 100. Slice on numbered markers, attach nearby assets, and reject an empty document before AI calls.

- [ ] Step 4: Run verification

Run: python -m pytest apps/study/tests/test_document_import_models.py apps/study/tests/test_document_import_service.py -q
Expected: PASS for invalid extension/signature, size, 101-page PDF, table and image cases.

Run: python manage.py makemigrations --check
Expected: No changes detected.

- [ ] Step 5: Commit

    git add apps/study/models.py apps/study/document_import_models.py apps/study/migrations/0008_questiondocumentimporttask.py apps/study/document_import_service.py apps/study/tests/test_document_import_models.py apps/study/tests/test_document_import_service.py
    git commit -m "feat: add document import extraction"

### Task 2: Shared ingestion and Qwen Celery pipeline

Files:
- Create: apps/study/structured_ingestion.py
- Modify: apps/study/json_import_views.py, functions _process_json_import, _import_single_question and _link_questions_to_course
- Create: apps/study/document_structure_ai.py
- Create: apps/study/document_import_tasks.py
- Modify: config/settings.py, CELERY_TASK_ROUTES
- Test: apps/study/tests/test_structured_ingestion.py
- Test: apps/study/tests/test_document_structure_ai.py
- Test: apps/study/tests/test_document_import_tasks.py

Interfaces:
- ingest_structured_questions takes questions, paper_info, actor, batch, source_root, course, tree_node and returns IngestionResult.
- IngestionResult contains all counters, linked_count, tree_node_id and bounded redacted errors.
- structure_candidate(candidate, model='qwen3.7-plus') returns StructuredQuestion.
- process_document_import_task(task_id) is routed to document.import.

- [ ] Step 1: Write failing shared-ingestion and worker tests

    def test_existing_question_is_linked_without_recreation(teacher, course, existing_question, structured_question):
        result = ingest_structured_questions(
            questions=[structured_question], paper_info={'title': 'paper'}, actor=teacher,
            batch=make_batch(teacher, course), source_root=None, course=course, tree_node=None,
        )
        assert result.imported == 0
        assert result.skipped_existing == 1
        assert CourseQuestionLink.objects.filter(course=course, question=existing_question).exists()

    def test_task_marks_partial_success_after_one_candidate_failure(task, monkeypatch):
        monkeypatch.setattr(module, 'structure_candidate', side_effect=[valid_question(), AIResponseError('bad json')])
        process_document_import_task.run(str(task.id))
        task.refresh_from_db()
        assert task.stage == 'partial_success'

- [ ] Step 2: Run tests to verify failure

Run: python -m pytest apps/study/tests/test_structured_ingestion.py apps/study/tests/test_document_structure_ai.py apps/study/tests/test_document_import_tasks.py -q
Expected: FAIL because the service, adapter and task do not exist.

- [ ] Step 3: Implement shared ingestion and strict AI task

Move JSON preflight normalization, paper creation/reuse, fingerprint reservation/activation, question/options/media creation, counters and course linking to structured_ingestion.py. Keep ZIP layout reading and JSON response envelopes in json_import_views.py.

Prompt one candidate at a time for fields question_no, question_type, stem, options, answer, analysis, tables, illustrations, confidence and review_reason. Strip Markdown fences, validate JSON/schema/assets, retry timeout/non-JSON/asset-read once, record a redacted failure on second error, and continue remaining candidates. Update persisted stage/progress and ingest only valid candidates.

    @shared_task(bind=True, max_retries=0)
    def process_document_import_task(self, task_id: str) -> None:
        task = QuestionDocumentImportTask.objects.select_related('batch', 'course').get(pk=task_id)
        # extracting, structuring, importing, then terminal state

Set the task route to queue document.import.

- [ ] Step 4: Run regression verification

Run: python -m pytest apps/study/tests/test_json_import_dedup.py apps/study/tests/test_json_formula_assets.py apps/study/tests/test_structured_ingestion.py apps/study/tests/test_document_structure_ai.py apps/study/tests/test_document_import_tasks.py -q
Expected: PASS, including existing JSON behavior and duplicate-to-course links.

- [ ] Step 5: Commit

    git add apps/study/structured_ingestion.py apps/study/json_import_views.py apps/study/document_structure_ai.py apps/study/document_import_tasks.py config/settings.py apps/study/tests
    git commit -m "feat: process document imports asynchronously"

### Task 3: Course APIs, UniApp tab and end-to-end verification

Files:
- Create: apps/study/document_import_views.py
- Modify: apps/courses/views.py
- Modify: apps/courses/urls.py
- Modify: uniapp/src/api/questions.ts
- Modify: uniapp/src/pages/teacher/course-practice.vue
- Modify: uniapp/src/components/QuestionIngestionHistoryModal.vue
- Test: apps/courses/tests/test_course_document_import.py
- Test: uniapp/src/api/questions.spec.ts
- Test: uniapp/src/pages/teacher/course-practice.spec.ts
- Test: apps/study/tests/test_document_import_integration.py

Interfaces:
- POST /api/v1/courses/{course_id}/questions/import-document/ returns HTTP 202 with task_id, batch_id, course_id, tree_node_id, stage.
- GET /api/v1/courses/{course_id}/questions/import-document/{task_id}/status/ returns persisted stage/progress/counters/redacted errors.
- importCourseDocument(file, options) and getCourseDocumentImportStatus(courseId, taskId).
- Course practice adds activeTab equal to document.

- [ ] Step 1: Write failing API, UI and integration tests

    def test_upload_creates_task_and_dispatches(teacher_client, course, pdf_upload, monkeypatch):
        delay = monkeypatch.spy(process_document_import_task, 'delay')
        response = teacher_client.post(
            '/api/v1/courses/{}/questions/import-document/'.format(course.id),
            {'file': pdf_upload},
        )
        assert response.status_code == 202
        assert response.data['data']['course_id'] == str(course.id)
        assert delay.call_count == 1

    def test_status_is_not_visible_from_another_course(teacher_client, other_course, task):
        response = teacher_client.get(
            '/api/v1/courses/{}/questions/import-document/{}/status/'.format(other_course.id, task.id)
        )
        assert response.status_code == 404

    it('posts to the course document endpoint', async () => {
      await importCourseDocument(new File(['%PDF'], 'paper.pdf'), { courseId: 'course-1' })
      expect(fetch).toHaveBeenCalledWith(
        expect.stringContaining('/courses/course-1/questions/import-document/'),
        expect.objectContaining({ method: 'POST' }),
      )
    })

- [ ] Step 2: Run tests to verify failure

Run: python -m pytest apps/courses/tests/test_course_document_import.py apps/study/tests/test_document_import_integration.py -q
Expected: FAIL with route not found.

Run: npm run test -- --run uniapp/src/api/questions.spec.ts uniapp/src/pages/teacher/course-practice.spec.ts
Expected: FAIL because document Tab/client do not exist.

- [ ] Step 3: Implement backend API

Reuse _get_course_or_404 and _check_course_owner; validate node belongs to course. Save a UUID-named source path in controlled media storage, atomically create batch/task, dispatch after transaction commit, and return HTTP 202. Read status only from persistent task state, not Celery result backend.

- [ ] Step 4: Implement client and UI

Add third real Tab named PDF-Word文档导入; picker extensions are pdf and docx; render exact 100 MB/100-page copy. Poll every three seconds while non-terminal, retain task state after panel close, clean timers on unmount, and refresh tree/questions after success or partial success. Add document_import label, stage copy and bounded errors to history.

- [ ] Step 5: Run complete verification

Run: python manage.py makemigrations --check
Expected: No changes detected.

Run: python -m pytest apps/courses/tests/test_course_document_import.py apps/courses/tests/test_course_question_list.py apps/study/tests/test_document_import_integration.py -q
Expected: PASS.

Run: npm run test -- --run uniapp/src/api/questions.spec.ts uniapp/src/pages/teacher/course-practice.spec.ts uniapp/src/components/QuestionIngestionHistoryModal.spec.ts
Expected: PASS.

Run: npm run build
Expected: successful production build from uniapp.

- [ ] Step 6: Add dependencies, smoke test, commit

Pin PyMuPDF and python-docx in the actual backend dependency manifest; document a worker consuming document.import at concurrency one or two without removing ai.batch or ai.guidance.

On staging, upload a PDF with options, formula, table, illustration and cross-page question, and a DOCX with table/image. Verify terminal state, course visibility, duplicate linking, controlled image access and history counters.

    git add apps/courses apps/study uniapp/src config requirements*.txt docs
    git commit -m "feat: add course PDF DOCX import"

## Plan Self-Review

- Tasks 1 to 3 cover formats/limits, auto import, course association, deduplication, asynchronous stages, Qwen structured output, UI/history, permissions, diagnostics, dependencies and end-to-end verification.
- All later interfaces are defined by earlier tasks: QuestionDocumentImportTask, ingest_structured_questions, process_document_import_task, importCourseDocument, task_id, batch_id and document.import.
- The plan excludes legacy DOC, independent FastAPI infrastructure, confirmation-before-import, variant generation and changes to existing AI probing.
