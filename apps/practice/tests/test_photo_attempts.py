from pathlib import Path

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.practice.models import PracticeAttempt, PracticeAttemptImage
from apps.practice.tests.test_online_and_pdf import make_active_set


def image_file(name='answer.png', content=b'not-a-real-image'):
    return SimpleUploadedFile(name, content, content_type='image/png')


@pytest.mark.django_db
def test_photo_attempt_draft_upload_and_submit_updates_only_practice_records(
    student_client, student_user, sample_paper, settings, tmp_path
):
    settings.MEDIA_ROOT = Path(tmp_path)
    practice_set, item, question = make_active_set(student_user, sample_paper, question_type='short_answer')

    draft = student_client.post(
        f'/api/v1/practice/sets/{practice_set.id}/items/{item.id}/attempts/draft',
        {'question_id': str(question.id)}, format='json',
    )
    assert draft.status_code == 201
    attempt_id = draft.json()['data']['attempt_id']
    assert PracticeAttempt.objects.get(pk=attempt_id).status == 'draft'

    uploaded = student_client.post(
        f'/api/v1/practice/attempts/{attempt_id}/images',
        {'image': image_file(), 'page_no': 1}, format='multipart',
    )
    assert uploaded.status_code == 201
    image_data = uploaded.json()['data']['image']
    image = PracticeAttemptImage.objects.get(pk=image_data['id'])
    assert image.page_no == 1
    assert image.image_path.startswith(f'practice_attempts/{attempt_id}/')
    assert (Path(settings.MEDIA_ROOT) / image.image_path).exists()

    submitted = student_client.post(
        f'/api/v1/practice/attempts/{attempt_id}/submit',
        {'answer_content': {'note': '照片作答'}}, format='json',
    )
    assert submitted.status_code == 200
    data = submitted.json()['data']
    assert data['status'] == 'pending_review'
    assert data['is_pending'] is True
    attempt = PracticeAttempt.objects.get(pk=attempt_id)
    assert attempt.submit_source == 'photo'
    assert attempt.is_correct is None
    assert practice_set.__class__.objects.get(pk=practice_set.id).answered_count == 1


@pytest.mark.django_db
def test_photo_attempt_rejects_duplicate_page_and_parent_submission(
    student_client, student_user, sample_paper
):
    from apps.accounts.models import UserAccount
    from apps.accounts.roles import grant_user_role
    from apps.practice.tests.test_pool_and_sets import parent_client_for

    practice_set, item, question = make_active_set(student_user, sample_paper)
    draft = student_client.post(
        f'/api/v1/practice/sets/{practice_set.id}/items/{item.id}/attempts/draft',
        {'question_id': str(question.id)}, format='json',
    )
    attempt_id = draft.json()['data']['attempt_id']
    first = student_client.post(
        f'/api/v1/practice/attempts/{attempt_id}/images',
        {'image': image_file(), 'page_no': 1}, format='multipart',
    )
    assert first.status_code == 201
    duplicate = student_client.post(
        f'/api/v1/practice/attempts/{attempt_id}/images',
        {'image': image_file('second.png'), 'page_no': 1}, format='multipart',
    )
    assert duplicate.status_code == 400
    assert duplicate.json()['data']['error_code'] == 'DUPLICATE_PAGE'

    parent = UserAccount.objects.create(
        role_type='parent', mobile='13900000991', display_name='照片家长', status='active'
    )
    grant_user_role(parent, 'parent')
    parent_client = parent_client_for(parent, student_user)
    forbidden = parent_client.post(
        f'/api/v1/practice/attempts/{attempt_id}/submit', {}, format='json'
    )
    assert forbidden.status_code == 403
    assert PracticeAttempt.objects.get(pk=attempt_id).status == 'draft'


@pytest.mark.django_db
def test_photo_attempt_requires_its_own_question_and_image(student_client, student_user, sample_paper):
    practice_set, item, question = make_active_set(student_user, sample_paper)
    mismatch = student_client.post(
        f'/api/v1/practice/sets/{practice_set.id}/items/{item.id}/attempts/draft',
        {'question_id': str(practice_set.id)}, format='json',
    )
    assert mismatch.status_code == 400
    assert mismatch.json()['data']['error_code'] == 'QUESTION_MISMATCH'

    draft = student_client.post(
        f'/api/v1/practice/sets/{practice_set.id}/items/{item.id}/attempts/draft',
        {'question_id': str(question.id)}, format='json',
    )
    attempt_id = draft.json()['data']['attempt_id']
    submit = student_client.post(
        f'/api/v1/practice/attempts/{attempt_id}/submit', {}, format='json'
    )
    assert submit.status_code == 400
    assert submit.json()['data']['error_code'] == 'IMAGE_REQUIRED'
