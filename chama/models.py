from django.db import models
from django.conf import settings


class Member(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    is_active = models.BooleanField(default=True)
    joined_month = models.DateField(help_text='First month they contributed (YYYY-MM-01)')

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def total_contributed(self):
        return self.contributions.aggregate(
            total=models.Sum('amount')
        )['total'] or 0

    def months_contributed(self):
        return self.contributions.values('contribution_month').distinct().count()

    def has_contributed_for(self, year, month):
        from datetime import date
        month_start = date(year, month, 1)
        return self.contributions.filter(contribution_month=month_start).exists()


class MonthlyTarget(models.Model):
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    effective_from = models.DateField(help_text='First month this target applies (YYYY-MM-01)')

    class Meta:
        ordering = ['-effective_from']

    def __str__(self):
        return f'KES {self.amount:,.0f} from {self.effective_from.strftime("%b %Y")}'

    @classmethod
    def for_month(cls, year, month):
        from datetime import date
        month_start = date(year, month, 1)
        target = cls.objects.filter(effective_from__lte=month_start).first()
        if target:
            return target.amount
        return settings.CHAMA_MONTHLY_TARGET


class Contribution(models.Model):
    SMS_SOURCE_MPESA = 'mpesa'
    SMS_SOURCE_CYTONN = 'cytonn'
    SMS_SOURCE_MANUAL = 'manual'
    SMS_SOURCE_CHOICES = [
        (SMS_SOURCE_MPESA, 'M-Pesa'),
        (SMS_SOURCE_CYTONN, 'Cytonn'),
        (SMS_SOURCE_MANUAL, 'Manual entry'),
    ]

    member = models.ForeignKey(Member, on_delete=models.CASCADE, related_name='contributions')
    mpesa_code = models.CharField(max_length=20, unique=True, help_text='M-Pesa transaction code')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_date = models.DateTimeField(help_text='Date & time from the SMS')
    contribution_month = models.DateField(
        help_text='Month this payment counts for (YYYY-MM-01)',
    )
    sms_text = models.TextField(blank=True, help_text='Original SMS pasted by admin')
    sms_source = models.CharField(max_length=10, choices=SMS_SOURCE_CHOICES, default=SMS_SOURCE_MPESA)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-transaction_date']
        unique_together = [('member', 'contribution_month')]

    def __str__(self):
        return f'{self.member.name} – {self.contribution_month.strftime("%b %Y")} – KES {self.amount:,.0f}'
