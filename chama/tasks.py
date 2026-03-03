from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from datetime import date
import calendar


def _get_current_target_month():
    """Return (year, month) for the month members should have paid for."""
    today = date.today()
    # Between 3rd and 15th: reminder is for the PREVIOUS month
    if 3 <= today.day <= 15:
        first_of_current = date(today.year, today.month, 1)
        prev = first_of_current.replace(day=1)
        import datetime
        prev = (first_of_current - datetime.timedelta(days=1)).replace(day=1)
        return prev.year, prev.month
    return today.year, today.month


@shared_task
def send_monthly_reminders():
    """
    Daily task: if today is between 3rd–15th of month, send individual
    reminder emails to members who haven't paid for the previous month.
    """
    from .models import Member, Contribution, MonthlyTarget

    today = date.today()
    if not (3 <= today.day <= 15):
        return 'Not in reminder window (3rd–15th). Skipping.'

    year, month = _get_current_target_month()
    month_start = date(year, month, 1)
    month_name = month_start.strftime('%B %Y')

    members = Member.objects.filter(is_active=True)
    reminded = []

    for member in members:
        paid = Contribution.objects.filter(
            member=member, contribution_month=month_start
        ).exists()
        if not paid:
            target = MonthlyTarget.for_month(year, month)
            context = {
                'member': member,
                'month_name': month_name,
                'target': target,
                'today': today,
            }
            html_body = render_to_string('chama/emails/reminder.html', context)
            text_body = render_to_string('chama/emails/reminder.txt', context)
            send_mail(
                subject=f'[BBC Chama] Reminder: {month_name} contribution pending',
                message=text_body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[member.email],
                html_message=html_body,
                fail_silently=False,
            )
            reminded.append(member.name)

    if reminded:
        return f'Reminders sent to: {", ".join(reminded)}'
    return f'All members have paid for {month_name}. No reminders sent.'


@shared_task
def send_monthly_report():
    """
    Runs on 1st of each month: sends a report summarising the previous month.
    """
    from .models import Member, Contribution, MonthlyTarget

    today = date.today()
    # Report covers the previous month
    first_of_current = date(today.year, today.month, 1)
    import datetime
    prev_month_end = first_of_current - datetime.timedelta(days=1)
    prev_month_start = date(prev_month_end.year, prev_month_end.month, 1)
    year, month = prev_month_start.year, prev_month_start.month
    month_name = prev_month_start.strftime('%B %Y')

    members = Member.objects.filter(is_active=True)
    target = MonthlyTarget.for_month(year, month)
    total_expected = float(target) * members.count()

    member_data = []
    total_collected = 0
    for member in members:
        contrib = Contribution.objects.filter(
            member=member, contribution_month=prev_month_start
        ).first()
        amount = float(contrib.amount) if contrib else 0
        total_collected += amount
        member_data.append({
            'member': member,
            'paid': contrib is not None,
            'amount': amount,
            'shortfall': max(0, float(target) - amount),
        })

    context = {
        'month_name': month_name,
        'member_data': member_data,
        'total_collected': total_collected,
        'total_expected': total_expected,
        'deficit': max(0, total_expected - total_collected),
        'target': target,
        'today': today,
    }
    html_body = render_to_string('chama/emails/monthly_report.html', context)
    text_body = render_to_string('chama/emails/monthly_report.txt', context)

    all_emails = list(members.values_list('email', flat=True))
    send_mail(
        subject=f'[BBC Chama] Monthly Report – {month_name}',
        message=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=all_emails,
        html_message=html_body,
        fail_silently=False,
    )
    return f'Monthly report for {month_name} sent to {len(all_emails)} members.'


@shared_task
def send_end_of_month_reminder():
    """
    Runs on the 28th of each month: reminds members who haven't paid yet
    for the CURRENT month (deadline approaching).
    """
    from .models import Member, Contribution, MonthlyTarget

    today = date.today()
    month_start = date(today.year, today.month, 1)
    month_name = month_start.strftime('%B %Y')
    days_left = calendar.monthrange(today.year, today.month)[1] - today.day

    members = Member.objects.filter(is_active=True)
    target = MonthlyTarget.for_month(today.year, today.month)
    reminded = []

    for member in members:
        paid = Contribution.objects.filter(
            member=member, contribution_month=month_start
        ).exists()
        if not paid:
            context = {
                'member': member,
                'month_name': month_name,
                'target': target,
                'days_left': days_left,
                'today': today,
                'is_end_of_month': True,
            }
            html_body = render_to_string('chama/emails/reminder.html', context)
            text_body = render_to_string('chama/emails/reminder.txt', context)
            send_mail(
                subject=f'[BBC Chama] {days_left} days left – send your {month_name} contribution!',
                message=text_body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[member.email],
                html_message=html_body,
                fail_silently=False,
            )
            reminded.append(member.name)

    if reminded:
        return f'End-of-month reminders sent to: {", ".join(reminded)}'
    return f'All members paid for {month_name}. No end-of-month reminder needed.'
