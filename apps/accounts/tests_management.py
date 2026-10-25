from decimal import Decimal
from io import StringIO

from django.core.management import call_command

from rest_framework.test import APITestCase

from apps.audit.models import AuditLog
from apps.orders.models import Order, OrderAddress

from .models import Permission, Role, User


def bootstrap_accounts():
    call_command(
        "seed_accounts",
        stdout=StringIO(),
    )


class AdminUserManagementTests(APITestCase):

    @classmethod
    def setUpTestData(cls):
        bootstrap_accounts()

        cls.admin_role = Role.objects.get(name="ADMIN")
        cls.client_role = Role.objects.get(name="CLIENT")

        cls.admin = User.objects.create_user(
            email="admin@example.com",
            first_name="Admin",
            last_name="BOMBAA",
            phone="+22890000101",
            password="AdminPassword123!",
            is_staff=True,
        )
        cls.admin.roles.add(cls.admin_role)

        cls.customer = User.objects.create_user(
            email="client@example.com",
            first_name="Client",
            last_name="Test",
            phone="+22890000102",
            password="ClientPassword123!",
        )
        cls.customer.roles.add(cls.client_role)

    def setUp(self):
        self.client.force_authenticate(user=self.admin)
        self.users_url = "/api/accounts/users/"

    def create_order_for(self, user, reference="CMD-TEST-0001"):
        order = Order.objects.create(
            user=user,
            reference=reference,
            subtotal=Decimal("10.00"),
            total_amount=Decimal("10.00"),
            currency="XOF",
        )

        OrderAddress.objects.create(
            order=order,
            recipient_name="Client Test",
            phone="+22890000102",
            address_line1="1 Rue de Test",
            city="Lomé",
            country_name="Togo",
            country_code="TG",
        )

        return order

    def test_admin_can_list_search_and_filter_users(self):
        response = self.client.get(
            self.users_url,
            {"search": "client"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["count"],
            1,
        )
        self.assertEqual(
            response.data["results"][0]["email"],
            "client@example.com",
        )

        response = self.client.get(
            self.users_url,
            {"role": "CLIENT"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["results"][0]["email"],
            "client@example.com",
        )

        response = self.client.get(
            self.users_url,
            {"is_active": "true"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 2)

    def test_client_cannot_manage_users(self):
        self.client.force_authenticate(user=self.customer)

        response = self.client.get(self.users_url)

        self.assertEqual(response.status_code, 403)

    def test_admin_can_create_user(self):
        response = self.client.post(
            self.users_url,
            {
                "first_name": "Nouveau",
                "last_name": "Client",
                "email": "nouveau@example.com",
                "phone": "+22890000104",
                "password": "NewPassword123!",
                "roles": [self.client_role.id],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            response.data["email"],
            "nouveau@example.com",
        )
        self.assertIn("CLIENT", response.data["roles"])
        self.assertNotIn("password", response.data)

        user = User.objects.get(email="nouveau@example.com")

        self.assertTrue(
            user.roles.filter(name="CLIENT").exists()
        )
        self.assertTrue(
            AuditLog.objects.filter(
                action=AuditLog.Action.CREATE,
                target_type="accounts.user",
                target_id=str(user.id),
            ).exists()
        )

    def test_admin_can_update_user_and_roles(self):
        response = self.client.patch(
            f"{self.users_url}{self.customer.id}/",
            {
                "first_name": "Nouveau",
                "roles": [self.admin_role.id],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)

        self.customer.refresh_from_db()

        self.assertEqual(
            self.customer.first_name,
            "Nouveau",
        )
        self.assertEqual(
            list(
                self.customer.roles.values_list(
                    "name",
                    flat=True,
                )
            ),
            ["ADMIN"],
        )

        audit = AuditLog.objects.get(
            action=AuditLog.Action.UPDATE,
            target_type="accounts.user",
            target_id=str(self.customer.id),
        )

        self.assertIn("first_name", audit.changes)
        self.assertIn("roles", audit.changes)

    def test_admin_can_deactivate_and_activate_user(self):
        response = self.client.post(
            f"{self.users_url}{self.customer.id}/deactivate/",
            format="json",
        )

        self.assertEqual(response.status_code, 200)

        self.customer.refresh_from_db()
        self.assertFalse(self.customer.is_active)

        self.assertTrue(
            AuditLog.objects.filter(
                action=AuditLog.Action.DEACTIVATE,
                target_type="accounts.user",
                target_id=str(self.customer.id),
            ).exists()
        )

        response = self.client.post(
            f"{self.users_url}{self.customer.id}/activate/",
            format="json",
        )

        self.assertEqual(response.status_code, 200)

        self.customer.refresh_from_db()
        self.assertTrue(self.customer.is_active)

        self.assertTrue(
            AuditLog.objects.filter(
                action=AuditLog.Action.ACTIVATE,
                target_type="accounts.user",
                target_id=str(self.customer.id),
            ).exists()
        )

    def test_admin_can_deactivate_user_with_patch(self):
        response = self.client.patch(
            f"{self.users_url}{self.customer.id}/",
            {"is_active": False},
            format="json",
        )

        self.assertEqual(response.status_code, 200)

        self.customer.refresh_from_db()
        self.assertFalse(self.customer.is_active)

        self.assertTrue(
            AuditLog.objects.filter(
                action=AuditLog.Action.DEACTIVATE,
                target_type="accounts.user",
                target_id=str(self.customer.id),
            ).exists()
        )

    def test_admin_cannot_deactivate_self(self):
        response = self.client.post(
            f"{self.users_url}{self.admin.id}/deactivate/",
            format="json",
        )

        self.assertEqual(response.status_code, 400)

        response = self.client.patch(
            f"{self.users_url}{self.admin.id}/",
            {"is_active": False},
            format="json",
        )

        self.assertEqual(response.status_code, 400)

    def test_admin_can_delete_user_without_orders(self):
        user = User.objects.create_user(
            email="delete@example.com",
            first_name="A",
            last_name="Supprimer",
            password="Password123!",
        )
        user.roles.add(self.client_role)
        user_id = user.id

        response = self.client.delete(
            f"{self.users_url}{user_id}/"
        )

        self.assertEqual(response.status_code, 204)
        self.assertFalse(
            User.objects.filter(pk=user_id).exists()
        )

        audit = AuditLog.objects.get(
            action=AuditLog.Action.DELETE,
            target_type="accounts.user",
            target_id=str(user_id),
        )

        self.assertEqual(
            audit.metadata["mode"],
            "deleted",
        )

    def test_delete_user_with_orders_anonymizes_account(self):
        user = User.objects.create_user(
            email="history@example.com",
            first_name="Historique",
            last_name="Client",
            phone="+22890000103",
            password="Password123!",
        )
        user.roles.add(self.client_role)
        order = self.create_order_for(
            user,
            reference="CMD-TEST-HISTORY",
        )

        response = self.client.delete(
            f"{self.users_url}{user.id}/"
        )

        self.assertEqual(response.status_code, 204)

        user.refresh_from_db()

        self.assertTrue(
            user.email.startswith(f"deleted-{user.id}-")
        )
        self.assertTrue(
            user.email.endswith("@bombaa.invalid")
        )
        self.assertIsNone(user.phone)
        self.assertFalse(user.is_active)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertFalse(user.roles.exists())

        self.assertTrue(
            Order.objects.filter(pk=order.id).exists()
        )

        audit = AuditLog.objects.get(
            action=AuditLog.Action.DELETE,
            target_type="accounts.user",
            target_id=str(user.id),
        )

        self.assertEqual(
            audit.metadata["mode"],
            "anonymized",
        )

    def test_admin_can_view_customer_orders(self):
        order = self.create_order_for(
            self.customer,
            reference="CMD-TEST-ORDERS",
        )

        response = self.client.get(
            f"{self.users_url}{self.customer.id}/orders/"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(
            response.data["results"][0]["reference"],
            order.reference,
        )

    def test_admin_can_view_customer_activities(self):
        self.client.patch(
            f"{self.users_url}{self.customer.id}/",
            {"first_name": "Activité"},
            format="json",
        )

        response = self.client.get(
            f"{self.users_url}{self.customer.id}/activities/"
        )

        self.assertEqual(response.status_code, 200)

        actions = [
            item["action"]
            for item in response.data["results"]
        ]

        self.assertIn(
            AuditLog.Action.UPDATE,
            actions,
        )

    def test_non_superuser_cannot_modify_superuser(self):
        superuser = User.objects.create_superuser(
            email="superuser@example.com",
            first_name="Super",
            last_name="Admin",
            password="SuperPassword123!",
        )

        response = self.client.patch(
            f"{self.users_url}{superuser.id}/",
            {"first_name": "Tentative"},
            format="json",
        )

        self.assertEqual(response.status_code, 403)

        response = self.client.delete(
            f"{self.users_url}{superuser.id}/"
        )

        self.assertEqual(response.status_code, 403)


class RoleAndPermissionManagementTests(APITestCase):

    @classmethod
    def setUpTestData(cls):
        bootstrap_accounts()

        cls.admin_role = Role.objects.get(name="ADMIN")
        cls.client_role = Role.objects.get(name="CLIENT")

        cls.admin = User.objects.create_user(
            email="role-admin@example.com",
            first_name="Role",
            last_name="Admin",
            password="AdminPassword123!",
        )
        cls.admin.roles.add(cls.admin_role)

        cls.customer = User.objects.create_user(
            email="role-client@example.com",
            first_name="Role",
            last_name="Client",
            password="ClientPassword123!",
        )
        cls.customer.roles.add(cls.client_role)

    def setUp(self):
        self.client.force_authenticate(user=self.admin)
        self.roles_url = "/api/accounts/roles/"
        self.permissions_url = "/api/accounts/permissions/"

    def test_admin_can_create_update_and_delete_role(self):
        permission = Permission.objects.get(
            name="products.view"
        )
        dashboard_permission = Permission.objects.get(
            name="dashboard.view"
        )

        response = self.client.post(
            self.roles_url,
            {
                "name": "test_manager",
                "description": "Rôle de test",
                "permissions": [permission.id],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            response.data["name"],
            "TEST_MANAGER",
        )

        role = Role.objects.get(name="TEST_MANAGER")

        self.assertEqual(
            response.data["permission_names"],
            ["products.view"],
        )

        response = self.client.patch(
            f"{self.roles_url}{role.id}/",
            {
                "description": "Rôle modifié",
                "permissions": [
                    permission.id,
                    dashboard_permission.id,
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            sorted(response.data["permission_names"]),
            ["dashboard.view", "products.view"],
        )

        self.assertTrue(
            AuditLog.objects.filter(
                action=AuditLog.Action.UPDATE,
                target_type="accounts.role",
                target_id=str(role.id),
            ).exists()
        )

        response = self.client.delete(
            f"{self.roles_url}{role.id}/"
        )

        self.assertEqual(response.status_code, 204)
        self.assertFalse(
            Role.objects.filter(pk=role.id).exists()
        )

        self.assertTrue(
            AuditLog.objects.filter(
                action=AuditLog.Action.DELETE,
                target_type="accounts.role",
                target_id=str(role.id),
            ).exists()
        )

    def test_cannot_delete_assigned_role(self):
        response = self.client.delete(
            f"{self.roles_url}{self.admin_role.id}/"
        )

        self.assertEqual(response.status_code, 400)

    def test_client_cannot_manage_roles(self):
        self.client.force_authenticate(user=self.customer)

        response = self.client.get(self.roles_url)

        self.assertEqual(response.status_code, 403)

    def test_admin_can_manage_permissions(self):
        response = self.client.post(
            self.permissions_url,
            {
                "name": "reports.view",
                "description": "Consulter les rapports",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)

        permission = Permission.objects.get(
            name="reports.view"
        )

        self.assertTrue(
            AuditLog.objects.filter(
                action=AuditLog.Action.CREATE,
                target_type="accounts.permission",
                target_id=str(permission.id),
            ).exists()
        )

        response = self.client.patch(
            f"{self.permissions_url}{permission.id}/",
            {
                "description": "Rapports et exports",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["description"],
            "Rapports et exports",
        )

        response = self.client.delete(
            f"{self.permissions_url}{permission.id}/"
        )

        self.assertEqual(response.status_code, 204)
        self.assertFalse(
            Permission.objects.filter(
                pk=permission.id
            ).exists()
        )


class AuditLogAPITests(APITestCase):

    @classmethod
    def setUpTestData(cls):
        bootstrap_accounts()

        cls.admin_role = Role.objects.get(name="ADMIN")
        cls.client_role = Role.objects.get(name="CLIENT")

        cls.admin = User.objects.create_user(
            email="audit-admin@example.com",
            first_name="Audit",
            last_name="Admin",
            password="AdminPassword123!",
        )
        cls.admin.roles.add(cls.admin_role)

        cls.customer = User.objects.create_user(
            email="audit-client@example.com",
            first_name="Audit",
            last_name="Client",
            password="ClientPassword123!",
        )
        cls.customer.roles.add(cls.client_role)

    def setUp(self):
        self.client.force_authenticate(user=self.admin)
        self.audit_url = "/api/audit-logs/"

    def test_admin_can_list_and_filter_audit_logs(self):
        self.client.patch(
            f"/api/accounts/users/{self.customer.id}/",
            {"first_name": "Journalisé"},
            format="json",
        )

        response = self.client.get(self.audit_url)

        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(response.data["count"], 1)

        response = self.client.get(
            self.audit_url,
            {
                "action": AuditLog.Action.UPDATE,
                "target_type": "accounts.user",
                "actor": self.admin.id,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(
            response.data["results"][0]["target_id"],
            str(self.customer.id),
        )

        response = self.client.get(
            self.audit_url,
            {"search": "audit-client@example.com"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(response.data["count"], 1)

    def test_client_cannot_access_audit_logs(self):
        self.client.force_authenticate(user=self.customer)

        response = self.client.get(self.audit_url)

        self.assertEqual(response.status_code, 403)
