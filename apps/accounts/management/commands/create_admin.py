"""Create an admin user for initial system setup."""
from django.core.management.base import BaseCommand

from apps.accounts.models import UserAccount
from apps.accounts.roles import grant_user_role


class Command(BaseCommand):
    help = 'Create a system admin user (or reset password if exists)'

    def add_arguments(self, parser):
        parser.add_argument('mobile', type=str, help='Admin mobile number')
        parser.add_argument('display_name', type=str, help='Admin display name')
        parser.add_argument(
            '--code', type=str, default='123456',
            help='SMS verification code to use for login (default: 123456)',
        )

    def handle(self, *args, **options):
        mobile = options['mobile']
        display_name = options['display_name']
        code = options['code']

        from django.core.cache import cache
        cache.set(f'sms_code:{mobile}', code, timeout=86400)  # 24h

        user, created = UserAccount.objects.get_or_create(
            mobile=mobile,
            defaults={
                'role_type': 'admin',
                'display_name': display_name,
                'status': 'active',
            },
        )
        grant_user_role(user, 'admin')
        if not created:
            self.stdout.write(
                self.style.WARNING(f'Admin grant for {display_name} ({mobile}) is ready'),
            )

        self.stdout.write(self.style.SUCCESS(
            f'Admin user ready: {mobile} / {display_name}',
        ))
        self.stdout.write(self.style.SUCCESS(
            f'Login with code: {code}',
        ))
