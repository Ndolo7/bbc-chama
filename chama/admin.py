from django.contrib import admin
from .models import Member, Contribution, MonthlyTarget


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'joined_month', 'is_active', 'total_contributed')
    list_filter = ('is_active',)
    search_fields = ('name', 'email')


@admin.register(Contribution)
class ContributionAdmin(admin.ModelAdmin):
    list_display = ('member', 'contribution_month', 'amount', 'mpesa_code', 'transaction_date', 'sms_source')
    list_filter = ('member', 'contribution_month', 'sms_source')
    search_fields = ('mpesa_code', 'member__name')
    date_hierarchy = 'transaction_date'
    ordering = ('-transaction_date',)


@admin.register(MonthlyTarget)
class MonthlyTargetAdmin(admin.ModelAdmin):
    list_display = ('amount', 'effective_from')
