from decimal import Decimal

from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.geography.models import Country, Currency

from .models import Address


class AddressCountryTests(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            email="address-country@example.com",
            password="TestPassword123!",
            first_name="Client",
            last_name="Adresse",
            phone="+22890000123",
        )

        self.xof = Currency.objects.create(
            code="XOF",
            name="Franc CFA",
            symbol="FCFA",
            exchange_rate=Decimal("1.000000"),
            is_base=True,
        )

        self.togo = Country.objects.create(
            name="Togo",
            code="TG",
            phone_code="+228",
            currency=self.xof,
        )

        self.payload = {
            "first_name": "Client",
            "last_name": "Adresse",
            "phone": "+22890000123",
            "address_line_1": "1 rue du Test",
            "city": "Lomé",
        }

    def test_create_address_with_country_id(self):
        self.client.force_authenticate(self.user)

        response = self.client.post(
            "/api/addresses/",
            {
                **self.payload,
                "country_id": self.togo.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["country"], "Togo")
        self.assertEqual(response.data["country_id"], self.togo.id)
        self.assertEqual(response.data["country_code"], "TG")
        self.assertEqual(
            response.data["country_detail"]["code"],
            "TG",
        )

        address = Address.objects.get(user=self.user)

        self.assertEqual(address.country_ref, self.togo)
        self.assertEqual(address.country, "Togo")

    def test_create_address_with_country_name_resolves_country(self):
        self.client.force_authenticate(self.user)

        response = self.client.post(
            "/api/addresses/",
            {
                **self.payload,
                "country": "Togo",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["country_id"], self.togo.id)
        self.assertEqual(response.data["country_code"], "TG")

        address = Address.objects.get(user=self.user)

        self.assertEqual(address.country_ref, self.togo)

    def test_create_address_requires_country(self):
        self.client.force_authenticate(self.user)

        response = self.client.post(
            "/api/addresses/",
            self.payload,
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("country", response.data)

    def test_create_address_without_configured_country_keeps_country_name(self):
        self.client.force_authenticate(self.user)

        response = self.client.post(
            "/api/addresses/",
            {
                **self.payload,
                "country": "Pays inconnu",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["country"], "Pays inconnu")
        self.assertIsNone(response.data["country_id"])
        self.assertIsNone(response.data["country_code"])
        self.assertIsNone(response.data["country_detail"])

        address = Address.objects.get(user=self.user)

        self.assertIsNone(address.country_ref)

    def test_update_address_with_country_id_updates_country_name(self):
        address = Address.objects.create(
            user=self.user,
            first_name="Client",
            last_name="Adresse",
            phone="+22890000123",
            address_line_1="1 rue du Test",
            city="Lomé",
            country="Ancien pays",
        )

        self.client.force_authenticate(self.user)

        response = self.client.patch(
            f"/api/addresses/{address.id}/",
            {"country_id": self.togo.id},
            format="json",
        )

        self.assertEqual(response.status_code, 200)

        address.refresh_from_db()

        self.assertEqual(address.country_ref, self.togo)
        self.assertEqual(address.country, "Togo")
