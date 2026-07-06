from rest_framework import serializers

from apps.accounts.models import UserAccount
from apps.institutions.models import (
    Institution,
    InstitutionMember,
    Class,
    ClassTeacher,
    ClassStudent,
    ClassJoinRequest,
)


# ──────────────────────────────────────────────
# Institution serializers
# ──────────────────────────────────────────────

class InstitutionListSerializer(serializers.ModelSerializer):
    teacher_count = serializers.SerializerMethodField()
    class_count = serializers.SerializerMethodField()

    class Meta:
        model = Institution
        fields = [
            'id', 'institution_name', 'contact_name', 'contact_phone',
            'contact_email', 'address', 'status', 'teacher_count',
            'class_count', 'created_at', 'updated_at',
        ]

    def get_teacher_count(self, obj):
        return InstitutionMember.objects.filter(
            institution=obj, role='teacher', status='active',
        ).count()

    def get_class_count(self, obj):
        return obj.classes.count()


class InstitutionDetailSerializer(serializers.ModelSerializer):
    creator_name = serializers.SerializerMethodField()

    class Meta:
        model = Institution
        fields = [
            'id', 'institution_name', 'contact_name', 'contact_phone',
            'contact_email', 'address', 'status', 'creator_name',
            'created_at', 'updated_at',
        ]

    def get_creator_name(self, obj):
        if obj.created_by:
            return obj.created_by.display_name
        return None


class CreateInstitutionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Institution
        fields = ['institution_name', 'contact_name', 'contact_phone',
                  'contact_email', 'address']

    def create(self, validated_data):
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)


# ──────────────────────────────────────────────
# Institution member serializers
# ──────────────────────────────────────────────

class InstitutionMemberSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()
    user_mobile = serializers.SerializerMethodField()
    user_role_type = serializers.SerializerMethodField()
    user_subject = serializers.SerializerMethodField()
    stages = serializers.SerializerMethodField()

    class Meta:
        model = InstitutionMember
        fields = ['id', 'institution', 'user', 'role', 'status',
                  'joined_at', 'user_name', 'user_mobile', 'user_role_type', 'user_subject', 'stages']

    def get_user_name(self, obj):
        return obj.user.display_name if obj.user else None

    def get_user_mobile(self, obj):
        return obj.user.mobile if obj.user else None

    def get_user_role_type(self, obj):
        return obj.user.role_type if obj.user else None

    def get_user_subject(self, obj):
        return obj.user.subject if obj.user else None

    def get_stages(self, obj):
        return obj.user.stages if obj.user and obj.user.stages else []


class AddMemberSerializer(serializers.Serializer):
    mobile = serializers.CharField(max_length=20)
    display_name = serializers.CharField(max_length=64, required=False)
    role = serializers.ChoiceField(choices=['admin', 'teacher'])
    subject = serializers.CharField(max_length=20, required=False, allow_blank=True)
    stages = serializers.ListField(child=serializers.CharField(), required=False, default=list)

    def create(self, validated_data):
        institution = self.context['institution']
        mobile = validated_data['mobile']
        display_name = validated_data.get('display_name', '')
        role = validated_data['role']
        subject = validated_data.get('subject', '')
        stages = validated_data.get('stages', [])

        # Get or create the UserAccount
        user, created = UserAccount.objects.get_or_create(
            mobile=mobile,
            defaults={
                'display_name': display_name or mobile,
                'role_type': role,
                'subject': subject if subject else None,
                'stages': stages if stages else None,
            },
        )

        # Update stages if user already existed
        if not created and stages:
            user.stages = stages
            user.save(update_fields=['stages'])

        member, created = InstitutionMember.objects.get_or_create(
            institution=institution,
            user=user,
            defaults={'role': role, 'status': 'active'},
        )
        # Reactivate if member was previously removed
        if not created and member.status != 'active':
            member.status = 'active'
            member.role = role
            member.save(update_fields=['status', 'role'])
        return member


# ──────────────────────────────────────────────
# Class serializers
# ──────────────────────────────────────────────

class ClassListSerializer(serializers.ModelSerializer):
    student_count = serializers.SerializerMethodField()
    pending_request_count = serializers.SerializerMethodField()

    class Meta:
        model = Class
        fields = [
            'id', 'class_no', 'class_name', 'description', 'max_students',
            'invite_code', 'allow_invite_join', 'status', 'student_count',
            'pending_request_count', 'created_at', 'updated_at',
        ]

    def get_student_count(self, obj):
        return obj.class_students.filter(status='active').count()

    def get_pending_request_count(self, obj):
        return obj.join_requests.filter(status='pending').count()


class ClassDetailSerializer(serializers.ModelSerializer):
    institution_name = serializers.SerializerMethodField()
    creator_name = serializers.SerializerMethodField()
    student_count = serializers.SerializerMethodField()
    teachers = serializers.SerializerMethodField()

    class Meta:
        model = Class
        fields = [
            'id', 'class_no', 'class_name', 'description', 'max_students',
            'invite_code', 'allow_invite_join', 'status', 'institution_name',
            'creator_name', 'student_count', 'teachers', 'created_at',
            'updated_at',
        ]

    def get_institution_name(self, obj):
        return obj.institution.institution_name if obj.institution else None

    def get_creator_name(self, obj):
        if obj.creator_teacher:
            return obj.creator_teacher.display_name
        return None

    def get_student_count(self, obj):
        return obj.class_students.filter(status='active').count()

    def get_teachers(self, obj):
        rels = obj.class_teachers.select_related('teacher').all()
        return [
            {
                'id': r.teacher.id,
                'display_name': r.teacher.display_name,
                'role': r.role,
            }
            for r in rels
        ]


class CreateClassSerializer(serializers.ModelSerializer):
    class Meta:
        model = Class
        fields = ['class_name', 'description', 'max_students',
                  'allow_invite_join']

    def create(self, validated_data):
        validated_data['institution_id'] = self.context['institution_id']
        validated_data['creator_teacher'] = self.context['request'].user
        return super().create(validated_data)


class UpdateClassSerializer(serializers.ModelSerializer):
    class Meta:
        model = Class
        fields = ['class_name', 'description', 'max_students',
                  'allow_invite_join', 'status']


# ──────────────────────────────────────────────
# Class student serializers
# ──────────────────────────────────────────────

class ClassStudentSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    student_mobile = serializers.SerializerMethodField()

    class Meta:
        model = ClassStudent
        fields = ['id', 'class_obj', 'student', 'join_type', 'status',
                  'joined_at', 'student_name', 'student_mobile']

    def get_student_name(self, obj):
        return obj.student.display_name if obj.student else None

    def get_student_mobile(self, obj):
        return obj.student.mobile if obj.student else None


# ──────────────────────────────────────────────
# Join request serializers
# ──────────────────────────────────────────────

class ClassJoinRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClassJoinRequest
        fields = [
            'id', 'class_obj', 'applicant', 'applicant_name',
            'applicant_phone', 'request_type', 'status', 'message',
            'handled_by', 'handled_at', 'created_at',
        ]


class CreateJoinRequestSerializer(serializers.Serializer):
    class_id = serializers.IntegerField()
    applicant_name = serializers.CharField(max_length=100)
    applicant_phone = serializers.CharField(
        max_length=20, required=False, allow_blank=True,
    )
    request_type = serializers.ChoiceField(
        choices=['invite_code', 'self_apply'],
    )
    message = serializers.CharField(
        required=False, allow_blank=True, default='',
    )

    def validate(self, data):
        class_id = data.pop('class_id')
        request = self.context['request']
        user = request.user

        # Check class exists
        try:
            cls = Class.objects.get(id=class_id)
        except Class.DoesNotExist:
            raise serializers.ValidationError(
                {'class_id': 'Class not found'},
            )

        # Check not already a member
        if ClassStudent.objects.filter(
            class_obj=cls, student=user, status='active',
        ).exists():
            raise serializers.ValidationError(
                'You are already a member of this class',
            )

        # Check no pending request
        if ClassJoinRequest.objects.filter(
            class_obj=cls, applicant=user, status='pending',
        ).exists():
            raise serializers.ValidationError(
                'You already have a pending request for this class',
            )

        data['class_obj'] = cls
        return data

    def create(self, validated_data):
        validated_data['applicant'] = self.context['request'].user
        return ClassJoinRequest.objects.create(**validated_data)


# ──────────────────────────────────────────────
# Search / join serializers
# ──────────────────────────────────────────────

class SearchClassesSerializer(serializers.Serializer):
    teacher_mobile = serializers.CharField(max_length=20)

    def to_representation(self, instance):
        """instance is a queryset of open Classes for a teacher."""
        return ClassListSerializer(instance, many=True).data


class MyClassesSerializer(serializers.Serializer):
    """Serializes a ClassStudent with class info."""

    def to_representation(self, instance):
        """instance is a ClassStudent queryset item."""
        class_obj = instance.class_obj
        creator = class_obj.creator_teacher
        return {
            'id': instance.id,
            'class_id': instance.class_obj_id,
            'class_no': class_obj.class_no,
            'class_name': class_obj.class_name,
            'description': class_obj.description,
            'status': class_obj.status,
            'join_type': instance.join_type,
            'joined_at': instance.joined_at,
            'institution_name': (
                class_obj.institution.institution_name
                if class_obj.institution else None
            ),
            'subject': creator.subject if creator else None,
            'student_count': class_obj.class_students.filter(status='active').count(),
        }


class JoinByCodeSerializer(serializers.Serializer):
    invite_code = serializers.CharField(max_length=8)
    applicant_name = serializers.CharField(max_length=100)
    applicant_phone = serializers.CharField(
        max_length=20, required=False, allow_blank=True,
    )

    def validate(self, data):
        invite_code = data['invite_code']
        user = self.context['request'].user

        # Find class by invite code
        try:
            cls = Class.objects.get(invite_code=invite_code)
        except Class.DoesNotExist:
            raise serializers.ValidationError(
                {'invite_code': 'Invalid invite code'},
            )

        # Check allow_invite_join is enabled
        if not cls.allow_invite_join:
            raise serializers.ValidationError(
                'This class does not allow invite code joining',
            )

        # Check max students (0 means unlimited)
        max_students = cls.max_students
        if max_students > 0:
            current_count = cls.class_students.filter(
                status='active',
            ).count()
            if current_count >= max_students:
                raise serializers.ValidationError(
                    'This class has reached its maximum student capacity',
                )

        # Check not already a member
        if ClassStudent.objects.filter(
            class_obj=cls, student=user, status='active',
        ).exists():
            raise serializers.ValidationError(
                'You are already a member of this class',
            )

        data['class_obj'] = cls
        return data

    def create(self, validated_data):
        cls = validated_data['class_obj']
        user = self.context['request'].user

        student, created = ClassStudent.objects.get_or_create(
            class_obj=cls,
            student=user,
            defaults={
                'join_type': 'invite',
                'status': 'active',
            },
        )
        return student
