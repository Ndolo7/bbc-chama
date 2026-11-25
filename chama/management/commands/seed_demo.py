"""
Reset the guest demo database with fresh fictional data.

Usage:
    python manage.py seed_demo
"""
from django.core.management.base import BaseCommand

from chama.demo import seed_demo_data


class Command(BaseCommand):
    help = 'Wipe and reseed the guest demo database with fictional data'

    def handle(self, *args, **options):
        members, contributions = seed_demo_data()
        self.stdout.write(self.style.SUCCESS(
            f'Demo database seeded: {members} members, {contributions} contributions.'
        ))
