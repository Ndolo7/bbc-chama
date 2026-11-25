from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .demo import ensure_demo_data, sample_sms, seed_demo_data, use_demo_db
from .models import Contribution, Member, MonthlyTarget
from .parsers import parse_sms_text


class DemoModeTests(TestCase):
    databases = {'default', 'demo'}

    def setUp(self):
        self.real_member = Member.objects.create(
            name='RealPerson', email='real@example.org', joined_month=date(2025, 8, 1),
        )
        self.real_user = get_user_model().objects.create_user('treasurer', password='pw-12345!')

    def demo_login(self):
        return self.client.post(reverse('demo_login'))

    def test_demo_login_signs_in_and_seeds_isolated_data(self):
        resp = self.demo_login()
        self.assertRedirects(resp, reverse('chama:dashboard'))

        demo_user = get_user_model().objects.get(username='demo')
        self.assertFalse(demo_user.has_usable_password())
        self.assertFalse(demo_user.is_staff)

        # Demo data is in the demo DB only; the real DB is untouched.
        self.assertEqual(list(Member.objects.values_list('name', flat=True)), ['RealPerson'])
        self.assertFalse(Contribution.objects.exists())
        self.assertGreater(Member.objects.using('demo').count(), 0)
        self.assertGreater(Contribution.objects.using('demo').count(), 0)
        self.assertFalse(Member.objects.using('demo').filter(name='RealPerson').exists())

    def test_demo_user_sees_only_demo_data(self):
        self.demo_login()
        for url in [reverse('chama:dashboard'), reverse('chama:contributions'),
                    reverse('chama:reports'), reverse('chama:reports_all')]:
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 200, url)
            self.assertNotContains(resp, 'RealPerson')
            self.assertNotContains(resp, '80224053')
            self.assertContains(resp, 'Demo mode')
        demo_member = Member.objects.using('demo').first()
        resp = self.client.get(reverse('chama:member_detail', args=[demo_member.pk]))
        self.assertContains(resp, demo_member.name)

    def test_real_user_never_sees_demo_data(self):
        self.demo_login()
        self.client.logout()
        self.client.login(username='treasurer', password='pw-12345!')
        resp = self.client.get(reverse('chama:dashboard'))
        self.assertContains(resp, 'RealPerson')
        self.assertNotContains(resp, 'Amina Wanjiru')
        self.assertNotContains(resp, 'Demo mode')

    def test_demo_contribution_is_saved_to_demo_db(self):
        self.demo_login()
        resp = self.client.get(reverse('chama:add_contribution'))
        sms = resp.context['demo_sample_sms']
        parsed = self.client.post(reverse('chama:parse_sms'), {'sms_text': sms}).json()
        self.assertTrue(parsed['ok'])

        # The seed leaves the last members unpaid for last month.
        month = date.fromisoformat(parsed['contribution_month'])
        with use_demo_db():
            unpaid = Member.objects.exclude(contributions__contribution_month=month).first()
        before = Contribution.objects.using('demo').count()
        resp = self.client.post(reverse('chama:add_contribution'), {
            'member': unpaid.pk,
            'mpesa_code': parsed['code'],
            'amount': parsed['amount'],
            'transaction_date': parsed['transaction_date'][:16],
            'contribution_month': parsed['contribution_month'][:7],
            'sms_source': parsed['source'],
            'sms_text': sms,
        })
        self.assertRedirects(resp, reverse('chama:dashboard'))
        self.assertEqual(Contribution.objects.using('demo').count(), before + 1)
        self.assertFalse(Contribution.objects.exists())

    def test_demo_user_cannot_delete_or_use_admin(self):
        self.demo_login()
        contrib = Contribution.objects.using('demo').first()
        resp = self.client.post(reverse('chama:delete_contribution', args=[contrib.pk]))
        self.assertEqual(resp.status_code, 403)
        resp = self.client.get('/admin/')
        self.assertEqual(resp.status_code, 302)

    def test_demo_login_requires_post(self):
        self.assertEqual(self.client.get(reverse('demo_login')).status_code, 405)

    @override_settings(DEMO_ENABLED=False)
    def test_demo_disabled(self):
        self.assertEqual(self.demo_login().status_code, 404)
        self.assertNotContains(self.client.get(reverse('login')), 'Try the demo')

    def test_login_page_shows_demo_button(self):
        self.assertContains(self.client.get(reverse('login')), 'Try the demo')

    def test_repeat_logins_keep_data_and_sessions(self):
        self.demo_login()
        other = self.client_class()
        other.post(reverse('demo_login'))
        self.assertFalse(ensure_demo_data())  # fresh – not reseeded
        self.assertEqual(self.client.get(reverse('chama:dashboard')).status_code, 200)

    def test_stale_demo_data_is_reseeded(self):
        seed_demo_data()
        with use_demo_db():
            Contribution.objects.update(created_at=timezone.now() - timedelta(days=2))
        self.assertTrue(ensure_demo_data())

    def test_seed_covers_every_month_and_targets(self):
        seed_demo_data()
        with use_demo_db():
            self.assertEqual(MonthlyTarget.objects.count(), 2)
            months = set(Contribution.objects.values_list('contribution_month', flat=True))
            for c in Contribution.objects.all():
                parse_sms_text(c.sms_text)  # stored SMS texts are realistic/parseable
        self.assertIn(date(2025, 8, 1), months)

    def test_sample_sms_parses_to_last_month(self):
        seed_demo_data()
        with use_demo_db():
            parsed = parse_sms_text(sample_sms())
        today = date.today()
        last = date(today.year, today.month, 1) - timedelta(days=1)
        self.assertEqual(parsed['contribution_month'], date(last.year, last.month, 1).isoformat())
