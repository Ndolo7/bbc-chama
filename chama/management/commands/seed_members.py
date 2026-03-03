"""
Management command to seed the 4 chama members.

Usage:
    python manage.py seed_members
    python manage.py seed_members --email-ndolo ndolo@example.com ...
"""
from django.core.management.base import BaseCommand
from datetime import date
from chama.models import Member, MonthlyTarget


MEMBERS = [
    {'name': 'Ndolo', 'email': ''},
    {'name': 'Njau', 'email': ''},
    {'name': 'Patrick', 'email': ''},
    {'name': 'Timothy', 'email': ''},
]


class Command(BaseCommand):
    help = 'Seed the four BBC Chama members and the initial monthly target'

    def add_arguments(self, parser):
        parser.add_argument('--email-ndolo', default='', help='Email for Ndolo')
        parser.add_argument('--email-njau', default='', help='Email for Njau')
        parser.add_argument('--email-patrick', default='', help='Email for Patrick')
        parser.add_argument('--email-timothy', default='', help='Email for Timothy')
        parser.add_argument('--target', type=int, default=5000, help='Monthly target (KES)')

    def handle(self, *args, **options):
        emails = {
            'Ndolo': options['email_ndolo'],
            'Njau': options['email_njau'],
            'Patrick': options['email_patrick'],
            'Timothy': options['email_timothy'],
        }
        joined = date(2025, 8, 1)

        for data in MEMBERS:
            name = data['name']
            email = emails.get(name, '') or f'{name.lower()}@placeholder.com'
            member, created = Member.objects.get_or_create(
                name=name,
                defaults={'email': email, 'joined_month': joined},
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'  Created member: {name} <{email}>'))
            else:
                self.stdout.write(f'  Member already exists: {name}')

        # Create initial monthly target
        target, created = MonthlyTarget.objects.get_or_create(
            effective_from=joined,
            defaults={'amount': options['target']},
        )
        if created:
            self.stdout.write(self.style.SUCCESS(
                f'  Created monthly target: KES {options["target"]:,} from Aug 2025'
            ))
        else:
            self.stdout.write(f'  Monthly target already set: KES {target.amount:,}')

        self.stdout.write(self.style.SUCCESS('\nDone! Update member emails via Django admin at /admin/'))
