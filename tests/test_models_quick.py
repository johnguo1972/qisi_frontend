import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from apps.accounts.models import UserAccount, StudentParentBind
from apps.missions.models import LearningMission, MissionLevel, MissionQuestionRel
from apps.study.models import StudentMissionProgress, StudentLevelProgress, AnswerAttempt, AIGuidanceSession
from apps.wrongbook.models import WrongBookItem, MasteryRecord


def test_models_smoke():
    """Smoke test: verify all 12 models are importable and have correct table names."""
    models = [
        (UserAccount, 'user_account'),
        (StudentParentBind, 'student_parent_bind'),
        (LearningMission, 'learning_mission'),
        (MissionLevel, 'mission_level'),
        (MissionQuestionRel, 'mission_question_rel'),
        (StudentMissionProgress, 'student_mission_progress'),
        (StudentLevelProgress, 'student_level_progress'),
        (AnswerAttempt, 'answer_attempt'),
        (AIGuidanceSession, 'ai_guidance_session'),
        (WrongBookItem, 'wrong_book_item'),
        (MasteryRecord, 'mastery_record'),
    ]

    for model_cls, expected_table in models:
        assert hasattr(model_cls, 'objects'), f"{model_cls.__name__} missing .objects"
        assert model_cls._meta.db_table == expected_table, (
            f"{model_cls.__name__}._meta.db_table = '{model_cls._meta.db_table}', expected '{expected_table}'"
        )
        # Verify the model has fields we expect
        fields = [f.name for f in model_cls._meta.get_fields()]
        assert 'id' in fields, f"{model_cls.__name__} missing 'id' field"

    print(f"All {len(models)} model smoke tests PASSED")
    print(f"Tables verified: {[m[1] for m in models]}")


if __name__ == '__main__':
    test_models_smoke()
