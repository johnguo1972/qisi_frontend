"""Validate the production prerequisites for the practice beta rollout."""
from __future__ import annotations

import os
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder
from django.urls import reverse

from apps.practice.feature_flags import practice_feature_state


class Command(BaseCommand):
    help = '检查精练灰度发布所需的迁移、表、媒体目录和 feature flag 配置'

    def add_arguments(self, parser):
        parser.add_argument(
            '--strict', action='store_true',
            help='发现错误时以非零状态退出，适合 CI/CD 发布前检查',
        )

    def handle(self, *args, **options):
        errors = []
        warnings = []
        required_tables = {
            'practice_pool_item', 'practice_set', 'practice_set_item',
            'practice_attempt', 'practice_attempt_image',
        }
        tables = set(connection.introspection.table_names())
        if not MigrationRecorder(connection).migration_qs.filter(
            app='practice', name='0001_initial',
        ).exists():
            errors.append('practice.0001_initial 尚未应用')
        missing_tables = sorted(required_tables - tables)
        if missing_tables:
            errors.append(f'缺少精练数据表: {", ".join(missing_tables)}')

        feature = practice_feature_state()
        if not feature['enabled']:
            warnings.append('精练 feature flag 当前关闭（可作为回滚状态）')

        media_root = Path(settings.MEDIA_ROOT)
        if not media_root.exists():
            warnings.append(f'MEDIA_ROOT 不存在，将在上传/PDF生成时创建: {media_root}')
        elif not os.access(media_root, os.W_OK):
            errors.append(f'MEDIA_ROOT 不可写: {media_root}')

        try:
            reverse('practice:practice-health')
        except Exception as exc:
            errors.append(f'精练健康检查路由不可用: {exc}')

        self.stdout.write(self.style.SUCCESS('Practice release check'))
        self.stdout.write(f"feature={feature}")
        for warning in warnings:
            self.stdout.write(self.style.WARNING(f'WARN: {warning}'))
        for error in errors:
            self.stdout.write(self.style.ERROR(f'ERROR: {error}'))
        if errors and options['strict']:
            raise CommandError('精练灰度发布检查失败')
        if not errors:
            self.stdout.write(self.style.SUCCESS('OK: 可进入下一步灰度验证'))
