"""Factory definitions for test data generation."""
import factory
from factory.django import DjangoModelFactory
from factory.fuzzy import FuzzyInteger, FuzzyText


class UserAccountFactory(DjangoModelFactory):
    class Meta:
        model = 'accounts.UserAccount'

    role_type = 'teacher'
    mobile = factory.Sequence(lambda n: f'139{10000000 + n}')
    display_name = factory.Sequence(lambda n: f'测试用户{n}')
    password = 'pbkdf2_sha256$dummy'


class AdminUserFactory(UserAccountFactory):
    role_type = 'admin'
    display_name = factory.Sequence(lambda n: f'管理员{n}')


class TeacherUserFactory(UserAccountFactory):
    role_type = 'teacher'
    subject = '数学'


class StudentUserFactory(UserAccountFactory):
    role_type = 'student'


class InstitutionFactory(DjangoModelFactory):
    class Meta:
        model = 'institutions.Institution'

    institution_name = factory.Sequence(lambda n: f'测试学校{n}')
    contact_name = '联系人'
    contact_phone = factory.Sequence(lambda n: f'138{10000000 + n}')


class ClassFactory(DjangoModelFactory):
    class Meta:
        model = 'institutions.Class'

    institution = factory.SubFactory(InstitutionFactory)
    class_name = factory.Sequence(lambda n: f'测试班级{n}')
    creator_teacher = factory.SubFactory(TeacherUserFactory)


class ExamPaperFactory(DjangoModelFactory):
    class Meta:
        model = 'papers.ExamPaper'

    title = factory.Sequence(lambda n: f'测试试卷{n}')
    subject = '数学'
    stage = '初中'
    grade = '9'
    source_file_path = factory.Sequence(lambda n: f'uploads/paper-{n}.docx')
    status = 'uploaded'
    uploaded_by = factory.SubFactory(TeacherUserFactory)


class ExamQuestionFactory(DjangoModelFactory):
    class Meta:
        model = 'parser.ExamQuestion'

    paper = factory.SubFactory(ExamPaperFactory)
    question_no = factory.Sequence(lambda n: str(n))
    question_type = 'single_choice'
    subject = '数学'
    stem = factory.Sequence(lambda n: f'测试题目{n}：以下哪个选项是正确的？')
    answer = 'A'
    difficulty = 3.00


class LearningMissionFactory(DjangoModelFactory):
    class Meta:
        model = 'missions.LearningMission'

    mission_name = factory.Sequence(lambda n: f'测试任务{n}')
    goal_text = '测试学习目标'
    status = 'draft'
    creator_teacher = factory.SubFactory(TeacherUserFactory)


class MissionLevelFactory(DjangoModelFactory):
    class Meta:
        model = 'missions.MissionLevel'

    mission = factory.SubFactory(LearningMissionFactory)
    level_no = FuzzyInteger(1, 10)
    level_name = factory.Sequence(lambda n: f'第{n}关')
    level_type = 'practice'
    mode_policy = 'block_a'


class ParseTaskFactory(DjangoModelFactory):
    class Meta:
        model = 'papers.ParseTask'

    paper = factory.SubFactory(ExamPaperFactory)
    task_type = 'full_parse'
    status = 'running'
    progress = 0
    current_step = '等待解析'
