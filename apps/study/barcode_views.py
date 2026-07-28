"""条形码生成与扫码查询视图。"""
import io
import uuid
import barcode
from barcode.writer import ImageWriter
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.http import HttpResponse
from apps.parser.models import ExamQuestion


def make_trace_id() -> str:
    return uuid.uuid4().hex[:16]


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def question_barcode(request, question_id):
    """
    生成题目的条形码图片。
    GET /api/v1/questions/<id>/barcode/
    返回: image/png
    """
    try:
        question = ExamQuestion.objects.get(pk=question_id)
    except ExamQuestion.DoesNotExist:
        return Response({'code': 404, 'message': '题目不存在', 'data': None, 'trace_id': make_trace_id()}, status=404)

    # 使用 system_id 或 question_id 作为条形码数据
    barcode_data = question.barcode_data or question.system_id or str(question.id)

    # 生成 Code128 条形码
    try:
        code128 = barcode.get('code128', barcode_data, writer=ImageWriter())
        buf = io.BytesIO()
        code128.write(buf, options={
            'write_text': True,
            'font_size': 10,
            'text_distance': 5,
            'quiet_zone': 6.5,
        })
        buf.seek(0)

        return HttpResponse(buf.getvalue(), content_type='image/png')
    except Exception as e:
        return Response({'code': 500, 'message': f'条形码生成失败: {str(e)}', 'data': None}, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def barcode_scan(request):
    """
    扫码查询题目。
    POST /api/v1/questions/barcode/scan/
    Body: { "barcode_data": "P001234" }
    """
    barcode_data = request.data.get('barcode_data', '').strip()
    if not barcode_data:
        return Response({'code': 400, 'message': '缺少barcode_data', 'data': None, 'trace_id': make_trace_id()}, status=400)

    # 先按 barcode_data 查找
    question = ExamQuestion.objects.filter(barcode_data=barcode_data).first()

    # 再按 system_id 查找
    if not question:
        question = ExamQuestion.objects.filter(system_id=barcode_data).first()

    if not question:
        return Response({'code': 404, 'message': '未找到对应题目', 'data': None, 'trace_id': make_trace_id()}, status=404)

    # 返回题目基本信息
    return Response({
        'code': 0,
        'message': 'success',
        'data': {
            'question_id': str(question.id),
            'system_id': question.system_id,
            'question_no': question.question_no,
            'question_type': question.question_type,
            'stem': question.stem[:100] + '...' if len(question.stem) > 100 else question.stem,
            'tags': question.tags or [],
            'knowledge_points': question.knowledge_points or [],
            'video_url': question.video_explanation_url,
        },
        'trace_id': make_trace_id(),
    })
