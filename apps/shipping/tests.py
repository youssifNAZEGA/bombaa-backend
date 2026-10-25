from decimal import Decimal

from rest_framework.test import APITestCase

from apps.accounts.models import User
from apps.geography.models import Country, Currency
from apps.orders.models import Order

from .models import (
    Delivery,
    ShippingMethod,
    ShippingRate,
    ShippingZone,
)


class ShippingTestBase(APITestCase):

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
        )

        self.france = Country.objects.create(
            name="France",
            code="FR",
            phone_code="+33",
            currency=self.eur,
        )

        self.standard = ShippingMethod.objects.create(
            name="Standard",
            code="STANDARD",
            carrier="BOMBAA Express",
            estimated_days=3,
        )

        self.express = ShippingMethod.objects.create(
            name="Express",
            code="EXPRESS",
            carrier="BOMBAA Express",
            estimated_days=1,
        )

        self.inactive_method = ShippingMethod.objects.create(
            name="Méthode inactive",
            code="INACTIVE",
            estimated_days=5,
            is_active=False,
        )

        self.togo_zone = ShippingZone.objects.create(
            name="Zone Togo",
        )
        self.togo_zone.countries.add(self.togo)

        self.inactive_zone = ShippingZone.objects.create(
            name="Zone inactive",
            is_active=False,
        )
        self.inactive_zone.countries.add(self.france)

        self.light_rate = ShippingRate.objects.create(
            zone=self.togo_zone,
            method=self.standard,
            min_weight_grams=0,
            max_weight_grams=1000,
            price=Decimal("1500.00"),
            currency=self.xof,
        )

        self.heavy_rate = ShippingRate.objects.create(
            zone=self.togo_zone,
            method=self.standard,
            min_weight_grams=1001,
            max_weight_grams=5000,
            price=Decimal("2500.00"),
            currency=self.xof,
        )

        self.express_rate = ShippingRate.objects.create(
            zone=self.togo_zone,
            method=self.express,
            min_weight_grams=0,
            max_weight_grams=5000,
            price=Decimal("3000.00"),
            currency=self.xof,
        )

        ShippingRate.objects.create(
            zone=self.togo_zone,
            method=self.standard,
            min_weight_grams=0,
            max_weight_grams=5000,
            price=Decimal("999.00"),
            currency=self.xof,
            is_active=False,
        )

        ShippingRate.objects.create(
            zone=self.inactive_zone,
            method=self.inactive_method,
            min_weight_grams=0,
            max_weight_grams=5000,
            price=Decimal("500.00"),
            currency=self.eur,
        )

        self.admin_user = User.objects.create_superuser(
            email="shipping-admin@example.com",
            password="TestPassword123!",
            first_name="Admin",
            last_name="Shipping",
        )


class ShippingQuoteTests(ShippingTestBase):

    def test_quote_selects_cheapest_rate_for_weight(self):
        response = self.client.get(
            "/api/shipping/quote/?country=TG&weight_grams=800"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            Decimal(response.data["shipping_cost"]),
            Decimal("1500.00"),
        )
        self.assertEqual(response.data["currency"], "XOF")
        self.assertEqual(
            response.data["method"]["code"],
            "STANDARD",
        )
        self.assertEqual(response.data["estimated_days"], 3)

        response = self.client.get(
            "/api/shipping/quote/?country=TG&weight_grams=1500"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            Decimal(response.data["shipping_cost"]),
            Decimal("2500.00"),
        )

    def test_quote_can_select_a_specific_method(self):
        response = self.client.get(
            (
                "/api/shipping/quote/"
                "?country=TG&weight_grams=800&method=EXPRESS"
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            Decimal(response.data["shipping_cost"]),
            Decimal("3000.00"),
        )
        self.assertEqual(
            response.data["method"]["code"],
            "EXPRESS",
        )
        self.assertEqual(response.data["estimated_days"], 1)

    def test_quote_prefers_country_zone_over_global_zone(self):
        global_zone = ShippingZone.objects.create(
            name="Zone internationale de test",
        )

        ShippingRate.objects.create(
            zone=global_zone,
            method=self.standard,
            min_weight_grams=0,
            max_weight_grams=5000,
            price=Decimal("100.00"),
            currency=self.xof,
        )

        response = self.client.get(
            "/api/shipping/quote/?country=TG&weight_grams=800"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            Decimal(response.data["shipping_cost"]),
            Decimal("1500.00"),
        )
        self.assertEqual(
            response.data["zone"]["name"],
            "Zone Togo",
        )

        response = self.client.get(
            "/api/shipping/quote/?country=FR&weight_grams=800"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            Decimal(response.data["shipping_cost"]),
            Decimal("100.00"),
        )
        self.assertEqual(
            response.data["zone"]["name"],
            "Zone internationale de test",
        )

    def test_quote_rejects_country_without_zone(self):
        response = self.client.get(
            "/api/shipping/quote/?country=FR&weight_grams=800"
        )

        self.assertEqual(response.status_code, 400)

    def test_quote_rejects_weight_without_rate(self):
        response = self.client.get(
            "/api/shipping/quote/?country=TG&weight_grams=6000"
        )

        self.assertEqual(response.status_code, 400)

    def test_quote_rejects_unknown_country(self):
        response = self.client.get(
            "/api/shipping/quote/?country=XX&weight_grams=800"
        )

        self.assertEqual(response.status_code, 404)

    def test_quote_rejects_invalid_weight(self):
        response = self.client.get(
            "/api/shipping/quote/?country=TG&weight_grams=abc"
        )

        self.assertEqual(response.status_code, 400)


class ShippingCatalogTests(ShippingTestBase):

    def test_public_rate_list_filters_country_and_weight(self):
        response = self.client.get(
            "/api/shipping-rates/?country=TG&weight_grams=800"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            {
                rate["price"]
                for rate in response.data["results"]
            },
            {"1500.00", "3000.00"},
        )

        response = self.client.get(
            "/api/shipping-rates/?country=TG&weight_grams=1500"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            {
                rate["price"]
                for rate in response.data["results"]
            },
            {"2500.00", "3000.00"},
        )

        response = self.client.get(
            "/api/shipping-rates/?country=FR"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["results"], [])

    def test_public_only_returns_active_shipping_configuration(self):
        response = self.client.get("/api/shipping-zones/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            {
                zone["name"]
                for zone in response.data["results"]
            },
            {"Zone Togo"},
        )

        response = self.client.get("/api/shipping-methods/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            {
                method["code"]
                for method in response.data["results"]
            },
            {"STANDARD", "EXPRESS"},
        )

        response = self.client.get("/api/shipping-rates/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            {
                rate["price"]
                for rate in response.data["results"]
            },
            {"1500.00", "2500.00", "3000.00"},
        )

        self.client.force_authenticate(self.admin_user)

        response = self.client.get("/api/shipping-methods/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "INACTIVE",
            {
                method["code"]
                for method in response.data["results"]
            },
        )

    def test_anonymous_cannot_create_shipping_method(self):
        response = self.client.post(
            "/api/shipping-methods/",
            {
                "name": "Méthode pirate",
                "code": "PIRATE",
            },
            format="json",
        )

        self.assertIn(response.status_code, [401, 403])
        self.assertFalse(
            ShippingMethod.objects.filter(code="PIRATE").exists()
        )

    def test_admin_can_create_shipping_method(self):
        self.client.force_authenticate(self.admin_user)

        response = self.client.post(
            "/api/shipping-methods/",
            {
                "name": "Retrait en boutique",
                "code": "pickup",
                "estimated_days": 0,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["code"], "PICKUP")
        self.assertTrue(
            ShippingMethod.objects.filter(code="PICKUP").exists()
        )


class DeliveryTests(ShippingTestBase):

    def setUp(self):
        super().setUp()

        self.client_user = User.objects.create_user(
            email="delivery-client@example.com",
            password="TestPassword123!",
            first_name="Client",
            last_name="Delivery",
        )

        self.other_user = User.objects.create_user(
            email="delivery-other@example.com",
            password="TestPassword123!",
            first_name="Autre",
            last_name="Delivery",
        )

        self.order = Order.objects.create(
            user=self.client_user,
            reference="CMD-DELIVERY-001",
            status=Order.Status.CONFIRMED,
            subtotal=Decimal("10000.00"),
            shipping_cost=Decimal("1500.00"),
            discount_amount=Decimal("0.00"),
            total_amount=Decimal("11500.00"),
            currency="XOF",
        )

        self.other_order = Order.objects.create(
            user=self.other_user,
            reference="CMD-DELIVERY-002",
            status=Order.Status.CONFIRMED,
            subtotal=Decimal("5000.00"),
            shipping_cost=Decimal("1500.00"),
            discount_amount=Decimal("0.00"),
            total_amount=Decimal("6500.00"),
            currency="XOF",
        )

        self.delivery = Delivery.objects.create(
            order=self.order,
            shipping_method=self.standard,
            tracking_number="TRACK-001",
        )

        self.other_delivery = Delivery.objects.create(
            order=self.other_order,
            shipping_method=self.standard,
            tracking_number="TRACK-002",
        )

    def test_client_only_sees_own_deliveries(self):
        self.client.force_authenticate(self.client_user)

        response = self.client.get("/api/deliveries/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [
                delivery["id"]
                for delivery in response.data["results"]
            ],
            [self.delivery.id],
        )

        self.client.force_authenticate(self.admin_user)

        response = self.client.get("/api/deliveries/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            {
                delivery["id"]
                for delivery in response.data["results"]
            },
            {self.delivery.id, self.other_delivery.id},
        )

    def test_admin_updates_delivery_status_and_tracking(self):
        self.client.force_authenticate(self.admin_user)

        response = self.client.patch(
            f"/api/deliveries/{self.delivery.id}/",
            {
                "status": Delivery.Status.SHIPPED,
                "tracking_number": "TRACK-UPDATED",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)

        self.delivery.refresh_from_db()
        self.assertEqual(
            self.delivery.status,
            Delivery.Status.SHIPPED,
        )
        self.assertIsNotNone(self.delivery.shipped_at)
        self.assertIsNone(self.delivery.delivered_at)
        self.assertEqual(
            self.delivery.tracking_number,
            "TRACK-UPDATED",
        )

        response = self.client.patch(
            f"/api/deliveries/{self.delivery.id}/",
            {"status": Delivery.Status.DELIVERED},
            format="json",
        )

        self.assertEqual(response.status_code, 200)

        self.delivery.refresh_from_db()
        self.assertEqual(
            self.delivery.status,
            Delivery.Status.DELIVERED,
        )
        self.assertIsNotNone(self.delivery.delivered_at)

    def test_client_cannot_update_delivery(self):
        self.client.force_authenticate(self.client_user)

        response = self.client.patch(
            f"/api/deliveries/{self.delivery.id}/",
            {"status": Delivery.Status.DELIVERED},
            format="json",
        )

        self.assertEqual(response.status_code, 403)
