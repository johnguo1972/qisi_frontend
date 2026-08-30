import uuid

from rest_framework.response import Response


def trace_id():
    return uuid.uuid4().hex[:16]


def success(data, *, message='success', status=200, meta=None):
    return Response({
        'code': 0, 'message': message, 'data': data,
        'meta': meta or {}, 'trace_id': trace_id(),
    }, status=status)
