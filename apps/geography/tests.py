from decimal import Decimal

from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.payments.models import PaymentMethod

from .models import Country, Currency


class GeographyTestBase(APITestCase):

    def setUp(self):
        self.xof = Currency.objects.create(
            code="XOF",
            name="Franc CFA",
            symbol="FCFA",
            exchange_rate=Decimal("1.000000"),
            is_base=True,
        )

        self.eur = Currency.objects.create(
            code="EUR",
            name="Euro",
            symbol="€",
            exchange_rate=Decimal("655.957000"),
            is_base=False,
        )

        self.togo = Country.objects.create(
            name="Togo",
            code="TG",
            phone_code="+228",
            currency=self.xof,
            is_active=True,
        )

        self.france = Country.objects.create(
            name="France",
            code="FR",
            phone_code="+33",
            currency=self.eur,
            is_active=True,
        )

        self.ghana = Country.objects.create(
            name="Ghana",
            code="GH",
            phone_code="+233",
            currency=self.xof,
            is_active=False,
        )

        self.admin_user = User.objects.create_superuser(
            email="geography-admin@example.com",
            password="TestPassword123!",
            first_name="Admin",
            last_name="Geography",
        )


class CurrencyTests(GeographyTestBase):

    def test_currency_conversion_methods(self):
        self.assertEqual(
            self.eur.convert_from_base(Decimal("655957.00")),
            Decimal("1000.00"),
        )

        self.assertEqual(
            self.eur.convert_to_base(Decimal("1000.00")),
            Decimal("655957.00"),
        )

    def test_only_one_base_currency(self):
        self.eur.is_base = True
        self.eur.save()

        self.xof.refresh_from_db()
        self.eur.refresh_from_db()

        self.assertFalse(self.xof.is_base)
        self.assertTrue(self.eur.is_base)

    def test_public_currency_list_only_returns_active_currencies(self):
        Currency.objects.create(
            code="USD",
            name="Dollar américain",
            symbol="$",
            exchange_rate=Decimal("600.000000"),
            is_active=False,
        )

        response = self.client.get("/api/currencies/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            {
                currency["code"]
                for currency in response.data["results"]
            },
            {"XOF", "EUR"},
        )

    def test_currency_conversion_endpoint(self):
        response = self.client.get(
            (
                "/api/currencies/convert/"
                "?amount=655957&from=XOF&to=EUR"
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["from"], "XOF")
        self.assertEqual(response.data["to"], "EUR")
        self.assertEqual(
            Decimal(response.data["converted_amount"]),
            Decimal("1000.00"),
        )
        self.assertEqual(
            Decimal(response.data["rate"]),
            Decimal("0.001524"),
        )

    def test_currency_conversion_rejects_invalid_amount(self):
        response = self.client.get(
            "/api/currencies/convert/?amount=abc"
        )

        self.assertEqual(response.status_code, 400)

        response = self.client.get(
            "/api/currencies/convert/?amount=NaN"
        )

        self.assertEqual(response.status_code, 400)


class CountryTests(GeographyTestBase):

    def test_public_country_list_only_returns_active_countries(self):
        response = self.client.get("/api/countries/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            {
                country["code"]
                for country in response.data["results"]
            },
            {"TG", "FR"},
        )

    def test_country_search_and_currency_filters(self):
        response = self.client.get(
            "/api/countries/?search=togo"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [
                country["code"]
                for country in response.data["results"]
            ],
            ["TG"],
        )

        response = self.client.get(
            "/api/countries/?currency=EUR"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [
                country["code"]
                for country in response.data["results"]
            ],
            ["FR"],
        )

    def test_country_exposes_currency_and_payment_methods(self):
        method = PaymentMethod.objects.create(
            name="Mobile Money",
            code="GEO_MOBILE_MONEY",
            is_active=True,
        )

        self.togo.payment_methods.add(method)

        response = self.client.get(
            f"/api/countries/{self.togo.id}/"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["currency_detail"]["code"],
            "XOF",
        )
        self.assertEqual(
            response.data["payment_methods"],
            [method.id],
        )
        self.assertEqual(
            response.data["payment_methods_detail"][0]["code"],
            "GEO_MOBILE_MONEY",
        )

    def test_anonymous_cannot_create_country(self):
        response = self.client.post(
            "/api/countries/",
            {
                "name": "Bénin",
                "code": "BJ",
                "currency": self.xof.id,
            },
            format="json",
        )

        self.assertIn(response.status_code, [401, 403])
        self.assertFalse(
            Country.objects.filter(code="BJ").exists()
        )

    def test_admin_can_create_country(self):
        self.client.force_authenticate(self.admin_user)

        response = self.client.post(
            "/api/countries/",
            {
                "name": "Bénin",
                "code": "bj",
                "phone_code": "+229",
                "currency": self.xof.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["code"], "BJ")

        country = Country.objects.get(code="BJ")
        self.assertEqual(country.currency, self.xof)
