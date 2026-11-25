"""
Guest demo mode.

Guests who click "Try the demo" on the login page are signed in as a shared,
password-less demo user. Every query for the ``chama`` app made while serving
that user is routed to a separate database (``settings.DEMO_DB_ALIAS``), which
is filled with fictional members and contributions. Real chama data is never
read or written in demo mode.

Pieces:
- ``DemoRouter``            – database router (settings.DATABASE_ROUTERS)
- ``DemoDatabaseMiddleware`` – switches routing on for the demo user's requests
- ``ensure_demo_data``      – (re)seeds the demo database when stale
- ``sample_sms``            – a parseable fake SMS for the Add Contribution page
"""
import random
import string
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.conf import settings
from django.core.management import call_command
from django.db import connections, transaction
from django.utils import timezone

DEMO_APPS = {'chama'}

_demo_active = ContextVar('chama_demo_active', default=False)


def demo_db_alias():
    return getattr(settings, 'DEMO_DB_ALIAS', 'demo')


def is_demo_user(user):
    return bool(
        user is not None
        and user.is_authenticated
        and user.get_username() == settings.DEMO_USERNAME
    )


def demo_active():
    return _demo_active.get()


@contextmanager
def use_demo_db():
    """Route all chama queries inside this block to the demo database."""
    token = _demo_active.set(True)
    try:
        yield
    finally:
        _demo_active.reset(token)


class DemoRouter:
    def _route(self, model):
        if model._meta.app_label in DEMO_APPS and _demo_active.get():
            return demo_db_alias()
        return None

    def db_for_read(self, model, **hints):
        return self._route(model)

    def db_for_write(self, model, **hints):
        return self._route(model)

    def allow_migrate(self, db, app_label, **hints):
        # The demo database only ever holds chama tables.
        if db == demo_db_alias():
            return app_label in DEMO_APPS
        return None


class DemoDatabaseMiddleware:
    """Must come after AuthenticationMiddleware."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if is_demo_user(getattr(request, 'user', None)):
            with use_demo_db():
                return self.get_response(request)
        return self.get_response(request)


# ── Seeding ──────────────────────────────────────────────────────────────────

DEMO_MEMBERS = [
    # (name, probability of paying in any given month)
    ('Amina Wanjiru', 0.97),
    ('Brian Otieno', 0.92),
    ('Faith Mwangi', 0.85),
    ('Kevin Kiprop', 0.9),
    ('Grace Achieng', 0.75),
]


def _demo_targets():
    """Fictional target history: base target, raised by 1,000 from the 6th month."""
    start = date.fromisoformat(settings.CHAMA_START_MONTH)
    base = Decimal(settings.CHAMA_MONTHLY_TARGET)
    y, m = start.year, start.month + 5
    y, m = y + (m - 1) // 12, (m - 1) % 12 + 1
    return [(start, base), (date(y, m, 1), base + 1000)]


def _target_for(targets, month_start):
    applicable = [amt for eff, amt in targets if eff <= month_start]
    return applicable[-1] if applicable else targets[0][1]


def _months_until(today):
    start = date.fromisoformat(settings.CHAMA_START_MONTH)
    y, m = start.year, start.month
    months = []
    while (y, m) <= (today.year, today.month):
        months.append(date(y, m, 1))
        m += 1
        if m > 12:
            y, m = y + 1, 1
    return months


def _next_month(d):
    return date(d.year + (d.month // 12), d.month % 12 + 1, 1)


def _mpesa_code(rng):
    return rng.choice('QRSTU') + ''.join(rng.choices(string.ascii_uppercase + string.digits, k=9))


def _mpesa_sms(code, amount, dt):
    return (
        f'{code} Confirmed. Ksh{amount:,.2f} sent to CYTONN HIGH YIELD FUND '
        f'on {dt.day}/{dt.month}/{dt:%y} at {dt:%I:%M %p}.'
    )


def _cytonn_sms(code, amount, dt):
    return (
        f'Your deposit of KES {amount:,.2f} in Cytonn High Yield Fund was successful. '
        f'Transaction ID: {code}. Date: {dt:%d-%b-%Y}'
    )


def seed_demo_data(today=None):
    """Wipe the demo database and fill it with fresh fictional data."""
    from .models import Member, MonthlyTarget, Contribution

    alias = demo_db_alias()
    if 'chama_member' not in connections[alias].introspection.table_names():
        call_command('migrate', 'chama', database=alias, verbosity=0, interactive=False)

    now = timezone.localtime()
    today = today or now.date()
    rng = random.Random(f'bbc-chama-demo-{today:%Y-%m}')
    months = _months_until(today)
    prev_month = months[-2] if len(months) > 1 else None
    targets = _demo_targets()

    with use_demo_db(), transaction.atomic(using=alias):
        Contribution.objects.all().delete()
        Member.objects.all().delete()
        MonthlyTarget.objects.all().delete()

        MonthlyTarget.objects.bulk_create(
            MonthlyTarget(effective_from=eff, amount=amt) for eff, amt in targets
        )
        members = Member.objects.bulk_create(
            Member(
                name=name,
                email=f'{name.split()[0].lower()}@example.com',
                joined_month=months[0],
            )
            for name, _ in DEMO_MEMBERS
        )

        used_codes = set()
        contributions = []
        for idx, (member, (_, reliability)) in enumerate(zip(members, DEMO_MEMBERS)):
            for month_start in months:
                # Leave gaps the guest can fill in themselves: the last two
                # members haven't paid for last month yet.
                if month_start == prev_month and idx >= len(members) - 2:
                    continue
                if rng.random() > reliability:
                    continue

                # Paid between the 15th of the month and the 10th of the next.
                if rng.random() < 0.5:
                    day = date(month_start.year, month_start.month, rng.randint(15, 28))
                else:
                    nxt = _next_month(month_start)
                    day = date(nxt.year, nxt.month, rng.randint(1, 10))
                naive = datetime(day.year, day.month, day.day, rng.randint(7, 21), rng.randint(0, 59))
                txn = timezone.make_aware(naive)
                if txn > now:
                    continue

                target = _target_for(targets, month_start)
                roll = rng.random()
                amount, notes = target, ''
                if roll < 0.08:
                    amount, notes = target - 1000, 'Partial payment – balance to follow.'
                elif roll < 0.12:
                    amount, notes = target + 1000, 'Paid extra this month.'

                if rng.random() < 0.8:
                    source = Contribution.SMS_SOURCE_MPESA
                    code = _mpesa_code(rng)
                    while code in used_codes:
                        code = _mpesa_code(rng)
                    sms = _mpesa_sms(code, amount, naive)
                else:
                    source = Contribution.SMS_SOURCE_CYTONN
                    code = f'CYT{rng.randint(100000, 999999)}'
                    while code in used_codes:
                        code = f'CYT{rng.randint(100000, 999999)}'
                    sms = _cytonn_sms(code, amount, naive)
                used_codes.add(code)

                contributions.append(Contribution(
                    member=member,
                    mpesa_code=code,
                    amount=amount,
                    transaction_date=txn,
                    contribution_month=month_start,
                    sms_text=sms,
                    sms_source=source,
                    notes=notes,
                ))
        Contribution.objects.bulk_create(contributions)
    return len(members), len(contributions)


def _seeded_at():
    """Seed time = earliest created_at (guest-added rows are always newer)."""
    from .models import Contribution

    alias = demo_db_alias()
    if 'chama_contribution' not in connections[alias].introspection.table_names():
        return None
    with use_demo_db():
        return (
            Contribution.objects.order_by('created_at')
            .values_list('created_at', flat=True).first()
        )


def ensure_demo_data():
    """Reseed the demo database if empty, older than DEMO_RESET_HOURS, or from a previous month."""
    seeded = _seeded_at()
    now = timezone.localtime()
    stale = (
        seeded is None
        or now - seeded > timedelta(hours=settings.DEMO_RESET_HOURS)
        or timezone.localtime(seeded).strftime('%Y-%m') != now.strftime('%Y-%m')
    )
    if stale:
        seed_demo_data()
    return stale


def sample_sms():
    """A fresh, parseable M-Pesa SMS dated now (counts for last month)."""
    from .models import Contribution, MonthlyTarget

    rng = random.Random()
    now = timezone.localtime().replace(tzinfo=None)
    code = _mpesa_code(rng)
    while Contribution.objects.filter(mpesa_code=code).exists():
        code = _mpesa_code(rng)
    first = date(now.year, now.month, 1)
    prev = first - timedelta(days=1)
    amount = MonthlyTarget.for_month(prev.year, prev.month)
    return _mpesa_sms(code, Decimal(amount), now)
