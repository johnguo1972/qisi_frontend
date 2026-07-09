import uuid
import json
import os
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import LearningMission, MissionLevel, MissionQuestionRel
from apps.parser.models import ExamQuestion, QuestionImage, QuestionOption
from .serializers import (
    MissionListSerializer, MissionDetailSerializer,
    CreateMissionSerializer, CreateLevelSerializer, AddQuestionsSerializer,
    BatchCreateLevelsSerializer,
)


def make_trace_id():
    return uuid.uuid4().hex[:16]


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def mission_list(request):
    """M-01 / M-02: List / Create missions."""
    user = request.user

    if request.method == 'GET':
        missions = LearningMission.objects.filter(
            creator_teacher_id=user
        ).order_by('-created_at')
        return Response({
            'code': 0, 'message': 'success', 'trace_id': make_trace_id(),
            'data': MissionListSerializer(missions, many=True).data,
        })

    # POST: create
    serializer = CreateMissionSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    mission = serializer.save(creator_teacher_id=user)
    return Response({
        'code': 0, 'message': '创建成功',
        'data': {'id': mission.id, 'mission_no': mission.mission_no},
        'trace_id': make_trace_id(),
    }, status=status.HTTP_201_CREATED)


@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def mission_detail(request, mission_id):
    """M-03 / M-04: Mission detail / update."""
    try:
        mission = LearningMission.objects.get(pk=mission_id, creator_teacher_id=request.user)
    except LearningMission.DoesNotExist:
        return Response({
            'code': 404, 'message': '任务不存在', 'data': None, 'trace_id': make_trace_id(),
        }, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        return Response({
            'code': 0, 'message': 'success',
            'data': MissionDetailSerializer(mission).data, 'trace_id': make_trace_id(),
        })

    # PUT: update
    for field in ['mission_name', 'goal_text', 'start_at', 'end_at', 'default_mode_policy']:
        if field in request.data:
            val = request.data[field]
            # 空字符串转 None（Django DateTimeField 不接受空字符串）
            if field in ('start_at', 'end_at') and val == '':
                val = None
            setattr(mission, field, val)

    # Handle class_id separately (ForeignKey field)
    old_class_id = mission.class_obj_id
    if 'class_id' in request.data:
        class_id = request.data['class_id']
        if class_id:
            from apps.institutions.models import Class
            try:
                mission.class_obj = Class.objects.get(pk=class_id)
            except Class.DoesNotExist:
                pass
        else:
            mission.class_obj = None

    mission.save()

    # Sync StudentMissionProgress if class changed
    new_class_id = mission.class_obj_id
    if old_class_id != new_class_id:
        from apps.institutions.models import ClassStudent
        from apps.study.models import StudentMissionProgress

        if old_class_id:
            # Remove progress records for students no longer in this class
            old_student_ids = set(ClassStudent.objects.filter(
                class_obj_id=old_class_id, status='active',
            ).values_list('student_id', flat=True))
            if new_class_id:
                new_student_ids = set(ClassStudent.objects.filter(
                    class_obj_id=new_class_id, status='active',
                ).values_list('student_id', flat=True))
                removed_ids = old_student_ids - new_student_ids
            else:
                removed_ids = old_student_ids
            StudentMissionProgress.objects.filter(
                mission=mission, student_user_id__in=removed_ids,
            ).delete()

        if new_class_id:
            # Create progress records for new students in the class
            new_student_ids = ClassStudent.objects.filter(
                class_obj_id=new_class_id, status='active',
            ).values_list('student_id', flat=True)
            for student_id in new_student_ids:
                StudentMissionProgress.objects.get_or_create(
                    mission=mission,
                    student_user_id_id=student_id,
                    defaults={
                        'progress_status': 'not_started',
                        'progress_percent': 0,
                    },
                )
    return Response({'code': 0, 'message': '更新成功', 'data': None, 'trace_id': make_trace_id()})


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def mission_delete(request, mission_id):
    """M-04b: Delete mission (only draft missions can be deleted)."""
    try:
        mission = LearningMission.objects.get(pk=mission_id, creator_teacher_id=request.user)
    except LearningMission.DoesNotExist:
        return Response({
            'code': 404, 'message': '任务不存在', 'data': None, 'trace_id': make_trace_id(),
        }, status=status.HTTP_404_NOT_FOUND)

    if mission.status != 'draft':
        return Response({
            'code': 400, 'message': '只能删除草稿状态的任务', 'data': None, 'trace_id': make_trace_id(),
        }, status=status.HTTP_400_BAD_REQUEST)

    # Delete related levels and question relations
    MissionLevel.objects.filter(mission=mission).delete()
    MissionQuestionRel.objects.filter(mission=mission).delete()
    mission.delete()

    return Response({'code': 0, 'message': '删除成功', 'data': None, 'trace_id': make_trace_id()})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mission_levels(request, mission_id):
    """M-05: Add level to mission."""
    try:
        mission = LearningMission.objects.get(pk=mission_id, creator_teacher_id=request.user)
    except LearningMission.DoesNotExist:
        return Response({
            'code': 404, 'message': '任务不存在', 'data': None, 'trace_id': make_trace_id(),
        }, status=status.HTTP_404_NOT_FOUND)

    serializer = CreateLevelSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    level = serializer.save(mission=mission)
    return Response({
        'code': 0, 'message': '关卡创建成功',
        'data': {'id': level.id}, 'trace_id': make_trace_id(),
    }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mission_levels_batch(request, mission_id):
    """M-05b: Batch create levels with questions for a mission."""
    try:
        mission = LearningMission.objects.get(pk=mission_id, creator_teacher_id=request.user)
    except LearningMission.DoesNotExist:
        return Response({
            'code': 404, 'message': '任务不存在', 'data': None, 'trace_id': make_trace_id(),
        }, status=status.HTTP_404_NOT_FOUND)

    serializer = BatchCreateLevelsSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    # 编辑模式：先删除旧关卡和题目关联，再创建新的
    old_levels = mission.levels.all()
    for old_lv in old_levels:
        MissionQuestionRel.objects.filter(level=old_lv).delete()
    old_levels.delete()

    level_ids = []
    for i, lv_data in enumerate(data['levels']):
        level = MissionLevel.objects.create(
            mission=mission,
            level_no=i + 1,
            level_name=lv_data.get('level_name') or lv_data.get('name') or f'第{i+1}关',
            level_type=lv_data.get('level_type') or lv_data.get('type') or 'practice',
            mode_policy=lv_data.get('mode_policy') or lv_data.get('mode') or 'block_a',
            pass_rule_json=lv_data.get('pass_rule_json') or lv_data.get('passRuleJson') or {},
            hint_strength=lv_data.get('hint_strength') or lv_data.get('hintStrength') or 'medium',
        )
        level_ids.append(level.id)

        # 添加题目到该关卡
        question_ids = lv_data.get('question_ids') or lv_data.get('questionIds') or []
        for j, qid in enumerate(question_ids):
            MissionQuestionRel.objects.create(
                mission=mission,
                level=level,
                question_id=qid,
                sort_no=j,
                is_required=True,
            )

    return Response({
        'code': 0, 'message': '关卡创建成功',
        'data': {'level_ids': level_ids}, 'trace_id': make_trace_id(),
    }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mission_questions(request, mission_id):
    """M-06: Add questions to level."""
    try:
        mission = LearningMission.objects.get(pk=mission_id, creator_teacher_id=request.user)
    except LearningMission.DoesNotExist:
        return Response({
            'code': 404, 'message': '任务不存在', 'data': None, 'trace_id': make_trace_id(),
        }, status=status.HTTP_404_NOT_FOUND)

    serializer = AddQuestionsSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    # Verify the level belongs to this mission
    try:
        level = MissionLevel.objects.get(pk=data['level_id'], mission=mission)
    except MissionLevel.DoesNotExist:
        return Response({
            'code': 400, 'message': '关卡不属于当前任务', 'data': None, 'trace_id': make_trace_id(),
        }, status=status.HTTP_400_BAD_REQUEST)

    for i, qid in enumerate(data['question_ids']):
        MissionQuestionRel.objects.create(
            mission=mission,
            level=level,
            question_id=qid,
            sort_no=i,
            is_required=data['is_required'],
        )
    return Response({'code': 0, 'message': '题目添加成功', 'data': None, 'trace_id': make_trace_id()})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def mission_level_detail(request, mission_id, level_id):
    """M-09: Get level detail with questions (teacher side)."""
    try:
        mission = LearningMission.objects.get(pk=mission_id, creator_teacher_id=request.user)
    except LearningMission.DoesNotExist:
        return Response({
            'code': 404, 'message': '任务不存在', 'data': None, 'trace_id': make_trace_id(),
        }, status=status.HTTP_404_NOT_FOUND)

    try:
        level = MissionLevel.objects.get(pk=level_id, mission=mission)
    except MissionLevel.DoesNotExist:
        return Response({
            'code': 404, 'message': '关卡不存在', 'data': None, 'trace_id': make_trace_id(),
        }, status=status.HTTP_404_NOT_FOUND)

    rels = MissionQuestionRel.objects.filter(level=level).order_by('sort_no')
    questions = []
    for rel in rels:
        try:
            q = ExamQuestion.objects.get(pk=rel.question_id)
            questions.append({
                'id': q.id,
                'question_no': q.question_no,
                'question_type': q.question_type,
                'difficulty': float(q.difficulty) if q.difficulty else None,
                'stem': q.stem,
                'stem_html': q.stem_html,
                'answer': q.answer,
                'analysis': q.analysis,
                'images': [{'url': img.file_path, 'sort_order': img.sort_order}
                          for img in q.images.all().order_by('sort_order')],
                'options': [{'label': o.option_label, 'content': o.content, 'sort_order': o.sort_order}
                           for o in q.options.all().order_by('sort_order')],
            })
        except ExamQuestion.DoesNotExist:
            continue

    return Response({
        'code': 0, 'message': 'success',
        'data': {
            'level_id': level.id,
            'level_name': level.level_name,
            'level_type': level.level_type,
            'mode_policy': level.mode_policy,
            'questions': questions,
        }, 'trace_id': make_trace_id(),
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mission_publish(request, mission_id):
    """M-07: Publish mission and create progress records for class students."""
    try:
        mission = LearningMission.objects.get(pk=mission_id, creator_teacher_id=request.user)
    except LearningMission.DoesNotExist:
        return Response({
            'code': 404, 'message': '任务不存在', 'data': None, 'trace_id': make_trace_id(),
        }, status=status.HTTP_404_NOT_FOUND)

    mission.status = 'published'
    mission.save()

    # If mission is tied to a class, create progress records for all students in that class
    created_count = 0
    if mission.class_obj_id:
        from apps.institutions.models import ClassStudent
        from apps.study.models import StudentMissionProgress

        student_ids = ClassStudent.objects.filter(
            class_obj_id=mission.class_obj_id, status='active',
        ).values_list('student_id', flat=True)

        for student_id in student_ids:
            StudentMissionProgress.objects.get_or_create(
                mission=mission,
                student_user_id_id=student_id,
                defaults={
                    'progress_status': 'not_started',
                    'progress_percent': 0,
                },
            )
            created_count += 1

    return Response({
        'code': 0, 'message': '发布成功',
        'data': {'students_notified': created_count},
        'trace_id': make_trace_id(),
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mission_clone(request, mission_id):
    """M-08: Clone mission."""
    try:
        original = LearningMission.objects.get(pk=mission_id, creator_teacher_id=request.user)
    except LearningMission.DoesNotExist:
        return Response({
            'code': 404, 'message': '任务不存在', 'data': None, 'trace_id': make_trace_id(),
        }, status=status.HTTP_404_NOT_FOUND)

    clone = LearningMission.objects.create(
        mission_name=f"{original.mission_name} (副本)",
        goal_text=original.goal_text,
        creator_teacher_id=request.user,
        start_at=original.start_at,
        end_at=original.end_at,
        default_mode_policy=original.default_mode_policy,
    )
    # Clone levels and questions
    for level in original.levels.all():
        new_level = MissionLevel.objects.create(
            mission=clone, level_no=level.level_no, level_name=level.level_name,
            level_type=level.level_type, pass_rule_json=level.pass_rule_json,
            mode_policy=level.mode_policy, hint_strength=level.hint_strength,
        )
        for rel in MissionQuestionRel.objects.filter(level=level):
            MissionQuestionRel.objects.create(
                mission=clone, level=new_level, question_id=rel.question_id,
                sort_no=rel.sort_no, is_required=rel.is_required,
            )
    return Response({
        'code': 0, 'message': '复制成功',
        'data': {'id': clone.id}, 'trace_id': make_trace_id(),
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mission_clone_with_class(request, mission_id):
    """M-09: Clone a mission and assign it to a different class with new deadlines."""
    try:
        original = LearningMission.objects.get(pk=mission_id)
    except LearningMission.DoesNotExist:
        return Response({
            'code': 404, 'message': '任务不存在', 'data': None, 'trace_id': make_trace_id(),
        }, status=status.HTTP_404_NOT_FOUND)

    # Verify user is the teacher of the original mission OR a teacher of the target class
    class_id = request.data.get('class_id')
    if not class_id:
        return Response({
            'code': 400, 'message': 'class_id 不能为空', 'data': None, 'trace_id': make_trace_id(),
        }, status=status.HTTP_400_BAD_REQUEST)

    # Verify user is a teacher of the target class
    from apps.institutions.models import ClassTeacher, Class
    try:
        target_class = Class.objects.get(pk=class_id)
    except Class.DoesNotExist:
        return Response({
            'code': 404, 'message': '班级不存在', 'data': None, 'trace_id': make_trace_id(),
        }, status=status.HTTP_404_NOT_FOUND)

    if not ClassTeacher.objects.filter(class_obj_id=class_id, teacher=request.user).exists():
        return Response({
            'code': 403, 'message': '您不是该班级的教师', 'data': None, 'trace_id': make_trace_id(),
        }, status=status.HTTP_403_FORBIDDEN)

    # Create clone with new class and deadlines
    clone = LearningMission.objects.create(
        mission_name=f"{original.mission_name} (副本)",
        goal_text=original.goal_text,
        creator_teacher_id=request.user,
        class_obj=target_class,
        start_at=request.data.get('start_at') or original.start_at,
        end_at=request.data.get('end_at'),  # Required for homework
        default_mode_policy=original.default_mode_policy,
    )

    # Clone levels and questions
    for level in original.levels.all():
        new_level = MissionLevel.objects.create(
            mission=clone, level_no=level.level_no, level_name=level.level_name,
            level_type=level.level_type, pass_rule_json=level.pass_rule_json,
            mode_policy=level.mode_policy, hint_strength=level.hint_strength,
        )
        for rel in MissionQuestionRel.objects.filter(level=level):
            MissionQuestionRel.objects.create(
                mission=clone, level=new_level, question_id=rel.question_id,
                sort_no=rel.sort_no, is_required=rel.is_required,
            )

    return Response({
        'code': 0, 'message': '复制成功',
        'data': {'id': clone.id, 'mission_no': clone.mission_no},
        'trace_id': make_trace_id(),
    })


# ============================================================
# Teacher B/C Mode Guidance
# ============================================================

# In-memory session store for teacher practice guidance
_teacher_guidance_sessions: dict = {}


def _get_question_image_urls(question, max_images=3):
    """Get OSS URLs for question images."""
    from django.conf import settings
    images = list(QuestionImage.objects.filter(question=question).order_by('sort_order')[:max_images])
    urls = []
    for img in images:
        if img.file_path:
            # Try to get OSS URL or fall back to media URL
            if img.oss_url:
                urls.append(img.oss_url)
            else:
                urls.append(f'{settings.MEDIA_URL}{img.file_path}')
    return urls


def _call_qwen(system_prompt, user_prompt, model='qwen3.6-flash'):
    """Call Qwen API for C mode evaluation."""
    import httpx
    import time
    api_key = os.environ.get('QWEN_API_KEY', '')
    if not api_key:
        return '（AI评价功能暂不可用，请配置QWEN_API_KEY）'
    url = 'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions'
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
    }
    messages = [
        {'role': 'system', 'content': system_prompt},
        {'role': 'user', 'content': user_prompt},
    ]
    payload = {
        'model': model,
        'messages': messages,
        'max_tokens': 500,
        'temperature': 0.7,
    }
    try:
        with httpx.Client(timeout=60.0, trust_env=False) as client:
            resp = client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            result = resp.json()
            return result['choices'][0]['message']['content']
    except Exception as e:
        return f'（AI评价调用失败：{str(e)}）'


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def start_teacher_guidance(request, question_id):
    """启动B/C模式引导。

    POST /api/v1/teacher/guidance/start/
    Body: { "question_id": 123, "mode": "B" }  // mode: "B" or "C"
    """
    mode = request.data.get('mode', 'B')
    if mode not in ('B', 'C'):
        return Response({'code': 400, 'message': 'mode 必须为 B 或 C'}, status=400)

    try:
        q = ExamQuestion.objects.get(pk=question_id)
    except ExamQuestion.DoesNotExist:
        return Response({'code': 404, 'message': '题目不存在'}, status=404)

    session_id = uuid.uuid4().hex[:16]

    if mode == 'B':
        # B模式：从 ai_answer_b 获取引导选项
        ai_b = q.ai_answer_b or {}
        if isinstance(ai_b, str):
            try:
                ai_b = json.loads(ai_b)
            except:
                ai_b = {}
        options = ai_b.get('options', [])
        hint = ai_b.get('hint', '请仔细阅读题目，思考关键条件。')
        # 如果 ai_answer_b 没有数据，使用默认引导
        if not options and not hint:
            hint = '这道题的关键条件是什么？请仔细阅读题干。'
            options = [
                '直接应用公式求解',
                '先分析已知条件',
                '画图辅助理解',
                '尝试代入具体数值',
            ]

        _teacher_guidance_sessions[session_id] = {
            'question_id': question_id,
            'mode': 'B',
            'turn': 0,
            'messages': [{'role': 'system', 'content': hint}],
            'options': options,
            'hint': hint,
        }

        return Response({
            'code': 0, 'message': 'success',
            'data': {
                'session_id': session_id,
                'mode': 'B',
                'hint': hint,
                'options': options,
            }, 'trace_id': make_trace_id(),
        })
    else:
        # C模式：生成第一个引导问题
        ai_c = q.ai_answer_c or {}
        if isinstance(ai_c, str):
            try:
                ai_c = json.loads(ai_c)
            except:
                ai_c = {}

        first_question = ai_c.get('first_question') or ai_c.get('question') or '你觉得这道题的关键条件是什么？'

        _teacher_guidance_sessions[session_id] = {
            'question_id': question_id,
            'mode': 'C',
            'turn': 0,
            'messages': [{'role': 'system', 'content': first_question}],
            'first_question': first_question,
            'ai_c': ai_c,
        }

        return Response({
            'code': 0, 'message': 'success',
            'data': {
                'session_id': session_id,
                'mode': 'C',
                'question': first_question,
            }, 'trace_id': make_trace_id(),
        })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def teacher_guidance_reply(request, session_id):
    """B/C模式引导回复。

    POST /api/v1/teacher/guidance/reply/{session_id}/
    Body: { "user_answer": "..." }
    """
    session = _teacher_guidance_sessions.get(session_id)
    if not session:
        return Response({'code': 404, 'message': '引导会话不存在'}, status=404)

    user_answer = request.data.get('user_answer', '')
    session['turn'] += 1
    session['messages'].append({'role': 'user', 'content': user_answer})

    question_id = session['question_id']
    try:
        q = ExamQuestion.objects.get(pk=question_id)
    except ExamQuestion.DoesNotExist:
        return Response({'code': 404, 'message': '题目不存在'}, status=404)

    if session['mode'] == 'B':
        # B模式：返回下一步引导
        ai_b = q.ai_answer_b or {}
        if isinstance(ai_b, str):
            try:
                ai_b = json.loads(ai_b)
            except:
                ai_b = {}

        next_hint = ai_b.get('next_hint') or ai_b.get('hint') or '很好，继续思考下一个关键点。'
        session['messages'].append({'role': 'system', 'content': next_hint})

        # 检查是否完成（3轮后）
        is_completed = session['turn'] >= 3
        if is_completed:
            next_hint = '引导完成！你可以继续巩固或进入下一题。'

        return Response({
            'code': 0, 'message': 'success',
            'data': {
                'next_hint': next_hint,
                'is_completed': is_completed,
                'mode': 'B',
                'turn': session['turn'],
            }, 'trace_id': make_trace_id(),
        })
    else:
        # C模式：调用Qwen评价用户回答，然后给出下一个引导问题
        ai_c = session.get('ai_c') or {}
        if not ai_c and q.ai_answer_c:
            ai_c = q.ai_answer_c
            if isinstance(ai_c, str):
                try:
                    ai_c = json.loads(ai_c)
                except:
                    ai_c = {}

        # 构建评价prompt
        eval_system = '你是一位经验丰富的教师。请对学生回答进行简明评价（1-2句），指出是否正确、有什么不足，然后给出鼓励。'
        eval_prompt = f'''题目：{q.stem}
正确答案：{q.answer or "见解析"}
学生回答：{user_answer}
请评价学生的回答。'''

        evaluation = _call_qwen(eval_system, eval_prompt, model='qwen3.6-flash')

        # 获取下一个引导问题
        steps = ai_c.get('steps') or ai_c.get('dialogue') or []
        next_question = None
        if session['turn'] < len(steps):
            step = steps[session['turn']]
            if isinstance(step, dict):
                next_question = step.get('question') or step.get('prompt')
            elif isinstance(step, str):
                next_question = step

        if not next_question:
            if session['turn'] >= 3:
                next_question = '引导完成！你已经很好地理解了这道题。'
            else:
                next_question = '很好，请继续思考下一个问题。'

        session['messages'].append({'role': 'system', 'content': f'评价：{evaluation}\n\n{next_question}'})

        is_completed = session['turn'] >= 3

        return Response({
            'code': 0, 'message': 'success',
            'data': {
                'evaluation': evaluation,
                'next_question': next_question,
                'is_completed': is_completed,
                'mode': 'C',
                'turn': session['turn'],
            }, 'trace_id': make_trace_id(),
        })
