from decimal import Decimal

from rest_framework.test import APITestCase

from apps.accounts.models import Permission, Role, User
from apps.addresses.models import Address
from apps.cart.models import Cart, CartItem
from apps.catalog.models import Product, ProductVariant
from apps.orders.models import Order
from apps.orders.services import OrderService
from apps.payments.models import PaymentMethod
from apps.payments.services import PaymentService
from apps.shipping.models import Delivery
from apps.stocks.models import Stock
from apps.wishlist.models import Wishlist, WishlistItem

from .models import Notification, NotificationPreference
from .services import NotificationService


PERMISSION_NAMES = [
    "notifications.view",
    "notifications.create",
    "orders.view",
    "orders.create",
    "orders.update",
    "payments.view",
    "payments.create",
    "shipping.view",
    "shipping.update",
    "products.view",
    "products.create",
    "products.update",
]


class NotificationTestBase(APITestCase):

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
            self.permissions["notifications.view"],
            self.permissions["orders.view"],
            self.permissions["orders.create"],
            self.permissions["payments.view"],
            self.permissions["payments.create"],
            self.permissions["shipping.view"],
            self.permissions["products.view"],
        ])

        self.admin_role = Role.objects.create(
            name="TEST_ADMIN",
            description="Administrateur de test",
        )
        self.admin_role.permissions.set(
            self.permissions.values()
        )

        self.client_user = self.create_user(
            "notification-client@example.com",
            self.client_role,
        )
        self.other_user = self.create_user(
            "notification-other@example.com",
            self.client_role,
        )
        self.admin_user = self.create_user(
            "notification-admin@example.com",
            self.admin_role,
            is_staff=True,
        )

        self.product = Product.objects.create(
            name="Produit notification",
            slug="produit-notification",
            base_price=Decimal("5000.00"),
            is_active=True,
        )

        self.variant = ProductVariant.objects.create(
            product=self.product,
            sku="NOTIF-001",
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
            last_name="Notification",
            phone="+22890000101",
            address_line_1="1 rue des Notifications",
            city="Lomé",
            country="Togo",
        )

    def create_user(self, email, role, is_staff=False):
        user = User.objects.create_user(
            email=email,
            password="TestPassword123!",
            first_name="Test",
            last_name="Notification",
            phone=f"+228{abs(hash(email)) % 100000000:08d}",
            is_staff=is_staff,
        )
        user.roles.add(role)
        return user

    def create_order_via_service(self, quantity=2):
        cart, _created = Cart.objects.get_or_create(
            user=self.client_user
        )
        CartItem.objects.create(
            cart=cart,
            variant=self.variant,
            quantity=quantity,
        )

        return OrderService.create_order(
            user=self.client_user,
            address=self.address,
        )

    def create_payment_for_order(self, order):
        method = PaymentMethod.objects.create(
            name="Mobile Money notification",
            code=f"NOTIF-{order.id}",
            is_active=True,
        )

        return PaymentService.create_payment(
            order=order,
            payment_method=method,
        )

    def notification_events(self, user=None):
        return list(
            Notification.objects
            .filter(user=user or self.client_user)
            .order_by("created_at")
            .values_list("event", flat=True)
        )


class NotificationAPITests(NotificationTestBase):

    def setUp(self):
        super().setUp()

        self.own_notification = Notification.objects.create(
            user=self.client_user,
            event=Notification.Event.PROMOTION,
            title="Promotion client",
            message="Une promotion vous attend.",
        )
        self.other_notification = Notification.objects.create(
            user=self.other_user,
            event=Notification.Event.NEW_PRODUCT,
            title="Produit pour un autre client",
            message="Cette notification ne doit pas être visible.",
        )

    def test_user_only_sees_own_notifications(self):
        self.client.force_authenticate(self.client_user)

        response = self.client.get("/api/notifications/")

        self.assertEqual(response.status_code, 200)

        results = response.data.get(
            "results",
            response.data,
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(
            results[0]["id"],
            self.own_notification.id,
        )

    def test_user_can_mark_one_notification_as_read(self):
        self.client.force_authenticate(self.client_user)

        response = self.client.post(
            f"/api/notifications/{self.own_notification.id}/read/"
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["is_read"])

        self.own_notification.refresh_from_db()
        self.assertTrue(self.own_notification.is_read)
        self.assertIsNotNone(self.own_notification.read_at)

    def test_user_can_mark_all_notifications_as_read(self):
        Notification.objects.create(
            user=self.client_user,
            event=Notification.Event.ORDER_CREATED,
            title="Deuxième notification",
            message="Notification non lue.",
        )

        self.client.force_authenticate(self.client_user)

        response = self.client.post(
            "/api/notifications/read-all/"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["updated"], 2)
        self.assertFalse(
            Notification.objects.filter(
                user=self.client_user,
                is_read=False,
            ).exists()
        )

    def test_unread_count_and_filters(self):
        Notification.objects.create(
            user=self.client_user,
            event=Notification.Event.ORDER_CREATED,
            title="Déjà lue",
            message="Notification lue.",
            is_read=True,
        )

        self.client.force_authenticate(self.client_user)

        response = self.client.get(
            "/api/notifications/unread-count/"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["unread_count"], 1)

        response = self.client.get(
            "/api/notifications/?unread=true"
        )

        results = response.data.get(
            "results",
            response.data,
        )

        self.assertEqual(len(results), 1)
        self.assertEqual(
            results[0]["event"],
            Notification.Event.PROMOTION,
        )

    def test_preferences_are_created_and_can_be_updated(self):
        self.client.force_authenticate(self.client_user)

        response = self.client.get(
            "/api/notifications/preferences/"
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["in_app_enabled"])
        self.assertFalse(response.data["email_enabled"])

        response = self.client.patch(
            "/api/notifications/preferences/",
            {
                "in_app_enabled": False,
                "email_enabled": True,
                "sms_enabled": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["in_app_enabled"])
        self.assertTrue(response.data["email_enabled"])
        self.assertTrue(response.data["sms_enabled"])

        result = NotificationService.notify(
            user=self.client_user,
            event=Notification.Event.PROMOTION,
            title="Notification désactivée",
            message="Ne doit pas être créée.",
        )

        self.assertIsNone(result)

    def test_admin_can_create_targeted_notification(self):
        self.client.force_authenticate(self.admin_user)

        response = self.client.post(
            "/api/notifications/",
            {
                "user": self.client_user.id,
                "event": Notification.Event.NEW_COUPON,
                "title": "Nouveau coupon",
                "message": "Un coupon de bienvenue est disponible.",
                "data": {"code": "BIENVENUE"},
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            response.data["event"],
            Notification.Event.NEW_COUPON,
        )
        self.assertTrue(
            Notification.objects.filter(
                user=self.client_user,
                event=Notification.Event.NEW_COUPON,
            ).exists()
        )

    def test_client_cannot_create_notification(self):
        self.client.force_authenticate(self.client_user)

        response = self.client.post(
            "/api/notifications/",
            {
                "user": self.client_user.id,
                "event": Notification.Event.PROMOTION,
                "title": "Interdit",
                "message": "Interdit.",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 403)

    def test_admin_can_broadcast_notification_to_clients(self):
        self.client.force_authenticate(self.admin_user)

        response = self.client.post(
            "/api/notifications/broadcast/",
            {
                "event": Notification.Event.PROMOTION,
                "title": "Promotion BOMBAA",
                "message": "Profitez de nos offres.",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["created"], 2)

        self.assertEqual(
            Notification.objects.filter(
                event=Notification.Event.PROMOTION,
                title="Promotion BOMBAA",
            ).count(),
            2,
        )


class NotificationOrderFlowTests(NotificationTestBase):

    def test_order_creation_creates_notification(self):
        order = self.create_order_via_service()

        self.assertTrue(
            Notification.objects.filter(
                user=self.client_user,
                event=Notification.Event.ORDER_CREATED,
                order=order,
            ).exists()
        )

    def test_payment_success_creates_payment_and_order_notifications(self):
        order = self.create_order_via_service()
        payment = self.create_payment_for_order(order)

        PaymentService.mark_payment_success(
            payment=payment,
            external_reference="EXT-NOTIF-001",
        )

        events = self.notification_events()

        self.assertIn(
            Notification.Event.ORDER_CREATED,
            events,
        )
        self.assertIn(
            Notification.Event.PAYMENT_CONFIRMED,
            events,
        )
        self.assertIn(
            Notification.Event.ORDER_CONFIRMED,
            events,
        )

    def test_payment_failure_creates_failure_and_cancellation_notifications(self):
        order = self.create_order_via_service()
        payment = self.create_payment_for_order(order)

        PaymentService.mark_payment_failed(
            payment=payment,
            response_message="Refus de test.",
        )

        events = self.notification_events()

        self.assertIn(
            Notification.Event.PAYMENT_FAILED,
            events,
        )
        self.assertIn(
            Notification.Event.ORDER_CANCELLED,
            events,
        )

    def test_order_status_changes_create_notifications(self):
        order = self.create_order_via_service()
        payment = self.create_payment_for_order(order)

        PaymentService.mark_payment_success(payment=payment)

        for new_status in [
            Order.Status.PROCESSING,
            Order.Status.SHIPPED,
            Order.Status.DELIVERED,
        ]:
            order = OrderService.update_status(
                order=order,
                new_status=new_status,
                actor=self.admin_user,
            )

        events = self.notification_events()

        self.assertIn(
            Notification.Event.ORDER_PROCESSING,
            events,
        )
        self.assertIn(
            Notification.Event.ORDER_SHIPPED,
            events,
        )
        self.assertIn(
            Notification.Event.ORDER_DELIVERED,
            events,
        )

    def test_cancellation_creates_notification(self):
        order = self.create_order_via_service()

        OrderService.cancel_order(
            order=order,
            actor=self.client_user,
        )

        self.assertTrue(
            Notification.objects.filter(
                user=self.client_user,
                event=Notification.Event.ORDER_CANCELLED,
                order=order,
            ).exists()
        )

    def test_refund_notification_can_be_created(self):
        order = self.create_order_via_service()
        payment = self.create_payment_for_order(order)

        PaymentService.mark_payment_success(payment=payment)

        NotificationService.refund_processed(
            payment,
            amount=Decimal("1000.00"),
        )

        notification = Notification.objects.get(
            user=self.client_user,
            event=Notification.Event.REFUND,
            order=order,
        )

        self.assertEqual(
            notification.data["amount"],
            "1000.00",
        )
        self.assertEqual(
            notification.data["currency"],
            "XOF",
        )


class NotificationCatalogueTests(NotificationTestBase):

    def test_new_product_notifies_clients(self):
        NotificationPreference.objects.create(
            user=self.client_user,
            in_app_enabled=True,
        )

        created = NotificationService.new_product(
            self.product
        )

        self.assertEqual(created, 2)
        self.assertTrue(
            Notification.objects.filter(
                user=self.client_user,
                event=Notification.Event.NEW_PRODUCT,
                product=self.product,
            ).exists()
        )

    def test_back_in_stock_notifies_wishlist_owner(self):
        wishlist = Wishlist.objects.create(
            user=self.client_user
        )
        WishlistItem.objects.create(
            wishlist=wishlist,
            variant=self.variant,
        )

        self.stock.quantity = 0
        self.stock.save(update_fields=["quantity"])

        created = NotificationService.back_in_stock(
            self.variant
        )

        self.assertEqual(created, 1)
        self.assertTrue(
            Notification.objects.filter(
                user=self.client_user,
                event=Notification.Event.BACK_IN_STOCK,
                product=self.product,
            ).exists()
        )

    def test_new_product_created_through_api_notifies_clients(self):
        self.client.force_authenticate(self.admin_user)

        response = self.client.post(
            "/api/products/",
            {
                "name": "Nouveau produit API",
                "slug": "nouveau-produit-api",
                "base_price": "4500.00",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)

        product_id = response.data["id"]

        self.assertTrue(
            Notification.objects.filter(
                user=self.client_user,
                event=Notification.Event.NEW_PRODUCT,
                product_id=product_id,
            ).exists()
        )

    def test_delivery_status_change_notifies_customer(self):
        order = self.create_order_via_service()

        delivery = Delivery.objects.create(
            order=order,
            status=Delivery.Status.PENDING,
        )

        self.client.force_authenticate(self.admin_user)

        response = self.client.patch(
            f"/api/deliveries/{delivery.id}/",
            {"status": Delivery.Status.SHIPPED},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            Notification.objects.filter(
                user=self.client_user,
                event=Notification.Event.ORDER_SHIPPED,
                order=order,
            ).exists()
        )

    def test_stock_update_notifies_wishlist_owner(self):
        wishlist = Wishlist.objects.create(
            user=self.client_user
        )
        WishlistItem.objects.create(
            wishlist=wishlist,
            variant=self.variant,
        )

        self.stock.quantity = 0
        self.stock.save(update_fields=["quantity"])

        self.client.force_authenticate(self.admin_user)

        response = self.client.patch(
            f"/api/stocks/{self.stock.id}/",
            {"quantity": 4},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            Notification.objects.filter(
                user=self.client_user,
                event=Notification.Event.BACK_IN_STOCK,
            ).exists()
        )
