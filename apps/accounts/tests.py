from rest_framework.test import APITestCase

from .models import Role, User


class RegisterTests(APITestCase):

    def test_register_creates_client_role_when_missing(self):
        Role.objects.filter(name="CLIENT").delete()

        response = self.client.post(
            "/api/accounts/register/",
            {
                "first_name": "Nouveau",
                "last_name": "Client",
                "email": "nouveau-client@example.com",
                "phone": "+22890000999",
                "password": "TestPassword123!",
                "password_confirmation": "TestPassword123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)

        user = User.objects.get(
            email="nouveau-client@example.com"
        )

        self.assertTrue(
            user.roles.filter(name="CLIENT").exists()
        )

    def test_register_rejects_mismatched_passwords(self):
        response = self.client.post(
            "/api/accounts/register/",
            {
                "first_name": "Nouveau",
                "last_name": "Client",
                "email": "mismatch@example.com",
                "password": "TestPassword123!",
                "password_confirmation": "AutrePassword123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(
            User.objects.filter(email="mismatch@example.com").exists()
        )
