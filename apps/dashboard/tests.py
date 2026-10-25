from datetime import datetime
from decimal import Decimal

from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.models import Permission, Role, User
from apps.catalog.models import (
    Category,
    Product,
    ProductCategory,
    ProductVariant,
)
from apps.geography.models import Country, Currency
from apps.orders.models import Order, OrderAddress, OrderItem
from apps.payments.models import Payment, PaymentMethod
from apps.stocks.models import Stock


class DashboardTestBase(APITestCase):

    def setUp(self):
        self.permission = Permission.objects.create(
            name="dashboard.view"
        )

        self.client_role = Role.objects.create(
            name="TEST_CLIENT",
            description="Client de test",
        )

        self.admin_role = Role.objects.create(
            name="TEST_ADMIN",
            description="Administrateur de test",
        )
        self.admin_role.permissions.add(self.permission)

        self.admin_user = self.create_user(
            "dashboard-admin@example.com",
            self.admin_role,
            is_staff=True,
        )
        self.client_one = self.create_user(
            "dashboard-client-one@example.com",
            self.client_role,
        )
        self.client_two = self.create_user(
            "dashboard-client-two@example.com",
            self.client_role,
        )

        self.currency = Currency.objects.create(
            code="XOF",
            name="Franc CFA",
            symbol="F",
            is_base=True,
        )

        self.togo = Country.objects.create(
            name="Togo",
            code="TG",
            currency=self.currency,
        )
        self.benin = Country.objects.create(
            name="Bénin",
            code="BJ",
            currency=self.currency,
        )

        self.category_clothes = Category.objects.create(
            name="Vêtements",
            slug="vetements",
        )
        self.category_shoes = Category.objects.create(
            name="Chaussures",
            slug="chaussures",
        )

        self.product_a = Product.objects.create(
            name="Produit A",
            slug="produit-a",
            base_price=Decimal("5000.00"),
            is_active=True,
        )
        self.product_b = Product.objects.create(
            name="Produit B",
            slug="produit-b",
            base_price=Decimal("7000.00"),
            is_active=True,
        )
        self.product_c = Product.objects.create(
            name="Produit C",
            slug="produit-c",
            base_price=Decimal("3000.00"),
            is_active=True,
        )

        ProductCategory.objects.create(
            product=self.product_a,
            category=self.category_clothes,
        )
        ProductCategory.objects.create(
            product=self.product_b,
            category=self.category_shoes,
        )
        ProductCategory.objects.create(
            product=self.product_c,
            category=self.category_clothes,
        )

        self.variant_a = ProductVariant.objects.create(
            product=self.product_a,
            sku="DASH-A",
            price=Decimal("5000.00"),
        )
        self.variant_b = ProductVariant.objects.create(
            product=self.product_b,
            sku="DASH-B",
            price=Decimal("7000.00"),
        )
        self.variant_c = ProductVariant.objects.create(
            product=self.product_c,
            sku="DASH-C",
            price=Decimal("3000.00"),
        )

        Stock.objects.create(
            variant=self.variant_a,
            quantity=5,
            reserved_quantity=0,
        )
        Stock.objects.create(
            variant=self.variant_b,
            quantity=0,
            reserved_quantity=0,
        )
        Stock.objects.create(
            variant=self.variant_c,
            quantity=0,
            reserved_quantity=0,
        )

        self.payment_method = PaymentMethod.objects.create(
            name="Mobile Money dashboard",
            code="DASH_MOBILE",
            is_active=True,
        )

        self.order_one = self.create_order(
            user=self.client_one,
            reference="CMD-DASH-000001",
            status=Order.Status.CONFIRMED,
            total=Decimal("10000.00"),
            country=self.togo,
            created_at=datetime(2026, 10, 10, 12, 0),
        )
        self.order_two = self.create_order(
            user=self.client_two,
            reference="CMD-DASH-000002",
            status=Order.Status.DELIVERED,
            total=Decimal("20000.00"),
            country=self.benin,
            created_at=datetime(2026, 9, 10, 12, 0),
        )
        self.order_three = self.create_order(
            user=self.client_one,
            reference="CMD-DASH-000003",
            status=Order.Status.CANCELLED,
            total=Decimal("5000.00"),
            country=self.togo,
            created_at=datetime(2026, 9, 11, 12, 0),
        )
        self.order_four = self.create_order(
            user=self.client_two,
            reference="CMD-DASH-000004",
            status=Order.Status.PENDING,
            total=Decimal("7000.00"),
            country=self.togo,
            created_at=datetime(2026, 9, 12, 12, 0),
        )

        self.create_item(
            order=self.order_one,
            variant=self.variant_a,
            product_name=self.product_a.name,
            quantity=2,
            unit_price=Decimal("5000.00"),
            subtotal=Decimal("10000.00"),
        )
        self.create_item(
            order=self.order_two,
            variant=self.variant_b,
            product_name=self.product_b.name,
            quantity=3,
            unit_price=Decimal("7000.00"),
            subtotal=Decimal("21000.00"),
        )
        self.create_item(
            order=self.order_three,
            variant=self.variant_a,
            product_name=self.product_a.name,
            quantity=1,
            unit_price=Decimal("5000.00"),
            subtotal=Decimal("5000.00"),
        )
        self.create_item(
            order=self.order_four,
            variant=self.variant_c,
            product_name=self.product_c.name,
            quantity=1,
            unit_price=Decimal("3000.00"),
            subtotal=Decimal("3000.00"),
        )

        self.success_payment(
            order=self.order_one,
            paid_at=datetime(2026, 10, 10, 13, 0),
        )
        self.success_payment(
            order=self.order_two,
            paid_at=datetime(2026, 9, 10, 13, 0),
        )

        Payment.objects.create(
            order=self.order_three,
            payment_method=self.payment_method,
            reference="PAY-DASH-000003",
            amount=self.order_three.total_amount,
            currency=self.order_three.currency,
            status=Payment.Status.FAILED,
        )
        Payment.objects.create(
            order=self.order_four,
            payment_method=self.payment_method,
            reference="PAY-DASH-000004",
            amount=self.order_four.total_amount,
            currency=self.order_four.currency,
            status=Payment.Status.PENDING,
        )

    def create_user(self, email, role, is_staff=False):
        user = User.objects.create_user(
            email=email,
            password="TestPassword123!",
            first_name="Dashboard",
            last_name="Test",
            phone=f"+228{abs(hash(email)) % 100000000:08d}",
            is_staff=is_staff,
        )
        user.roles.add(role)
        return user

    def create_order(
        self,
        *,
        user,
        reference,
        status,
        total,
        country,
        created_at,
    ):
        order = Order.objects.create(
            user=user,
            reference=reference,
            status=status,
            subtotal=total,
            shipping_cost=Decimal("0.00"),
            discount_amount=Decimal("0.00"),
            total_amount=total,
            currency="XOF",
        )

        OrderAddress.objects.create(
            order=order,
            recipient_name="Client Dashboard",
            phone="+22890000200",
            address_line1="1 rue du Dashboard",
            city="Lomé",
            country_name=country.name,
            country_code=country.code,
        )

        Order.objects.filter(pk=order.pk).update(
            created_at=timezone.make_aware(created_at)
        )

        return order

    def create_item(
        self,
        *,
        order,
        variant,
        product_name,
        quantity,
        unit_price,
        subtotal,
    ):
        return OrderItem.objects.create(
            order=order,
            variant=variant,
            product_name=product_name,
            variant_description=variant.sku,
            sku=variant.sku,
            quantity=quantity,
            unit_price=unit_price,
            subtotal=subtotal,
        )

    def success_payment(self, *, order, paid_at):
        return Payment.objects.create(
            order=order,
            payment_method=self.payment_method,
            reference=f"PAY-{order.reference}",
            amount=order.total_amount,
            currency=order.currency,
            status=Payment.Status.SUCCESS,
            paid_at=timezone.make_aware(paid_at),
        )


class DashboardPermissionTests(DashboardTestBase):

    def test_client_cannot_access_dashboard(self):
        self.client.force_authenticate(self.client_one)

        response = self.client.get(
            "/api/dashboard/overview/"
        )

        self.assertEqual(response.status_code, 403)

    def test_admin_can_access_dashboard(self):
        self.client.force_authenticate(self.admin_user)

        response = self.client.get(
            "/api/dashboard/overview/"
        )

        self.assertEqual(response.status_code, 200)


class DashboardOverviewTests(DashboardTestBase):

    def setUp(self):
        super().setUp()
        self.client.force_authenticate(self.admin_user)

    def test_overview_returns_main_indicators(self):
        response = self.client.get(
            "/api/dashboard/overview/"
        )

        self.assertEqual(response.status_code, 200)

        data = response.data

        self.assertEqual(
            data["revenue"]["by_currency"],
            [{"currency": "XOF", "amount": "30000.00"}],
        )
        self.assertEqual(data["orders"]["total_orders"], 4)
        self.assertEqual(
            data["orders"]["by_status"][Order.Status.CANCELLED],
            1,
        )
        self.assertEqual(
            data["orders"]["average_order_value"],
            [{
                "currency": "XOF",
                "amount": "12333.33",
                "order_count": 3,
            }],
        )
        self.assertEqual(
            data["customers"]["total_customers"],
            2,
        )
        self.assertEqual(
            data["customers"]["returning_customers"],
            1,
        )
        self.assertEqual(
            data["products"]["total_products"],
            3,
        )
        self.assertEqual(
            data["products"]["available_products"],
            1,
        )
        self.assertEqual(
            data["products"]["out_of_stock_products"],
            2,
        )
        self.assertEqual(len(data["recent_orders"]), 4)
        self.assertEqual(len(data["recent_payments"]), 4)

    def test_best_and_worst_sellers(self):
        response = self.client.get(
            "/api/dashboard/products/"
        )

        self.assertEqual(response.status_code, 200)

        best = response.data["best_sellers"]

        self.assertEqual(best[0]["product_id"], self.product_b.id)
        self.assertEqual(best[0]["quantity_sold"], 3)
        self.assertEqual(
            best[0]["revenue_by_currency"],
            [{"currency": "XOF", "amount": "21000.00"}],
        )

        worst = response.data["worst_sellers"]

        self.assertEqual(worst[0]["product_id"], self.product_c.id)
        self.assertEqual(worst[0]["quantity_sold"], 0)

    def test_sales_by_period_country_and_category(self):
        response = self.client.get(
            "/api/dashboard/sales/?group_by=month"
        )

        self.assertEqual(response.status_code, 200)

        periods = {
            item["period"]: item
            for item in response.data["by_period"]
        }

        self.assertEqual(
            periods["2026-10-01"]["revenue_by_currency"],
            [{"currency": "XOF", "amount": "10000.00"}],
        )
        self.assertEqual(
            periods["2026-09-01"]["revenue_by_currency"],
            [{"currency": "XOF", "amount": "20000.00"}],
        )

        countries = {
            item["country_code"]: item
            for item in response.data["by_country"]
        }

        self.assertEqual(
            countries["TG"]["revenue_by_currency"],
            [{"currency": "XOF", "amount": "10000.00"}],
        )
        self.assertEqual(
            countries["BJ"]["revenue_by_currency"],
            [{"currency": "XOF", "amount": "20000.00"}],
        )

        categories = {
            item["category_name"]: item
            for item in response.data["by_category"]
        }

        self.assertEqual(
            categories["Chaussures"]["quantity_sold"],
            3,
        )
        self.assertEqual(
            categories["Vêtements"]["quantity_sold"],
            2,
        )

    def test_date_filter_limits_revenue_and_orders(self):
        response = self.client.get(
            "/api/dashboard/overview/"
            "?date_from=2026-10-01&date_to=2026-10-31"
        )

        self.assertEqual(response.status_code, 200)

        data = response.data

        self.assertEqual(
            data["revenue"]["by_currency"],
            [{"currency": "XOF", "amount": "10000.00"}],
        )
        self.assertEqual(data["orders"]["total_orders"], 1)
        self.assertEqual(len(data["recent_orders"]), 1)

    def test_country_filter_limits_dashboard(self):
        response = self.client.get(
            "/api/dashboard/overview/?country=BJ"
        )

        self.assertEqual(response.status_code, 200)

        data = response.data

        self.assertEqual(
            data["filters"]["country"]["code"],
            "BJ",
        )
        self.assertEqual(
            data["revenue"]["by_currency"],
            [{"currency": "XOF", "amount": "20000.00"}],
        )
        self.assertEqual(data["orders"]["total_orders"], 1)
        self.assertEqual(
            data["customers"]["active_customers"],
            1,
        )

    def test_customers_and_orders_endpoints(self):
        response = self.client.get(
            "/api/dashboard/customers/"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["summary"]["total_customers"],
            2,
        )
        self.assertEqual(
            response.data["summary"]["active_customers"],
            2,
        )

        response = self.client.get(
            "/api/dashboard/orders/"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["summary"]["total_orders"],
            4,
        )
        self.assertEqual(
            len(response.data["recent_orders"]),
            4,
        )

    def test_invalid_dashboard_parameters_are_rejected(self):
        response = self.client.get(
            "/api/dashboard/overview/?date_from=invalid"
        )

        self.assertEqual(response.status_code, 400)

        response = self.client.get(
            "/api/dashboard/overview/?country=ZZ"
        )

        self.assertEqual(response.status_code, 400)

        response = self.client.get(
            "/api/dashboard/sales/?group_by=quarter"
        )

        self.assertEqual(response.status_code, 400)
