from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Sum, Count
from django.utils import timezone
from datetime import date, timedelta
import calendar
import json

from .models import Member, Contribution, MonthlyTarget
from .forms import SMSPasteForm, ContributionConfirmForm
from .parsers import parse_sms_text, ParseError


def _month_range_from_start():
    """Return list of (year, month) tuples from Aug 2025 to current month."""
    from django.conf import settings
    start = date.fromisoformat(settings.CHAMA_START_MONTH)
    today = date.today()
    months = []
    y, m = start.year, start.month
    while (y, m) <= (today.year, today.month):
        months.append((y, m))
        m += 1
        if m > 12:
            m = 1
            y += 1
    return months


@login_required
def dashboard(request):
    today = date.today()
    year = int(request.GET.get('year', today.year))
    month = int(request.GET.get('month', today.month))
    month_start = date(year, month, 1)

    members = Member.objects.filter(is_active=True)
    target = MonthlyTarget.for_month(year, month)

    # Per-member status for selected month
    member_status = []
    for m in members:
        contrib = Contribution.objects.filter(
            member=m, contribution_month=month_start
        ).first()
        member_status.append({
            'member': m,
            'contribution': contrib,
            'paid': contrib is not None,
            'amount': contrib.amount if contrib else 0,
            'shortfall': max(0, target - (contrib.amount if contrib else 0)),
        })

    total_collected = sum(s['amount'] for s in member_status)
    total_expected = target * members.count()

    # Chart data: total contribution per member (all time)
    chart_labels = [m.name for m in members]
    chart_data = [float(m.total_contributed()) for m in members]

    # Recent contributions (all months)
    recent = Contribution.objects.select_related('member').order_by('-created_at')[:10]

    # Month navigation
    all_months = _month_range_from_start()
    prev_month = (year, month - 1) if month > 1 else (year - 1, 12)
    next_month = (year, month + 1) if month < 12 else (year + 1, 1)
    has_prev = prev_month in all_months
    has_next = next_month in all_months and next_month <= (today.year, today.month)

    return render(request, 'chama/dashboard.html', {
        'member_status': member_status,
        'total_collected': total_collected,
        'total_expected': total_expected,
        'target': target,
        'month_start': month_start,
        'month_name': month_start.strftime('%B %Y'),
        'recent': recent,
        'chart_labels': json.dumps(chart_labels),
        'chart_data': json.dumps(chart_data),
        'members': members,
        'has_prev': has_prev,
        'prev_year': prev_month[0],
        'prev_month': prev_month[1],
        'has_next': has_next,
        'next_year': next_month[0],
        'next_month': next_month[1],
    })


@login_required
def add_contribution(request):
    if request.method == 'POST':
        form = ContributionConfirmForm(request.POST)
        if form.is_valid():
            contribution = form.save()
            messages.success(
                request,
                f'Contribution recorded: {contribution.member.name} – KES {contribution.amount:,.0f} '
                f'for {contribution.contribution_month.strftime("%B %Y")}.'
            )
            return redirect('chama:dashboard')
    else:
        # Pre-fill from parsed data passed via GET params or session
        initial = request.session.pop('parsed_sms', None)
        form = ContributionConfirmForm(initial=initial)

    sms_form = SMSPasteForm()
    return render(request, 'chama/add_contribution.html', {
        'sms_form': sms_form,
        'form': form,
    })


@login_required
def parse_sms(request):
    """AJAX endpoint: parse SMS text, return extracted fields as JSON."""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    sms_text = request.POST.get('sms_text', '').strip()
    if not sms_text:
        return JsonResponse({'error': 'No SMS text provided'}, status=400)

    try:
        result = parse_sms_text(sms_text)
    except ParseError as e:
        return JsonResponse({'ok': False, 'error': str(e)}, status=400)

    # Reject if this transaction code is already recorded
    if Contribution.objects.filter(mpesa_code=result['code']).exists():
        existing = Contribution.objects.get(mpesa_code=result['code'])
        return JsonResponse({
            'ok': False,
            'error': (
                f'Transaction {result["code"]} is already recorded — '
                f'{existing.member.name}, '
                f'{existing.contribution_month.strftime("%B %Y")}, '
                f'KES {existing.amount:,.0f}.'
            ),
        }, status=400)

    return JsonResponse({'ok': True, **result})


@login_required
def contributions(request):
    qs = Contribution.objects.select_related('member').order_by('-transaction_date')

    member_filter = request.GET.get('member')
    month_filter = request.GET.get('month')  # YYYY-MM

    if member_filter:
        qs = qs.filter(member_id=member_filter)
    if month_filter:
        try:
            y, m = month_filter.split('-')
            qs = qs.filter(contribution_month=date(int(y), int(m), 1))
        except (ValueError, AttributeError):
            pass

    members = Member.objects.filter(is_active=True)
    all_months = _month_range_from_start()

    return render(request, 'chama/contributions.html', {
        'contributions': qs,
        'members': members,
        'all_months': all_months,
        'member_filter': member_filter,
        'month_filter': month_filter,
    })


@login_required
def member_detail(request, pk):
    member = get_object_or_404(Member, pk=pk)
    all_months = _month_range_from_start()
    contribs_by_month = {}

    for y, m in all_months:
        month_start = date(y, m, 1)
        contrib = member.contributions.filter(contribution_month=month_start).first()
        target = MonthlyTarget.for_month(y, m)
        contribs_by_month[(y, m)] = {
            'month_start': month_start,
            'month_name': month_start.strftime('%b %Y'),
            'contribution': contrib,
            'paid': contrib is not None,
            'amount': contrib.amount if contrib else 0,
            'target': target,
            'shortfall': max(0, target - (contrib.amount if contrib else 0)),
        }

    months_paid = sum(1 for v in contribs_by_month.values() if v['paid'])
    months_missed = len(all_months) - months_paid
    total_contributed = float(member.total_contributed())
    total_expected = float(sum(
        MonthlyTarget.for_month(y, m) for y, m in all_months
    ))

    return render(request, 'chama/member_detail.html', {
        'member': member,
        'contribs_by_month': contribs_by_month,
        'all_months': all_months,
        'months_paid': months_paid,
        'months_missed': months_missed,
        'total_contributed': total_contributed,
        'total_expected': total_expected,
        'deficit': max(0, total_expected - total_contributed),
    })


@login_required
def reports(request):
    today = date.today()
    year = int(request.GET.get('year', today.year))
    all_months_all_years = _month_range_from_start()
    year_months = [(y, m) for y, m in all_months_all_years if y == year]
    available_years = sorted(set(y for y, _ in all_months_all_years), reverse=True)

    members = Member.objects.filter(is_active=True)

    # Build matrix: member × month
    matrix = []
    monthly_totals = []
    for y, m in year_months:
        month_start = date(y, m, 1)
        target = MonthlyTarget.for_month(y, m)
        month_contribs = []
        month_total = 0
        for member in members:
            contrib = member.contributions.filter(contribution_month=month_start).first()
            amount = float(contrib.amount) if contrib else 0
            month_total += amount
            month_contribs.append({
                'member': member,
                'contribution': contrib,
                'paid': contrib is not None,
                'amount': amount,
            })
        monthly_totals.append({
            'month_start': month_start,
            'month_name': month_start.strftime('%b %Y'),
            'contributions': month_contribs,
            'total': month_total,
            'expected': float(target) * members.count(),
            'deficit': max(0, float(target) * members.count() - month_total),
        })

    # Per-member annual summary
    member_summaries = []
    for member in members:
        total = float(member.contributions.filter(
            contribution_month__year=year
        ).aggregate(s=Sum('amount'))['s'] or 0)
        expected = sum(float(MonthlyTarget.for_month(y, m)) for y, m in year_months)
        member_summaries.append({
            'member': member,
            'total': total,
            'expected': expected,
            'deficit': max(0, expected - total),
            'months_paid': member.contributions.filter(
                contribution_month__year=year
            ).count(),
        })

    grand_total = sum(ms['total'] for ms in member_summaries)
    grand_expected = sum(mt['expected'] for mt in monthly_totals)

    # Chart: monthly totals for bar chart
    chart_labels = json.dumps([mt['month_name'] for mt in monthly_totals])
    chart_actual = json.dumps([mt['total'] for mt in monthly_totals])
    chart_expected = json.dumps([mt['expected'] for mt in monthly_totals])

    return render(request, 'chama/reports.html', {
        'year': year,
        'available_years': available_years,
        'year_months': year_months,
        'monthly_totals': monthly_totals,
        'member_summaries': member_summaries,
        'members': members,
        'grand_total': grand_total,
        'grand_expected': grand_expected,
        'grand_deficit': max(0, grand_expected - grand_total),
        'chart_labels': chart_labels,
        'chart_actual': chart_actual,
        'chart_expected': chart_expected,
    })


@login_required
def delete_contribution(request, pk):
    contribution = get_object_or_404(Contribution, pk=pk)
    if request.method == 'POST':
        name = str(contribution)
        contribution.delete()
        messages.success(request, f'Deleted contribution: {name}')
        return redirect('chama:contributions')
    return render(request, 'chama/confirm_delete.html', {'contribution': contribution})
