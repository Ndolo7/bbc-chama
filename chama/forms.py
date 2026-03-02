from django import forms
from datetime import date
from .models import Member, Contribution


class SMSPasteForm(forms.Form):
    sms_text = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 5,
            'class': 'form-control font-monospace',
            'placeholder': (
                'Paste the M-Pesa or Cytonn SMS here...\n\n'
                'Example (M-Pesa):\n'
                'QGH3K2P1R5 Confirmed. Ksh5,000.00 sent to CYTONN MONEY MARKET FUND on 31/8/25 at 10:30 AM.\n\n'
                'Example (Cytonn):\n'
                'Your deposit of KES 5,000.00 in Cytonn Money Market Fund was successful. '
                'Transaction ID: CYT123456. Date: 31-Aug-2025'
            ),
        }),
        label='Paste SMS',
    )


class ContributionConfirmForm(forms.ModelForm):
    class Meta:
        model = Contribution
        fields = ['member', 'mpesa_code', 'amount', 'transaction_date',
                  'contribution_month', 'sms_source', 'sms_text', 'notes']
        widgets = {
            'member': forms.Select(attrs={'class': 'form-select'}),
            # Parsed fields – readonly so values can only come from the SMS parser
            'mpesa_code': forms.TextInput(attrs={
                'class': 'form-control', 'readonly': True,
            }),
            'amount': forms.NumberInput(attrs={
                'class': 'form-control', 'step': '0.01', 'readonly': True,
            }),
            'transaction_date': forms.DateTimeInput(
                attrs={'class': 'form-control', 'type': 'datetime-local', 'readonly': True},
                format='%Y-%m-%dT%H:%M',
            ),
            'contribution_month': forms.DateInput(
                attrs={'class': 'form-control', 'type': 'month', 'readonly': True},
                format='%Y-%m',
            ),
            # Hidden – populated by JS after a successful parse
            'sms_source': forms.HiddenInput(),
            'sms_text': forms.HiddenInput(),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['member'].queryset = Member.objects.filter(is_active=True)
        self.fields['notes'].required = False
        self.fields['contribution_month'].input_formats = ['%Y-%m', '%Y-%m-%d']
        self.fields['transaction_date'].input_formats = [
            '%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M', '%Y-%m-%d',
        ]

    def clean_sms_text(self):
        val = self.cleaned_data.get('sms_text', '').strip()
        if not val:
            raise forms.ValidationError('An SMS must be parsed before saving a contribution.')
        return val

    def clean_contribution_month(self):
        val = self.cleaned_data['contribution_month']
        if isinstance(val, date):
            return date(val.year, val.month, 1)
        return val
