"""Tests for the staff-only monitoring_dashboard_view."""

from django.test import TestCase

from core.models import EmailLog, PBUser, Paper


class MonitoringDashboardTests(TestCase):
    """Access control (@staff_member_required) and aggregated context."""

    def setUp(self):
        self.staff = PBUser.objects.create_user(email="staff@example.com", password="SecurePass123!")
        self.staff.is_staff = True
        self.staff.save(update_fields=["is_staff"])

    def _login_staff(self):
        self.client.login(username="staff@example.com", password="SecurePass123!")

    def test_anonymous_is_redirected(self):
        resp = self.client.get("/monitoring/")
        self.assertEqual(resp.status_code, 302)
        self.assertIn("login", resp.url)

    def test_non_staff_is_redirected(self):
        PBUser.objects.create_user(email="plain@example.com", password="SecurePass123!")
        self.client.login(username="plain@example.com", password="SecurePass123!")
        resp = self.client.get("/monitoring/")
        self.assertEqual(resp.status_code, 302)
        self.assertIn("login", resp.url)

    def test_staff_gets_dashboard(self):
        self._login_staff()
        resp = self.client.get("/monitoring/")
        self.assertEqual(resp.status_code, 200)
        self.assertTemplateUsed(resp, "monitoring.html")

    def test_renders_with_empty_data(self):
        self._login_staff()
        ctx = self.client.get("/monitoring/").context
        self.assertEqual(ctx["total_papers"], 0)
        self.assertEqual(ctx["email_sent"], 0)
        self.assertEqual(ctx["email_failed"], 0)
        self.assertEqual(ctx["user_total"], 1)          # just the staff user

    def test_reflects_email_delivery_counts(self):
        EmailLog.objects.create(user=self.staff, status="sent")
        EmailLog.objects.create(user=self.staff, status="sent")
        EmailLog.objects.create(user=self.staff, status="failed")
        self._login_staff()
        ctx = self.client.get("/monitoring/").context
        self.assertEqual(ctx["email_sent"], 2)
        self.assertEqual(ctx["email_failed"], 1)
        self.assertAlmostEqual(ctx["email_failure_rate"], 33.3, places=1)
        self.assertEqual(len(ctx["recent_sent"]), 2)
        self.assertEqual(len(ctx["recent_failed"]), 1)

    def test_reflects_paper_and_user_counts(self):
        Paper.objects.create(title="P1")
        Paper.objects.create(title="P2")
        PBUser.objects.create_user(email="extra@example.com", password="SecurePass123!")
        self._login_staff()
        ctx = self.client.get("/monitoring/").context
        self.assertEqual(ctx["total_papers"], 2)
        self.assertEqual(ctx["user_total"], 2)          # staff + extra
