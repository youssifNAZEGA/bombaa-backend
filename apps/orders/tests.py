from decimal import Decimal

from rest_framework.test import APITestCase

from apps.accounts.models import Permission, Role, User
from apps.addresses.models import Address
from apps.cart.models import Cart, CartItem
from apps.catalog.models import Product, ProductVariant
from apps.payments.models import Payment, PaymentMethod, Transaction
from apps.stocks.models import Stock, StockMovement

from .models import Order, OrderItem


PERMISSION_NAMES = [
    "orders.view",
    "orders.create",
    "orders.update",
    "payments.view",
    "payments.create",
]


class OrderTestBase(APITestCase):

    def setUp(self):
        self.permissions = {
            name: Permission.objects.create(name=name)
            for name in PERMISSION_NAMES
        }

        self.client_role = Role.objects.create(
            name="TEST_CLIENT",
            description="Client de test",
        )

        self.client_role.permissions.set([
            self.permissions["orders.view"],
            self.permissions["orders.create"],
            self.permissions["payments.view"],
            self.permissions["payments.create"],
        ])

        self.admin_role = Role.objects.create(
            name="TEST_ADMIN",
            description="Administrateur de test",
        )

        self.admin_role.permissions.set(
            self.permissions.values()
        )

        self.client_user = self.create_user(
            "order-client@example.com",
            self.client_role,
        )

        self.admin_user = self.create_user(
            "order-admin@example.com",
            self.admin_role,
        )

        self.product = Product.objects.create(
            name="Produit commande",
            slug="produit-commande",
            base_price=Decimal("5000.00"),
        )

        self.variant = ProductVariant.objects.create(
            product=self.product,
            sku="ORDER-001",
            price=Decimal("5000.00"),
        )

        self.stock = Stock.objects.create(
            variant=self.variant,
            quantity=10,
            reserved_quantity=0,
            minimum_quantity=1,
        )

        self.address = Address.objects.create(
            user=self.client_user,
            first_name="Client",
            last_name="Commande",
            phone="+22890000011",
            address_line_1="1 rue du Test",
            city="Lomé",
            country="Togo",
        )

    def create_user(self, email, role):
        user = User.objects.create_user(
            email=email,
            password="TestPassword123!",
            first_name="Test",
            last_name="Order",
            phone=f"+228{abs(hash(email)) % 100000000:08d}",
        )

        user.roles.add(role)

        return user

    def create_order(
        self,
        *,
        user=None,
        status=Order.Status.PENDING,
        quantity=2,
    ):
        user = user or self.client_user

        subtotal = Decimal("5000.00") * quantity

        order = Order.objects.create(
            user=user,
            reference=f"CMD-TEST-{Order.objects.count() + 1:06d}",
            status=status,
            subtotal=subtotal,
            shipping_cost=Decimal("0.00"),
            discount_amount=Decimal("0.00"),
            total_amount=subtotal,
            currency="XOF",
        )

        OrderItem.objects.create(
            order=order,
            variant=self.variant,
            product_name=self.product.name,
            variant_description=self.variant.sku,
            sku=self.variant.sku,
            quantity=quantity,
            unit_price=self.variant.price,
            subtotal=subtotal,
        )

        if status == Order.Status.PENDING:
            self.stock.reserved_quantity += quantity

        elif status in [
            Order.Status.CONFIRMED,
            Order.Status.PROCESSING,
        ]:
            self.stock.quantity -= quantity

        self.stock.save()

        return order

    def create_pending_payment(self, order):
        method = PaymentMethod.objects.create(
            name="Mobile Money test",
            code=f"TEST_{order.id}",
            is_active=True,
        )

        payment = Payment.objects.create(
            order=order,
            payment_method=method,
            reference=f"PAY-{order.reference}",
            amount=order.total_amount,
            currency=order.currency,
            status=Payment.Status.PENDING,
        )

        transaction = Transaction.objects.create(
            payment=payment,
            reference=f"TXN-{order.reference}",
            amount=order.total_amount,
            currency=order.currency,
            status=Transaction.Status.PENDING,
        )

        return payment, transaction


class OrderCreateTests(OrderTestBase):

    def test_create_order_ignores_client_supplied_amounts(self):
        cart = Cart.objects.create(user=self.client_user)

        CartItem.objects.create(
            cart=cart,
            variant=self.variant,
            quantity=2,
        )

        self.client.force_authenticate(self.client_user)

        response = self.client.post(
            "/api/orders/",
            {
                "address_id": self.address.id,
                "shipping_cost": "99999.00",
                "discount_amount": "10000.00",
                "notes": "Commande de test",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)

        order = Order.objects.get(user=self.client_user)

        self.assertEqual(order.subtotal, Decimal("10000.00"))
        self.assertEqual(order.shipping_cost, Decimal("0.00"))
        self.assertEqual(order.discount_amount, Decimal("0.00"))
        self.assertEqual(order.total_amount, Decimal("10000.00"))

        self.stock.refresh_from_db()
        self.assertEqual(self.stock.quantity, 10)
        self.assertEqual(self.stock.reserved_quantity, 2)

        self.assertEqual(cart.items.count(), 0)

    def test_create_order_requires_orders_create_permission(self):
        user_without_role = User.objects.create_user(
            email="no-role-order@example.com",
            password="TestPassword123!",
            first_name="Sans",
            last_name="Role",
        )

        self.client.force_authenticate(user_without_role)

        response = self.client.post(
            "/api/orders/",
            {"address_id": self.address.id},
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            Order.objects.filter(user=user_without_role).exists()
        )


class OrderCancellationTests(OrderTestBase):

    def test_client_can_cancel_pending_order(self):
        order = self.create_order()

        payment, transaction = self.create_pending_payment(order)

        self.client.force_authenticate(self.client_user)

        response = self.client.post(
            f"/api/orders/{order.id}/cancel/"
        )

        self.assertEqual(response.status_code, 200)

        order.refresh_from_db()
        payment.refresh_from_db()
        transaction.refresh_from_db()
        self.stock.refresh_from_db()

        self.assertEqual(order.status, Order.Status.CANCELLED)
        self.assertEqual(payment.status, Payment.Status.CANCELLED)
        self.assertEqual(
            transaction.status,
            Transaction.Status.CANCELLED,
        )
        self.assertEqual(self.stock.quantity, 10)
        self.assertEqual(self.stock.reserved_quantity, 0)

    def test_client_cannot_cancel_confirmed_order(self):
        order = self.create_order(
            status=Order.Status.CONFIRMED,
        )

        self.client.force_authenticate(self.client_user)

        response = self.client.post(
            f"/api/orders/{order.id}/cancel/"
        )

        self.assertEqual(response.status_code, 400)

        order.refresh_from_db()
        self.stock.refresh_from_db()

        self.assertEqual(order.status, Order.Status.CONFIRMED)
        self.assertEqual(self.stock.quantity, 8)

    def test_client_cannot_cancel_another_user_order(self):
        other_user = self.create_user(
            "other-order-client@example.com",
            self.client_role,
        )

        order = self.create_order(user=other_user)

        self.client.force_authenticate(self.client_user)

        response = self.client.post(
            f"/api/orders/{order.id}/cancel/"
        )

        self.assertEqual(response.status_code, 404)

        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.PENDING)

    def test_admin_can_cancel_confirmed_order_and_restock(self):
        order = self.create_order(
            status=Order.Status.CONFIRMED,
        )

        self.client.force_authenticate(self.admin_user)

        response = self.client.post(
            f"/api/orders/{order.id}/cancel/"
        )

        self.assertEqual(response.status_code, 200)

        order.refresh_from_db()
        self.stock.refresh_from_db()

        self.assertEqual(order.status, Order.Status.CANCELLED)
        self.assertEqual(self.stock.quantity, 10)
        self.assertEqual(self.stock.reserved_quantity, 0)

        self.assertTrue(
            StockMovement.objects.filter(
                stock=self.stock,
                movement_type=StockMovement.MOVEMENT_IN,
                quantity=2,
            ).exists()
        )

    def test_admin_cannot_cancel_shipped_order(self):
        order = self.create_order(
            status=Order.Status.CONFIRMED,
        )

        order.status = Order.Status.SHIPPED
        order.save(update_fields=["status"])

        self.client.force_authenticate(self.admin_user)

        response = self.client.post(
            f"/api/orders/{order.id}/cancel/"
        )

        self.assertEqual(response.status_code, 400)

        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.SHIPPED)


class OrderStatusTests(OrderTestBase):

    def test_admin_can_advance_order_status(self):
        order = self.create_order(
            status=Order.Status.CONFIRMED,
        )

        self.client.force_authenticate(self.admin_user)

        for new_status in [
            Order.Status.PROCESSING,
            Order.Status.SHIPPED,
            Order.Status.DELIVERED,
            Order.Status.COMPLETED,
        ]:
            response = self.client.patch(
                f"/api/orders/{order.id}/status/",
                {"status": new_status},
                format="json",
            )

            self.assertEqual(response.status_code, 200)

            order.refresh_from_db()
            self.assertEqual(order.status, new_status)

    def test_invalid_status_transition_is_rejected(self):
        order = self.create_order(
            status=Order.Status.CONFIRMED,
        )

        self.client.force_authenticate(self.admin_user)

        response = self.client.patch(
            f"/api/orders/{order.id}/status/",
            {"status": Order.Status.DELIVERED},
            format="json",
        )

        self.assertEqual(response.status_code, 400)

        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CONFIRMED)

    def test_client_cannot_update_order_status(self):
        order = self.create_order(
            status=Order.Status.CONFIRMED,
        )

        self.client.force_authenticate(self.client_user)

        response = self.client.patch(
            f"/api/orders/{order.id}/status/",
            {"status": Order.Status.PROCESSING},
            format="json",
        )

        self.assertEqual(response.status_code, 403)

        order.refresh_from_db()
        self.assertEqual(order.status, Order.Status.CONFIRMED)


class OrderListingTests(OrderTestBase):

    def test_admin_sees_all_orders_and_client_sees_own(self):
        other_user = self.create_user(
            "other-list-client@example.com",
            self.client_role,
        )

        own_order = self.create_order(user=self.client_user)
        other_order = self.create_order(user=other_user)

        self.client.force_authenticate(self.client_user)

        response = self.client.get("/api/orders/")

        self.assertEqual(response.status_code, 200)

        ids = [order["id"] for order in response.data]

        self.assertIn(own_order.id, ids)
        self.assertNotIn(other_order.id, ids)

        self.client.force_authenticate(self.admin_user)

        response = self.client.get("/api/orders/")

        self.assertEqual(response.status_code, 200)

        ids = [order["id"] for order in response.data]

        self.assertIn(own_order.id, ids)
        self.assertIn(other_order.id, ids)
