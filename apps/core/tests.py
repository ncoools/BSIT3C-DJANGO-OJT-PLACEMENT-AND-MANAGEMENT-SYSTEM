from datetime import date, time, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps import authz
from apps.core.models import PasswordResetPIN, PasswordState
from apps.companies.models import Company
from apps.placements.models import Attendance, Placement, PlacementRequirement
from apps.students.models import Student
from apps.supervisors.models import Supervisor


class HomeViewTests(TestCase):
    def test_home_renders_for_admin(self):
        user = get_user_model().objects.create_user(
            username='admin', password='secret1234', is_staff=True,
        )

        self.client.force_login(user)
        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'home.html')

    def test_home_requires_login(self):
        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, 302)

    def test_student_is_redirected_to_student_dashboard(self):
        user = get_user_model().objects.create_user(
            username='stud', password='secret1234', email='stud@example.com',
        )
        Student.objects.create(
            student_number='HOME-001', first_name='Hom', last_name='Student',
            email='stud@example.com',
        )
        self.client.force_login(user)

        response = self.client.get(reverse('dashboard'))

        self.assertRedirects(response, reverse('student_dashboard'), fetch_redirect_response=False)

    def test_supervisor_is_redirected_to_supervisor_dashboard(self):
        user = get_user_model().objects.create_user(
            username='sup', password='secret1234', email='sup@example.com',
        )
        Supervisor.objects.create(
            first_name='Hom', last_name='Supervisor',
            supervisor_type=Supervisor.Type.COMPANY, email='sup@example.com',
        )
        self.client.force_login(user)

        response = self.client.get(reverse('dashboard'))

        self.assertRedirects(response, reverse('supervisor_dashboard'), fetch_redirect_response=False)

    def test_user_without_role_gets_forbidden_instead_of_redirect_loop(self):
        user = get_user_model().objects.create_user(username='norole', password='secret1234')
        self.client.force_login(user)

        response = self.client.get(reverse('dashboard'))

        self.assertEqual(response.status_code, 403)

    def test_home_json_payload_escapes_script_tags(self):
        user = get_user_model().objects.create_user(
            username='admin', password='secret1234', is_staff=True,
        )
        student = Student.objects.create(
            student_number='HOME-XSS', first_name='Jamie', last_name='Doe',
        )
        company = Company.objects.create(
            company_name='</script><script>alert(1)</script>',
        )
        Placement.objects.create(
            student=student, company=company, start_date=date(2026, 6, 1),
            end_date=date(2026, 9, 1), required_hours=500,
        )
        self.client.force_login(user)

        response = self.client.get(reverse('dashboard'))

        self.assertNotContains(response, '</script><script>alert(1)</script>')
        self.assertNotContains(response, '"|safe')
        self.assertIn('\\u003C', response.content.decode())


class RoleGroupSyncTests(TestCase):
    """auth groups stay in sync with Student/Supervisor profile records."""

    def test_student_add_creates_group_membership(self):
        user = get_user_model().objects.create_user(username='stud', password='secret1234', email='stud@example.com')

        Student.objects.create(student_number='SYNC-001', first_name='Stu', last_name='Dent', email='stud@example.com')

        self.assertTrue(user.groups.filter(name='student').exists())

    def test_student_delete_removes_group_membership(self):
        user = get_user_model().objects.create_user(username='stud', password='secret1234', email='stud@example.com')

        student = Student.objects.create(student_number='SYNC-002', first_name='Stu', last_name='Dent', email='stud@example.com')
        student.delete()

        self.assertFalse(user.groups.filter(name='student').exists())

    def test_supervisor_add_creates_group_membership(self):
        user = get_user_model().objects.create_user(username='sup', password='secret1234', email='sup@example.com')

        Supervisor.objects.create(first_name='Sup', last_name='Visor', supervisor_type=Supervisor.Type.COMPANY, email='sup@example.com')

        self.assertTrue(user.groups.filter(name='supervisor').exists())

    def test_supervisor_delete_removes_group_membership(self):
        user = get_user_model().objects.create_user(username='sup', password='secret1234', email='sup@example.com')

        supervisor = Supervisor.objects.create(first_name='Sup', last_name='Visor', supervisor_type=Supervisor.Type.COMPANY, email='sup@example.com')
        supervisor.delete()

        self.assertFalse(user.groups.filter(name='supervisor').exists())


class RegistrationTests(TestCase):
    def test_register_student_creates_student_and_group(self):
        response = self.client.post(reverse('register'), {
            'username': 'newstudent',
            'first_name': 'New',
            'last_name': 'Student',
            'email': 'new@example.com',
            'student_number': '2026-100',
        })

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'auth/register_success.html')
        generated_password = response.context['generated_password']
        self.assertContains(response, generated_password)
        self.assertTrue(Student.objects.filter(email__iexact='new@example.com').exists())
        user = get_user_model().objects.get(username='newstudent')
        self.assertTrue(user.groups.filter(name='student').exists())
        self.assertTrue(user.check_password(generated_password))
        self.assertFalse(user.check_password('2026-100'))
        self.assertTrue(PasswordState.objects.get(user=user).must_change_password)

    def test_register_notice_describes_generated_password(self):
        html = self.client.get(reverse('register')).content.decode()

        self.assertIn('We generate a secure initial password', html)
        self.assertNotIn('serves as your password', html.lower())
        self.assertNotIn('This will be your password', html)

    def test_register_student_requires_student_number(self):
        response = self.client.post(reverse('register'), {
            'username': 'newstudent2',
            'first_name': 'New',
            'last_name': 'Student',
            'email': 'new2@example.com',
            'student_number': '',
        })

        self.assertEqual(response.status_code, 200)
        self.assertFalse(get_user_model().objects.filter(username='newstudent2').exists())

    def test_admin_can_create_active_supervisor_account(self):
        admin = get_user_model().objects.create_user(username='admincreate', password='secret1234', is_staff=True)
        self.client.force_login(admin)
        response = self.client.post(reverse('supervisor_register'), {
            'first_name': 'Sup',
            'last_name': 'Visor',
            'email': 'supnew@example.com',
            'password': 'secret-1234',
            'confirm_password': 'secret-1234',
            'supervisor_type': Supervisor.Type.COMPANY,
        })

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'auth/supervisor_created.html')
        self.assertTrue(Supervisor.objects.filter(email__iexact='supnew@example.com').exists())
        user = get_user_model().objects.get(username='supnew@example.com')
        self.assertTrue(user.is_active)
        self.assertTrue(user.groups.filter(name='supervisor').exists())

    def test_supervisor_register_is_admin_only(self):
        student_user = get_user_model().objects.create_user(username='studGuest', password='secret1234', email='studguest@example.com')
        Student.objects.create(student_number='GUEST-001', first_name='Guest', last_name='Student', email='studguest@example.com')
        self.client.force_login(student_user)
        response = self.client.get(reverse('supervisor_register'))
        self.assertRedirects(response, reverse('student_dashboard'), fetch_redirect_response=False)

    def test_anonymous_redirected_to_login_for_supervisor_register(self):
        response = self.client.get(reverse('supervisor_register'))
        self.assertRedirects(response, '/?next=/supervisor-register/', fetch_redirect_response=False)

    def test_public_pages_do_not_link_supervisor_registration(self):
        login_html = self.client.get(reverse('login')).content.decode()
        register_html = self.client.get(reverse('register')).content.decode()
        for html in (login_html, register_html):
            self.assertNotIn('supervisor_register', html)
            self.assertNotIn('Register as Supervisor', html)
            self.assertNotIn('Supervisor Registration', html)

    def test_admin_can_approve_pending_supervisor(self):
        admin = get_user_model().objects.create_user(username='admin', password='secret1234', is_staff=True)
        user = get_user_model().objects.create_user(username='sup2@example.com', email='sup2@example.com', password='secret-1234', is_active=False)
        Supervisor.objects.create(first_name='Sup', last_name='Two', supervisor_type=Supervisor.Type.COMPANY, email='sup2@example.com')

        self.client.force_login(admin)
        response = self.client.post(reverse('approve_supervisor', args=[user.pk]))

        self.assertRedirects(response, reverse('approvals'), fetch_redirect_response=False)
        user.refresh_from_db()
        self.assertTrue(user.is_active)

    def test_admin_can_reject_pending_supervisor(self):
        admin = get_user_model().objects.create_user(username='adminrej', password='secret1234', is_staff=True)
        user = get_user_model().objects.create_user(username='sup3@example.com', email='sup3@example.com', password='secret-1234', is_active=False)
        Supervisor.objects.create(first_name='Sup', last_name='Three', supervisor_type=Supervisor.Type.COMPANY, email='sup3@example.com')

        self.client.force_login(admin)
        response = self.client.post(reverse('reject_supervisor', args=[user.pk]))

        self.assertRedirects(response, reverse('approvals'), fetch_redirect_response=False)
        self.assertFalse(get_user_model().objects.filter(username='sup3@example.com').exists())
        self.assertFalse(Supervisor.objects.filter(email__iexact='sup3@example.com').exists())

    def test_pending_supervisor_cannot_reach_approvals_page(self):
        # Inactive accounts resolve to anonymous on the next request, so
        # login_required bounces them to the login page.
        user = get_user_model().objects.create_user(username='sup4@example.com', email='sup4@example.com', password='secret-1234', is_active=False)
        Supervisor.objects.create(first_name='Sup', last_name='Four', supervisor_type=Supervisor.Type.COMPANY, email='sup4@example.com')
        self.client.force_login(user)
        response = self.client.get(reverse('approvals'))
        self.assertRedirects(response, '/?next=/approvals/', fetch_redirect_response=False)

    def test_non_admin_supervisor_redirected_from_approvals_page(self):
        user = get_user_model().objects.create_user(username='sup5@example.com', email='sup5@example.com', password='secret-1234', is_active=True)
        Supervisor.objects.create(first_name='Sup', last_name='Five', supervisor_type=Supervisor.Type.COMPANY, email='sup5@example.com')
        self.client.force_login(user)
        response = self.client.get(reverse('approvals'))
        self.assertRedirects(response, reverse('dashboard'), fetch_redirect_response=False)


class PasswordFlowTests(TestCase):
    def setUp(self):
        patcher = patch('apps.core.views._password_change_window_open', return_value=True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _create_student_user(self, username='pwstudent', email='pwstudent@example.com'):
        user = get_user_model().objects.create_user(
            username=username, password='initial-pass-123', email=email,
        )
        Student.objects.create(
            student_number='PW-100', first_name='Pass', last_name='Student', email=email,
        )
        return user

    def test_generated_password_user_is_forced_to_change(self):
        user = self._create_student_user()
        PasswordState.objects.create(user=user, must_change_password=True)
        self.client.force_login(user)

        dashboard_response = self.client.get(reverse('dashboard'))
        placements_response = self.client.get(reverse('placements:list'))
        change_response = self.client.get(reverse('password_change'))

        self.assertRedirects(dashboard_response, reverse('password_change'), fetch_redirect_response=False)
        self.assertRedirects(placements_response, reverse('password_change'), fetch_redirect_response=False)
        self.assertEqual(change_response.status_code, 200)

    def test_forced_password_change_clears_flag(self):
        user = self._create_student_user()
        PasswordState.objects.create(user=user, must_change_password=True)
        self.client.force_login(user)

        response = self.client.post(reverse('password_change'), {
            'new_password': 'MyNewPass!456',
            'confirm_password': 'MyNewPass!456',
        })

        self.assertRedirects(response, reverse('dashboard'), fetch_redirect_response=False)
        user.refresh_from_db()
        self.assertTrue(user.check_password('MyNewPass!456'))
        self.assertFalse(PasswordState.objects.get(user=user).must_change_password)
        self.assertRedirects(
            self.client.get(reverse('dashboard')),
            reverse('student_dashboard'),
            fetch_redirect_response=False,
        )

    def test_login_redirects_forced_user_to_password_change(self):
        user = self._create_student_user()
        PasswordState.objects.create(user=user, must_change_password=True)

        response = self.client.post(reverse('login'), {
            'username': 'pwstudent',
            'password': 'initial-pass-123',
        })

        self.assertRedirects(response, reverse('password_change'), fetch_redirect_response=False)

    def test_admin_can_issue_pin_and_student_can_use_it_once(self):
        admin = get_user_model().objects.create_user(
            username='pinadmin', password='secret1234', is_staff=True,
        )
        student = self._create_student_user()
        self.client.force_login(admin)

        with patch('apps.core.views.secrets.randbelow', return_value=654321):
            response = self.client.post(
                reverse('account_action', args=[student.pk]),
                {'action': 'generate_pin'},
            )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '654321')
        record = PasswordResetPIN.objects.get(user=student)
        self.assertNotEqual(record.pin_hash, '654321')
        self.assertIsNone(record.used_at)

        self.client.logout()
        response = self.client.post(reverse('password_change'), {
            'identity': 'PW-100',
            'pin': '654321',
            'new_password': 'ResetPass!789',
            'confirm_password': 'ResetPass!789',
        })

        self.assertRedirects(response, reverse('login'), fetch_redirect_response=False)
        student.refresh_from_db()
        record.refresh_from_db()
        self.assertTrue(student.check_password('ResetPass!789'))
        self.assertIsNotNone(record.used_at)

        reuse_response = self.client.post(reverse('password_change'), {
            'identity': 'PW-100',
            'pin': '654321',
            'new_password': 'AnotherPass!123',
            'confirm_password': 'AnotherPass!123',
        })
        self.assertEqual(reuse_response.status_code, 200)
        self.assertContains(reuse_response, 'PIN is invalid, expired, or already used.')

    def test_pin_is_not_shown_again_on_accounts_page(self):
        admin = get_user_model().objects.create_user(
            username='pinadmin2', password='secret1234', is_staff=True,
        )
        student = self._create_student_user(username='pinstudent2')
        self.client.force_login(admin)

        with patch('apps.core.views.secrets.randbelow', return_value=654321):
            self.client.post(
                reverse('account_action', args=[student.pk]),
                {'action': 'generate_pin'},
            )
        response = self.client.get(reverse('accounts'))

        self.assertNotContains(response, '654321')

    def test_admin_cannot_issue_pin_to_non_student(self):
        admin = get_user_model().objects.create_user(
            username='pinadmin3', password='secret1234', is_staff=True,
        )
        supervisor = get_user_model().objects.create_user(
            username='pinsup', password='secret1234', email='pinsup@example.com',
        )
        Supervisor.objects.create(
            first_name='Pin', last_name='Sup',
            supervisor_type=Supervisor.Type.COMPANY, email='pinsup@example.com',
        )
        self.client.force_login(admin)

        response = self.client.post(
            reverse('account_action', args=[supervisor.pk]),
            {'action': 'generate_pin'},
        )

        self.assertRedirects(response, reverse('accounts'), fetch_redirect_response=False)
        self.assertFalse(PasswordResetPIN.objects.filter(user=supervisor).exists())


    def test_password_change_blocked_outside_window(self):
        user = self._create_student_user()
        PasswordState.objects.create(user=user, must_change_password=True)
        self.client.force_login(user)

        with patch('apps.core.views._password_change_window_open', return_value=False):
            response = self.client.post(reverse('password_change'), {
                'new_password': 'OutsidePass!123',
                'confirm_password': 'OutsidePass!123',
            })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'available daily from 7:00 PM – 10:00 PM only')
        user.refresh_from_db()
        self.assertTrue(user.check_password('initial-pass-123'))
        self.assertTrue(PasswordState.objects.get(user=user).must_change_password)

    def test_admin_cannot_issue_pin_outside_window(self):
        admin = get_user_model().objects.create_user(
            username='windowadmin', password='secret1234', is_staff=True,
        )
        student = self._create_student_user(username='windowstudent')
        self.client.force_login(admin)

        with patch('apps.core.views._password_change_window_open', return_value=False):
            response = self.client.post(
                reverse('account_action', args=[student.pk]),
                {'action': 'generate_pin'},
            )

        self.assertRedirects(response, reverse('accounts'), fetch_redirect_response=False)
        self.assertFalse(PasswordResetPIN.objects.filter(user=student).exists())

    def test_window_note_is_visible(self):
        login_html = self.client.get(reverse('login')).content.decode()
        self.assertIn('7:00 PM – 10:00 PM', login_html)

        user = self._create_student_user()
        PasswordState.objects.create(user=user, must_change_password=True)
        self.client.force_login(user)
        response = self.client.get(reverse('password_change'))

        self.assertContains(response, '7:00 PM – 10:00 PM')


class AccountsViewTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user(username='boss', password='secret1234', email='boss@example.com', is_staff=True)
        self.target = User.objects.create_user(username='target', password='secret1234', email='target@example.com', first_name='Tar', last_name='Get')

    def test_admin_can_set_student_role_and_creates_profile(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse('account_action', args=[self.target.pk]), {'action': 'set_student'})

        self.assertRedirects(response, reverse('accounts'), fetch_redirect_response=False)
        self.assertTrue(self.target.groups.filter(name='student').exists())
        self.assertFalse(self.target.groups.filter(name='supervisor').exists())
        self.assertTrue(Student.objects.filter(email__iexact='target@example.com').exists())

    def test_admin_can_set_supervisor_role_and_creates_profile(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse('account_action', args=[self.target.pk]), {'action': 'set_supervisor'})

        self.assertRedirects(response, reverse('accounts'), fetch_redirect_response=False)
        self.assertTrue(self.target.groups.filter(name='supervisor').exists())
        self.assertFalse(self.target.groups.filter(name='student').exists())
        self.assertTrue(Supervisor.objects.filter(email__iexact='target@example.com').exists())

    def test_admin_can_clear_role(self):
        Group.objects.get_or_create(name='student')[0].user_set.add(self.target)
        self.client.force_login(self.admin)
        response = self.client.post(reverse('account_action', args=[self.target.pk]), {'action': 'clear_role'})

        self.assertRedirects(response, reverse('accounts'), fetch_redirect_response=False)
        self.assertFalse(self.target.groups.filter(name__in=['student', 'supervisor']).exists())

    def test_clear_role_does_not_grant_admin_access(self):
        self.client.force_login(self.admin)
        self.client.post(reverse('account_action', args=[self.target.pk]), {'action': 'set_supervisor'})
        self.client.post(reverse('account_action', args=[self.target.pk]), {'action': 'clear_role'})

        target = get_user_model().objects.get(pk=self.target.pk)
        self.assertFalse(target.groups.filter(name__in=['student', 'supervisor']).exists())
        self.assertFalse(authz.is_admin(target))
        self.client.force_login(target)
        response = self.client.get(reverse('accounts'))
        self.assertNotEqual(response.status_code, 200)

    def test_non_staff_without_role_is_not_admin(self):
        user = get_user_model().objects.create_user(username='norole', password='secret1234')

        self.assertFalse(authz.is_admin(user))

    def test_admin_can_toggle_active(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse('account_action', args=[self.target.pk]), {'action': 'toggle_active'})
        self.assertRedirects(response, reverse('accounts'), fetch_redirect_response=False)
        self.target.refresh_from_db()
        self.assertFalse(self.target.is_active)

    def test_admin_cannot_deactivate_self(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse('account_action', args=[self.admin.pk]), {'action': 'toggle_active'})
        self.assertRedirects(response, reverse('accounts'), fetch_redirect_response=False)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

    def test_admin_cannot_modify_superuser(self):
        User = get_user_model()
        superuser = User.objects.create_superuser(username='root', password='secret1234', email='root@example.com')
        self.client.force_login(self.admin)
        response = self.client.post(reverse('account_action', args=[superuser.pk]), {'action': 'toggle_active'})
        self.assertRedirects(response, reverse('accounts'), fetch_redirect_response=False)
        superuser.refresh_from_db()
        self.assertTrue(superuser.is_active)

    def test_student_cannot_reach_accounts_page(self):
        student_user = get_user_model().objects.create_user(username='plainstudent', password='secret1234', email='plainstudent@example.com')
        Student.objects.create(student_number='ACC-100', first_name='Plain', last_name='Student', email='plainstudent@example.com')
        self.client.force_login(student_user)
        response = self.client.get(reverse('accounts'))
        self.assertRedirects(response, reverse('student_dashboard'), fetch_redirect_response=False)

    def test_accounts_page_lists_users_for_admin(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('accounts'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'target')


class AdminModuleAccessTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user(username='admin', password='secret1234', email='admin@example.com', is_staff=True)
        self.student_user = User.objects.create_user(username='stud', password='secret1234', email='stud@example.com')
        Student.objects.create(student_number='ACC-001', first_name='Stu', last_name='Dent', email='stud@example.com')
        self.supervisor_user = User.objects.create_user(username='sup', password='secret1234', email='sup@example.com')
        Supervisor.objects.create(first_name='Sup', last_name='Visor', supervisor_type=Supervisor.Type.COMPANY, email='sup@example.com')

    def test_student_redirected_from_students_module(self):
        self.client.force_login(self.student_user)
        response = self.client.get(reverse('students:list'))

        self.assertRedirects(response, reverse('student_dashboard'), fetch_redirect_response=False)

    def test_supervisor_redirected_from_supervisors_module(self):
        self.client.force_login(self.supervisor_user)
        response = self.client.get(reverse('supervisors:list'))

        self.assertRedirects(response, reverse('supervisor_dashboard'), fetch_redirect_response=False)

    def test_admin_can_access_students_module(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('students:list'))

        self.assertEqual(response.status_code, 200)


class VerifiedAttendanceClockTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username='clockstudent', password='secret1234', email='clock@example.com',
        )
        student = Student.objects.create(
            student_number='CLK-001', first_name='Clock', last_name='Student',
            email='clock@example.com',
        )
        company = Company.objects.create(company_name='Clock Co')
        placement = Placement.objects.create(
            student=student, company=company, start_date=date(2026, 6, 1),
            end_date=date(2026, 9, 1), required_hours=500,
            status=Placement.Status.IN_PROGRESS,
        )
        self.attendance = Attendance.objects.create(
            placement=placement, attendance_date=timezone.now().date(),
            time_in=time(9, 0), time_out=time(17, 0),
            status=Attendance.Status.PRESENT, verified=True,
        )
        self.client.force_login(self.user)

    def test_time_in_does_not_change_verified_attendance(self):
        response = self.client.post(reverse('student_time_in'))

        self.assertRedirects(response, reverse('student_dashboard'), fetch_redirect_response=False)
        self.attendance.refresh_from_db()
        self.assertEqual(self.attendance.time_in, time(9, 0))
        self.assertEqual(self.attendance.status, Attendance.Status.PRESENT)

    def test_time_out_does_not_change_verified_attendance(self):
        response = self.client.post(reverse('student_time_out'))

        self.assertRedirects(response, reverse('student_dashboard'), fetch_redirect_response=False)
        self.attendance.refresh_from_db()
        self.assertEqual(self.attendance.time_out, time(17, 0))
        self.assertEqual(self.attendance.hours_rendered, 8)


class DashboardAlertTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.admin = get_user_model().objects.create_user(
            username='alertadmin', password='secret1234', is_staff=True,
        )
        self.student_user = get_user_model().objects.create_user(
            username='alertstudent', password='secret1234',
            email='alertstudent@example.com',
        )
        self.student = Student.objects.create(
            student_number='ALERT-001', first_name='Alert', last_name='Student',
            email='alertstudent@example.com',
        )
        self.supervisor_user = get_user_model().objects.create_user(
            username='alertsup', password='secret1234',
            email='alertsup@example.com',
        )
        self.supervisor = Supervisor.objects.create(
            first_name='Alert', last_name='Supervisor',
            supervisor_type=Supervisor.Type.COMPANY, email='alertsup@example.com',
        )
        self.company = Company.objects.create(company_name='Alert Company')
        self.placement = Placement.objects.create(
            student=self.student, company=self.company, supervisor=self.supervisor,
            start_date=self.today - timedelta(days=30),
            end_date=self.today + timedelta(days=7),
            required_hours=500, completed_hours=100,
            status=Placement.Status.IN_PROGRESS,
        )
        Student.objects.create(
            student_number='ALERT-002', first_name='No', last_name='Placement',
        )
        inactive_user = get_user_model().objects.create_user(
            username='inactivesup', password='secret1234',
            email='inactive-sup@example.com', is_active=False,
        )
        Supervisor.objects.create(
            first_name='Inactive', last_name='Supervisor',
            supervisor_type=Supervisor.Type.COMPANY, email=inactive_user.email,
        )
        PlacementRequirement.objects.create(
            placement=self.placement, requirement_name='Contract',
            status=PlacementRequirement.Status.PENDING,
        )
        Attendance.objects.create(
            placement=self.placement,
            attendance_date=self.today - timedelta(days=3),
            time_in=time(9, 0), time_out=time(17, 0), verified=False,
        )

    def test_admin_dashboard_shows_live_alerts(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse('dashboard'))

        alerts = {alert['id'] for alert in response.context['dashboard_alerts']}
        self.assertEqual(alerts, {
            'unplaced-students',
            'pending-approvals',
            'pending-requirements',
            'placements-ending',
            'unverified-attendance',
        })
        self.assertContains(response, 'Dashboard alerts')
        self.assertContains(response, 'Students not yet placed')

    def test_student_dashboard_shows_live_alerts(self):
        self.client.force_login(self.student_user)

        response = self.client.get(reverse('student_dashboard'))

        alerts = {alert['id'] for alert in response.context['dashboard_alerts']}
        self.assertEqual(alerts, {
            'attendance-awaiting-verification',
            'requirements-to-submit',
            'placement-ending',
        })
        self.assertContains(response, 'Attendance awaiting verification')

    def test_supervisor_dashboard_shows_live_alerts(self):
        self.client.force_login(self.supervisor_user)

        response = self.client.get(reverse('supervisor_dashboard'))

        alerts = {alert['id'] for alert in response.context['dashboard_alerts']}
        self.assertEqual(alerts, {
            'unverified-attendance',
            'evaluations-due',
            'hours-behind',
        })
        self.assertContains(response, 'Evaluations due')

