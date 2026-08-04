"""Question QR code endpoint."""
import io

from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.http import HttpResponse
from apps.parser.models import ExamQuestion


@api_view(['GET'])
@permission_classes([])
def question_qr(request, question_id):
    """Generate a QR code containing the question UUID."""
    try:
        question = ExamQuestion.objects.get(pk=question_id)
    except ExamQuestion.DoesNotExist:
        return Response({'code': 404, 'message': '题目不存在'}, status=404)

    try:
        import qrcode
        image = qrcode.make(str(question.id))
        buf = io.BytesIO()
        image.save(buf, format='PNG')
        return HttpResponse(buf.getvalue(), content_type='image/png')
    except ImportError:
        return Response({'code': 503, 'message': '二维码组件未安装'}, status=503)
