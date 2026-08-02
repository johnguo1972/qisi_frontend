from __future__ import annotations

import logging
import traceback
from types import SimpleNamespace

import pytest

from apps.common import status as const
from apps.common.exceptions import AIRequestError
from apps.papers.models import ExamPaper, ParseTask
from apps.parser.models import AIParseResult, ExamPage, ExamQuestion
from apps.parser.services import position_service, question_parse_service
from apps.parser import tasks as parser_tasks
from apps.study import photo_views


SENSITIVE_VALUES = (
    "https://bucket.example.test/private.png?OSSAccessKeyId=private-key&Signature=private-signature",
    r"C:\Users\private\exam.png",
    "/srv/private/exam.png",
    "data:image/png;base64,PRIVATE_BASE64_MARKER",
    "RAW_BYTES_MARKER",
)
UNSAFE_DETAIL = " | ".join(SENSITIVE_VALUES) + " | b'RAW_BYTES_MARKER'"


class UnsafeComponent:
    def detect_positions(self, _image_path):
        raise AIRequestError(UNSAFE_DETAIL)

    def parse_question(self, _images, _context):
        raise AIRequestError(UNSAFE_DETAIL)

    def recognize_photo(self, _images):
        raise AIRequestError(UNSAFE_DETAIL)


class RecordingQuestionComponent:
    def __init__(self):
        self.calls = []

    def parse_question(self, images, context):
        self.calls.append((tuple(images), dict(context)))
        content = '{"question_no":"8","stem":"题干"}'
        return {
            "raw_response": content,
            "response_json": content,
            "latency_ms": 1,
            "parsed": {"question_no": "8", "stem": "题干"},
        }


def _assert_no_sensitive(value) -> None:
    rendered = str(value)
    for sensitive in SENSITIVE_VALUES:
        assert sensitive not in rendered


def _assert_safe_records(records) -> None:
    for record in records:
        assert record.exc_info is None
        _assert_no_sensitive(record.getMessage())
        _assert_no_sensitive(record.args)
        _assert_no_sensitive(record.__dict__)


def _format_captured_locals(error: BaseException) -> str:
    return "".join(
        traceback.TracebackException(
            type(error),
            error,
            error.__traceback__,
            capture_locals=True,
        ).format()
    )


def test_position_failure_has_fixed_detail_and_safe_logger_records(
    monkeypatch, caplog
):
    monkeypatch.setattr(
        position_service,
        "vision_parser_component_factory",
        lambda: UnsafeComponent(),
    )
    caplog.set_level(logging.DEBUG)

    result = position_service.detect_positions(
        [{"page_no": 7, "path": SENSITIVE_VALUES[1]}]
    )

    assert result == [
        {
            "page_no": 7,
            "questions": [],
            "raw_response": "",
            "response_json": "",
            "error": "POSITION_DETECTION_FAILED: 题目位置检测失败",
            "latency_ms": 0,
        }
    ]
    _assert_no_sensitive(result)
    _assert_safe_records(caplog.records)


def test_position_component_factory_failure_is_also_fixed_and_safe(
    monkeypatch, caplog
):
    monkeypatch.setattr(
        position_service,
        "vision_parser_component_factory",
        lambda: (_ for _ in ()).throw(AIRequestError(UNSAFE_DETAIL)),
    )
    caplog.set_level(logging.DEBUG)

    result = position_service.detect_positions(
        [{"page_no": 7, "path": SENSITIVE_VALUES[1]}]
    )

    assert result[0]["error"] == (
        "POSITION_DETECTION_FAILED: 题目位置检测失败"
    )
    _assert_no_sensitive(result)
    _assert_safe_records(caplog.records)


def test_position_service_closes_created_component_after_failure(monkeypatch):
    class Component:
        def __init__(self):
            self.close_calls = 0

        def detect_positions(self, _image_path):
            raise AIRequestError("provider failed")

        def close(self):
            self.close_calls += 1

    component = Component()
    monkeypatch.setattr(
        position_service,
        "vision_parser_component_factory",
        lambda: component,
    )

    position_service.detect_positions([{"page_no": 1, "path": "page.png"}])

    assert component.close_calls == 1


def test_question_parse_service_context_closes_owned_but_not_borrowed_component(
    monkeypatch,
):
    class Component:
        def __init__(self):
            self.close_calls = 0

        def close(self):
            self.close_calls += 1

    owned = Component()
    monkeypatch.setattr(
        question_parse_service,
        "VisionParserComponent",
        lambda: owned,
    )

    with question_parse_service.QuestionParseService() as service:
        assert service is not None
    service.close()
    assert owned.close_calls == 1

    borrowed = Component()
    with question_parse_service.QuestionParseService(borrowed):
        pass
    assert borrowed.close_calls == 0


def test_question_adapter_raises_chainless_safe_error_and_clears_locals():
    service = question_parse_service.QuestionParseService(UnsafeComponent())

    with pytest.raises(
        AIRequestError,
        match=r"^QUESTION_PARSE_FAILED: 题目解析失败$",
    ) as caught:
        service.parse_question(
            {"question_no": "8", "section_title": SENSITIVE_VALUES[2]},
            list(SENSITIVE_VALUES),
            [8],
        )

    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None
    _assert_no_sensitive(caught.value)
    _assert_no_sensitive(_format_captured_locals(caught.value))


@pytest.mark.parametrize(
    ("page_images", "page_numbers", "is_multi_page"),
    [
        (["page-2.png"], [2], False),
        (["page-2.png", "page-3.png"], [2, 3], True),
    ],
)
def test_question_adapter_passes_only_page_data_for_single_and_multi_page(
    page_images, page_numbers, is_multi_page
):
    component = RecordingQuestionComponent()
    service = question_parse_service.QuestionParseService(component)

    result = service.parse_question(
        {
            "question_no": "8",
            "question_type": "single_choice",
            "section_title": "一、选择题",
            "page_start": 2,
            "page_end": page_numbers[-1],
        },
        page_images,
        page_numbers,
    )

    assert result["parsed"]["page_no"] == 2
    assert result["parsed"]["page_end"] == page_numbers[-1]
    assert component.calls == [
        (
            tuple(page_images),
            {
                "question_no": "8",
                "question_type": "single_choice",
                "question_type_label": "单选题",
                "section_title": "一、选择题",
                "page_start": 2,
                "page_end": page_numbers[-1],
                "page_numbers": page_numbers,
                "is_multi_page": is_multi_page,
            },
        )
    ]


def test_question_component_factory_failure_is_chainless_and_safe(
    monkeypatch,
):
    monkeypatch.setattr(
        question_parse_service,
        "VisionParserComponent",
        lambda: (_ for _ in ()).throw(AIRequestError(UNSAFE_DETAIL)),
    )

    with pytest.raises(
        AIRequestError,
        match=r"^QUESTION_PARSE_FAILED: 题目解析失败$",
    ) as caught:
        question_parse_service.QuestionParseService()

    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None
    _assert_no_sensitive(_format_captured_locals(caught.value))


def test_question_stage2_logs_only_fixed_failure_and_returns_no_raw_detail(
    monkeypatch, tmp_path, caplog
):
    private_page = tmp_path / "stage2-private-page.png"
    private_page.write_bytes(b"not inspected")
    original_service = question_parse_service.QuestionParseService
    monkeypatch.setattr(question_parse_service.settings, "MEDIA_ROOT", tmp_path)
    monkeypatch.setattr(
        question_parse_service,
        "QuestionParseService",
        lambda: original_service(UnsafeComponent()),
    )
    caplog.set_level(logging.DEBUG)

    result = question_parse_service.parse_questions_stage2(
        [
            {
                "page_no": 1,
                "questions": [
                    {
                        "question_no": "8",
                        "section_title": SENSITIVE_VALUES[0],
                    }
                ],
            }
        ],
        {1: SimpleNamespace(image_path=private_page.name)},
    )

    assert result == []
    _assert_no_sensitive(result)
    _assert_safe_records(caplog.records)


def test_photo_adapter_raises_chainless_safe_error_and_clears_locals(
    monkeypatch,
):
    monkeypatch.setattr(
        photo_views, "upload_crop_image_safe", lambda *_args, **_kwargs: SENSITIVE_VALUES[0]
    )
    monkeypatch.setattr(
        photo_views,
        "vision_parser_component_factory",
        lambda: UnsafeComponent(),
    )

    with pytest.raises(
        AIRequestError,
        match=r"^PHOTO_RECOGNITION_FAILED: 图片识别失败$",
    ) as caught:
        photo_views._call_vision_api(list(SENSITIVE_VALUES))

    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None
    _assert_no_sensitive(caught.value)
    _assert_no_sensitive(_format_captured_locals(caught.value))


@pytest.mark.django_db
def test_parse_paper_failure_persists_only_safe_detail_and_retries_safely(
    monkeypatch, tmp_path, caplog
):
    paper = ExamPaper.objects.create(
        title="safe failure test",
        subject="M",
        source_file_path="private/source.docx",
    )
    task = ParseTask.objects.create(
        paper=paper,
        task_type="full_parse",
        status=const.TASK_RUNNING,
    )
    monkeypatch.setattr(parser_tasks.settings, "MEDIA_ROOT", tmp_path)
    monkeypatch.setattr(
        parser_tasks,
        "word_to_pdf",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AIRequestError(UNSAFE_DETAIL)
        ),
    )
    captured = {}

    def retry(*, exc, countdown):
        captured.update(exc=exc, countdown=countdown)
        raise exc

    monkeypatch.setattr(parser_tasks.parse_paper_task, "retry", retry)
    caplog.set_level(logging.DEBUG)

    with pytest.raises(
        AIRequestError,
        match=r"^PAPER_PARSE_FAILED: 试卷解析失败$",
    ) as caught:
        parser_tasks.parse_paper_task.run(paper.id)

    task.refresh_from_db()
    paper.refresh_from_db()
    assert task.status == const.TASK_FAILED
    assert task.error_message == "PAPER_PARSE_FAILED: 试卷解析失败"
    assert paper.status == const.PAPER_FAILED
    assert paper.error_message == task.error_message
    assert captured["countdown"] == 30
    assert captured["exc"] is caught.value
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None
    _assert_no_sensitive(task.error_message)
    _assert_no_sensitive(paper.error_message)
    _assert_no_sensitive(_format_captured_locals(caught.value))
    _assert_safe_records(caplog.records)


@pytest.mark.django_db
def test_question_reparse_failure_persists_and_retries_only_safe_detail(
    monkeypatch, tmp_path, caplog
):
    paper = ExamPaper.objects.create(
        title="question reparse safety",
        subject="M",
        source_file_path="source.docx",
    )
    question = ExamQuestion.objects.create(
        paper=paper,
        question_no="8",
        question_type="short_answer",
        section_title=SENSITIVE_VALUES[0],
        stem="safe stem",
        page_start=1,
        page_end=1,
    )
    private_page = tmp_path / "private-page.png"
    private_page.write_bytes(b"not inspected")
    ExamPage.objects.create(
        paper=paper,
        page_no=1,
        image_path=private_page.name,
    )
    task = ParseTask.objects.create(
        paper=paper,
        question=question,
        task_type="question_reparse",
        status=const.TASK_RUNNING,
    )
    monkeypatch.setattr(parser_tasks.settings, "MEDIA_ROOT", tmp_path)

    class UnsafeService:
        close_calls = 0

        def parse_question(self, *_args, **_kwargs):
            raise AIRequestError(UNSAFE_DETAIL)

        def close(self):
            type(self).close_calls += 1

    monkeypatch.setattr(
        question_parse_service, "QuestionParseService", UnsafeService
    )
    captured = {}

    def retry(*, exc, countdown):
        captured.update(exc=exc, countdown=countdown)
        raise exc

    monkeypatch.setattr(parser_tasks.reparse_question_task, "retry", retry)
    caplog.set_level(logging.DEBUG)

    with pytest.raises(
        AIRequestError,
        match=r"^QUESTION_REPARSE_FAILED: 题目重解析失败$",
    ) as caught:
        parser_tasks.reparse_question_task.run(question.id)

    task.refresh_from_db()
    assert task.status == const.TASK_FAILED
    assert task.error_message == "QUESTION_REPARSE_FAILED: 题目重解析失败"
    assert captured["countdown"] == 15
    assert captured["exc"] is caught.value
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None
    formatted = _format_captured_locals(caught.value)
    _assert_no_sensitive(formatted)
    assert str(private_page) not in formatted
    assert not AIParseResult.objects.exclude(error_message__isnull=True).exists()
    assert UnsafeService.close_calls == 1
    _assert_safe_records(caplog.records)


@pytest.mark.django_db
def test_page_reparse_failure_persists_and_retries_only_safe_detail(
    monkeypatch, tmp_path, caplog
):
    paper = ExamPaper.objects.create(
        title="page reparse safety",
        subject="M",
        source_file_path="source.docx",
    )
    private_page = tmp_path / "private-page.png"
    private_page.write_bytes(b"not inspected")
    ExamPage.objects.create(
        paper=paper,
        page_no=3,
        image_path=private_page.name,
    )
    monkeypatch.setattr(parser_tasks.settings, "MEDIA_ROOT", tmp_path)
    monkeypatch.setattr(
        parser_tasks,
        "detect_positions",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AIRequestError(UNSAFE_DETAIL)
        ),
    )
    captured = {}

    def retry(*, exc, countdown):
        captured.update(exc=exc, countdown=countdown)
        raise exc

    monkeypatch.setattr(parser_tasks.reparse_page_task, "retry", retry)
    caplog.set_level(logging.DEBUG)

    with pytest.raises(
        AIRequestError,
        match=r"^PAGE_REPARSE_FAILED: 页面重解析失败$",
    ) as caught:
        parser_tasks.reparse_page_task.run(paper.id, 3)

    task = ParseTask.objects.get(paper=paper, task_type="page_reparse")
    assert task.status == const.TASK_FAILED
    assert task.error_message == "PAGE_REPARSE_FAILED: 页面重解析失败"
    assert captured["countdown"] == 15
    assert captured["exc"] is caught.value
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None
    formatted = _format_captured_locals(caught.value)
    _assert_no_sensitive(formatted)
    assert str(private_page) not in formatted
    assert not AIParseResult.objects.exclude(error_message__isnull=True).exists()
    _assert_safe_records(caplog.records)


@pytest.mark.parametrize(
    ("task", "runner_name", "args", "expected_detail", "countdown"),
    [
        (
            parser_tasks.parse_paper_task,
            "_run_parse_paper_task",
            (1,),
            "PAPER_PARSE_FAILED: 试卷解析失败",
            30,
        ),
        (
            parser_tasks.reparse_question_task,
            "_run_reparse_question_task",
            (1,),
            "QUESTION_REPARSE_FAILED: 题目重解析失败",
            15,
        ),
        (
            parser_tasks.reparse_page_task,
            "_run_reparse_page_task",
            (1, 2),
            "PAGE_REPARSE_FAILED: 页面重解析失败",
            15,
        ),
    ],
)
def test_task_outer_boundary_sanitizes_unexpected_runner_failure(
    monkeypatch, task, runner_name, args, expected_detail, countdown
):
    monkeypatch.setattr(
        parser_tasks,
        runner_name,
        lambda *_args: (_ for _ in ()).throw(AIRequestError(UNSAFE_DETAIL)),
    )
    captured = {}

    def retry(*, exc, countdown):
        captured.update(exc=exc, countdown=countdown)
        raise exc

    monkeypatch.setattr(task, "retry", retry)

    with pytest.raises(AIRequestError, match=f"^{expected_detail}$") as caught:
        task.run(*args)

    assert captured["countdown"] == countdown
    assert captured["exc"] is caught.value
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None
    _assert_no_sensitive(_format_captured_locals(caught.value))
