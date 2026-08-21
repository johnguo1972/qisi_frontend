"""Small response serializers for the personal practice APIs."""
from rest_framework import serializers

from .models import PracticePoolItem, PracticeSet, PracticeSetItem


class PracticePoolItemSerializer(serializers.ModelSerializer):
    question_id = serializers.UUIDField(format='hex_verbose', read_only=True)
    source_wrong_item_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = PracticePoolItem
        fields = [
            'id', 'question_id', 'source_wrong_item_id', 'source_type',
            'recommendation_snapshot', 'display_snapshot', 'status',
            'created_at', 'updated_at',
        ]


class PracticeSetItemSerializer(serializers.ModelSerializer):
    question_id = serializers.UUIDField(format='hex_verbose', read_only=True)
    pool_item_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = PracticeSetItem
        fields = [
            'id', 'pool_item_id', 'question_id', 'sort_no', 'source_type',
            'display_snapshot', 'created_at',
        ]


class PracticeSetSerializer(serializers.ModelSerializer):
    student_user_id = serializers.UUIDField(read_only=True)
    created_by_user_id = serializers.UUIDField(read_only=True)

    class Meta:
        model = PracticeSet
        fields = [
            'id', 'student_user_id', 'created_by_user_id', 'created_via_role',
            'title', 'status', 'question_count', 'answered_count',
            'progress_percent', 'pdf_file_path', 'pdf_version',
            'created_at', 'updated_at', 'completed_at',
        ]


def serialize_pool_item(item):
    return PracticePoolItemSerializer(item).data


def serialize_set_item(item):
    return PracticeSetItemSerializer(item).data


def serialize_set(practice_set, *, include_items=False):
    data = PracticeSetSerializer(practice_set).data
    if include_items:
        data['items'] = [
            serialize_set_item(item)
            for item in practice_set.items.all().order_by('sort_no')
        ]
    return data
