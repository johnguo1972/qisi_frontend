import pytest
from rest_framework.test import APIClient


@pytest.fixture
def student_user(db):
    from apps.accounts.models import UserAccount
    from apps.accounts.roles import grant_user_role

    user = UserAccount.objects.create(
        role_type='student',
        mobile='13900000333',
        display_name='精练测试学生',
        status='active',
    )
    grant_user_role(user, 'student')
    return user


@pytest.fixture
def student_client(db, student_user):
    from apps.accounts.services import generate_tokens

    client = APIClient()
    token = generate_tokens(student_user, 'student')['access_token']
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
    return client


@pytest.fixture
def sample_paper(db):
    from apps.papers.models import ExamPaper

    return ExamPaper.objects.create(
        title='精练测试试卷',
        subject='数学',
        stage='初中',
        grade='9',
        source_file_path='uploads/practice-test.docx',
        status='uploaded',
    )
