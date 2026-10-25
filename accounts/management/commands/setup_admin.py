import os
from django.core.management.base import BaseCommand
from accounts.models import User


class Command(BaseCommand):
    help = "Sets up the initial administrative superuser account idempotently."

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            default=os.getenv('ADMIN_USERNAME', 'Abhiadmin@17'),
            help='Admin username (default: Abhiadmin@17)'
        )
        parser.add_argument(
            '--password',
            default=os.getenv('ADMIN_PASSWORD', 'Abhi@17'),
            help='Admin password (default: Abhi@17)'
        )
        parser.add_argument(
            '--email',
            default=os.getenv('ADMIN_EMAIL', 'admin@library.com'),
            help='Admin email address'
        )

    def handle(self, *args, **options):
        username = options['username']
        password = options['password']
        email = options['email']

        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                'email': email,
                'first_name': 'Abhishek',
                'last_name': 'Admin',
                'role': User.ROLE_ADMIN,
                'is_staff': True,
                'is_superuser': True,
                'is_active': True,
            }
        )

        user.set_password(password)
        user.role = User.ROLE_ADMIN
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        user.email = email
        user.save()

        if created:
            self.stdout.write(self.style.SUCCESS(f"Initial Admin account '{username}' created successfully."))
        else:
            self.stdout.write(self.style.SUCCESS(f"Initial Admin account '{username}' already exists; verified and updated successfully."))
