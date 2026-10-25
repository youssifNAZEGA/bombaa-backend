import hashlib

from django.test import override_settings
from rest_framework.test import APITestCase
from decimal import Decimal

from django.test import TestCase

from apps.accounts.models import User
from apps.catalog.models import Product, ProductVariant
from apps.geography.models import Country, Currency
from apps.stocks.models import Stock, StockMovement
from apps.orders.models import Order, OrderAddress, OrderItem
from apps.payments.models import PaymentMethod, Payment, Transaction
from apps.payments.services import PaymentService


class PaymentStockTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="test-bombaa@example.com",
            password="TestPassword123!",
            first_name="Test",
            last_name="Client",
            phone="+22890000001",
        )

        self.product = Product.objects.create(
            name="T-shirt de test",
            slug="t-shirt-test",
            base_price=Decimal("8500.00"),
        )

        self.variant = ProductVariant.objects.create(
            product=self.product,
            sku="TEST-TSHIRT-001",
            price=Decimal("8500.00"),
        )

        self.stock = Stock.objects.create(
            variant=self.variant,
            quantity=10,
            reserved_quantity=2,
            minimum_quantity=1,
        )

        self.order = Order.objects.create(
            user=self.user,
            reference="CMD-TEST-000001",
            status=Order.Status.PENDING,
            subtotal=Decimal("17000.00"),
            shipping_cost=Decimal("1000.00"),
            discount_amount=Decimal("0.00"),
            total_amount=Decimal("18000.00"),
            currency="XOF",
        )

        self.item = OrderItem.objects.create(
            order=self.order,
            variant=self.variant,
            product_name=self.product.name,
            variant_description="Version test",
            sku=self.variant.sku,
            quantity=2,
            unit_price=Decimal("8500.00"),
            subtotal=Decimal("17000.00"),
        )

        self.method = PaymentMethod.objects.create(
            name="Mobile Money Test",
            code="TEST_MOBILE_MONEY",
            is_active=True,
        )

        self.payment = Payment.objects.create(
            order=self.order,
            payment_method=self.method,
            reference="PAY-TEST-000001",
            amount=Decimal("18000.00"),
            currency="XOF",
            status=Payment.Status.PENDING,
        )

        self.transaction = Transaction.objects.create(
            payment=self.payment,
            reference="TXN-TEST-000001",
            amount=Decimal("18000.00"),
            currency="XOF",
            status=Transaction.Status.PENDING,
        )

    def test_successful_payment_deducts_stock(self):
        PaymentService.mark_payment_success(
            payment=self.payment,
            external_reference="EXT-TEST-001",
            response_message="Paiement de test confirmé",
        )

        self.stock.refresh_from_db()
        self.order.refresh_from_db()
        self.payment.refresh_from_db()
        self.transaction.refresh_from_db()

        self.assertEqual(self.stock.quantity, 8)
        self.assertEqual(self.stock.reserved_quantity, 0)
        self.assertEqual(self.order.status, Order.Status.CONFIRMED)
        self.assertEqual(self.payment.status, Payment.Status.SUCCESS)
        self.assertEqual(
            self.transaction.status,
            Transaction.Status.SUCCESS,
        )
        self.assertEqual(
            StockMovement.objects.filter(
                stock=self.stock,
                movement_type=StockMovement.MOVEMENT_OUT,
            ).count(),
            1,
        )

    def test_repeated_success_does_not_deduct_stock_twice(self):
        PaymentService.mark_payment_success(payment=self.payment)
        PaymentService.mark_payment_success(payment=self.payment)

        self.stock.refresh_from_db()

        self.assertEqual(self.stock.quantity, 8)
        self.assertEqual(self.stock.reserved_quantity, 0)
        self.assertEqual(
            StockMovement.objects.filter(
                stock=self.stock,
                movement_type=StockMovement.MOVEMENT_OUT,
            ).count(),
            1,
        )

    def test_failed_payment_releases_reservation(self):
        PaymentService.mark_payment_failed(
            payment=self.payment,
            response_message="Paiement de test échoué",
        )

        self.stock.refresh_from_db()
        self.order.refresh_from_db()
        self.payment.refresh_from_db()
        self.transaction.refresh_from_db()

        self.assertEqual(self.stock.quantity, 10)
        self.assertEqual(self.stock.reserved_quantity, 0)
        self.assertEqual(self.order.status, Order.Status.CANCELLED)
        self.assertEqual(self.payment.status, Payment.Status.FAILED)
        self.assertEqual(
            self.transaction.status,
            Transaction.Status.FAILED,
        )

    def test_cancelled_payment_releases_reservation(self):
        PaymentService.mark_payment_cancelled(
            payment=self.payment,
            response_message="Paiement de test annulé",
        )

        self.stock.refresh_from_db()
        self.order.refresh_from_db()
        self.payment.refresh_from_db()
        self.transaction.refresh_from_db()

        self.assertEqual(self.stock.quantity, 10)
        self.assertEqual(self.stock.reserved_quantity, 0)
        self.assertEqual(self.order.status, Order.Status.CANCELLED)
        self.assertEqual(self.payment.status, Payment.Status.CANCELLED)
        self.assertEqual(
            self.transaction.status,
            Transaction.Status.CANCELLED,
        )




    def test_failed_payment_does_not_change_confirmed_order(self):
        self.order.status = Order.Status.CONFIRMED
        self.order.save(update_fields=["status"])

        self.payment.status = Payment.Status.PROCESSING
        self.payment.save(update_fields=["status"])

        self.stock.quantity = 8
        self.stock.reserved_quantity = 0
        self.stock.save()

        with self.assertRaises(ValueError):
            PaymentService.mark_payment_failed(
                payment=self.payment,
                response_message="Retour tardif de test",
            )

        self.order.refresh_from_db()
        self.payment.refresh_from_db()
        self.stock.refresh_from_db()
        self.transaction.refresh_from_db()

        self.assertEqual(self.order.status, Order.Status.CONFIRMED)
        self.assertEqual(self.payment.status, Payment.Status.PROCESSING)
        self.assertEqual(self.stock.quantity, 8)
        self.assertEqual(self.stock.reserved_quantity, 0)
        self.assertEqual(self.transaction.status, Transaction.Status.PENDING)

    def test_cancelled_payment_does_not_change_confirmed_order(self):
        self.order.status = Order.Status.CONFIRMED
        self.order.save(update_fields=["status"])

        self.payment.status = Payment.Status.PROCESSING
        self.payment.save(update_fields=["status"])

        self.stock.quantity = 8
        self.stock.reserved_quantity = 0
        self.stock.save()

        with self.assertRaises(ValueError):
            PaymentService.mark_payment_cancelled(
                payment=self.payment,
                response_message="Annulation tardive de test",
            )

        self.order.refresh_from_db()
        self.payment.refresh_from_db()
        self.stock.refresh_from_db()
        self.transaction.refresh_from_db()

        self.assertEqual(self.order.status, Order.Status.CONFIRMED)
        self.assertEqual(self.payment.status, Payment.Status.PROCESSING)
        self.assertEqual(self.stock.quantity, 8)
        self.assertEqual(self.stock.reserved_quantity, 0)
        self.assertEqual(self.transaction.status, Transaction.Status.PENDING)


@override_settings(PAYDUNYA_MASTER_KEY="cle_test_bombaa_123")
class PayDunyaIPNTests(APITestCase):

    URL = "/api/payments/webhooks/paydunya/"
    MASTER_KEY = "cle_test_bombaa_123"

    def setUp(self):
        from decimal import Decimal

        from apps.accounts.models import User
        from apps.catalog.models import Product, ProductVariant
        from apps.stocks.models import Stock
        from apps.orders.models import Order, OrderItem
        from apps.payments.models import PaymentMethod, Payment, Transaction

        self.user = User.objects.create_user(
            email="ipn-test@example.com",
            password="TestPassword123!",
            first_name="Test",
            last_name="IPN",
            phone="+22890000002",
        )

        self.product = Product.objects.create(
            name="Produit IPN",
            slug="produit-ipn-test",
            base_price=Decimal("8500.00"),
        )

        self.variant = ProductVariant.objects.create(
            product=self.product,
            sku="IPN-TEST-001",
            price=Decimal("8500.00"),
        )

        self.stock = Stock.objects.create(
            variant=self.variant,
            quantity=10,
            reserved_quantity=2,
            minimum_quantity=1,
        )

        self.order = Order.objects.create(
            user=self.user,
            reference="CMD-IPN-TEST-001",
            status=Order.Status.PENDING,
            subtotal=Decimal("17000.00"),
            shipping_cost=Decimal("1000.00"),
            discount_amount=Decimal("0.00"),
            total_amount=Decimal("18000.00"),
            currency="XOF",
        )

        OrderItem.objects.create(
            order=self.order,
            variant=self.variant,
            product_name=self.product.name,
            variant_description="Version test",
            sku=self.variant.sku,
            quantity=2,
            unit_price=Decimal("8500.00"),
            subtotal=Decimal("17000.00"),
        )

        method = PaymentMethod.objects.create(
            name="Mobile Money IPN",
            code="IPN_TEST",
            is_active=True,
        )

        self.payment = Payment.objects.create(
            order=self.order,
            payment_method=method,
            reference="PAY-IPN-TEST-001",
            amount=Decimal("18000.00"),
            currency="XOF",
            status=Payment.Status.PENDING,
        )

        self.transaction = Transaction.objects.create(
            payment=self.payment,
            reference="TXN-IPN-TEST-001",
            amount=Decimal("18000.00"),
            currency="XOF",
            status=Transaction.Status.PENDING,
        )

    def make_payload(self, payment_status="completed", amount="18000.00"):
        return {
            "hash": hashlib.sha512(
                self.MASTER_KEY.encode("utf-8")
            ).hexdigest(),
            "status": payment_status,
            "custom_data": {
                "payment_reference": self.payment.reference,
            },
            "invoice": {
                "total_amount": amount,
                "token": "TOKEN-FAKE-IPN-001",
            },
            "response_text": "Réponse de test",
        }

    def send_ipn(self, payload):
        return self.client.post(
            self.URL,
            {"data": payload},
            format="json",
        )

    def test_completed_ipn_confirms_payment_and_updates_stock(self):
        response = self.send_ipn(self.make_payload())

        self.assertEqual(response.status_code, 200)

        self.payment.refresh_from_db()
        self.order.refresh_from_db()
        self.stock.refresh_from_db()
        self.transaction.refresh_from_db()

        self.assertEqual(self.payment.status, Payment.Status.SUCCESS)
        self.assertEqual(self.order.status, Order.Status.CONFIRMED)
        self.assertEqual(self.stock.quantity, 8)
        self.assertEqual(self.stock.reserved_quantity, 0)
        self.assertEqual(self.transaction.status, Transaction.Status.SUCCESS)

    def test_invalid_signature_is_rejected(self):
        payload = self.make_payload()
        payload["hash"] = "signature_invalide"

        response = self.send_ipn(payload)

        self.assertEqual(response.status_code, 403)

        self.payment.refresh_from_db()
        self.stock.refresh_from_db()

        self.assertEqual(self.payment.status, Payment.Status.PENDING)
        self.assertEqual(self.stock.quantity, 10)
        self.assertEqual(self.stock.reserved_quantity, 2)

    def test_incorrect_amount_is_rejected(self):
        response = self.send_ipn(
            self.make_payload(amount="100.00")
        )

        self.assertEqual(response.status_code, 400)

        self.payment.refresh_from_db()
        self.stock.refresh_from_db()

        self.assertEqual(self.payment.status, Payment.Status.PENDING)
        self.assertEqual(self.stock.quantity, 10)
        self.assertEqual(self.stock.reserved_quantity, 2)

    def test_missing_amount_is_rejected(self):
        payload = self.make_payload()
        payload["invoice"].pop("total_amount")

        response = self.send_ipn(payload)

        self.assertEqual(response.status_code, 400)

        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, Payment.Status.PENDING)

    def test_cancelled_ipn_cancels_payment_and_releases_stock(self):
        response = self.send_ipn(
            self.make_payload(payment_status="cancelled")
        )

        self.assertEqual(response.status_code, 200)

        self.payment.refresh_from_db()
        self.order.refresh_from_db()
        self.stock.refresh_from_db()
        self.transaction.refresh_from_db()

        self.assertEqual(self.payment.status, Payment.Status.CANCELLED)
        self.assertEqual(self.order.status, Order.Status.CANCELLED)
        self.assertEqual(self.stock.quantity, 10)
        self.assertEqual(self.stock.reserved_quantity, 0)
        self.assertEqual(self.transaction.status, Transaction.Status.CANCELLED)

    def test_repeated_completed_ipn_does_not_deduct_stock_twice(self):
        first_response = self.send_ipn(self.make_payload())
        second_response = self.send_ipn(self.make_payload())

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 200)

        self.stock.refresh_from_db()

        self.assertEqual(self.stock.quantity, 8)
        self.assertEqual(self.stock.reserved_quantity, 0)



    def test_failed_ipn_after_success_does_not_modify_payment_or_stock(self):
        # Confirmer le paiement.
        response = self.send_ipn(
            self.make_payload(payment_status="completed")
        )
        self.assertEqual(response.status_code, 200)

        self.payment.refresh_from_db()
        self.order.refresh_from_db()
        self.stock.refresh_from_db()
        self.transaction.refresh_from_db()

        previous_reference = self.transaction.external_reference
        previous_message = self.transaction.response_message
        previous_status = self.transaction.status

        # Envoyer ensuite une notification d'échec contradictoire.
        payload = self.make_payload(payment_status="failed")
        payload["response_text"] = "Échec tardif simulé"

        response = self.send_ipn(payload)

        # La vue ne doit pas provoquer une erreur serveur.
        self.assertNotEqual(response.status_code, 500)

        self.payment.refresh_from_db()
        self.order.refresh_from_db()
        self.stock.refresh_from_db()
        self.transaction.refresh_from_db()

        # Le paiement et la commande doivent rester confirmés.
        self.assertEqual(self.payment.status, Payment.Status.SUCCESS)
        self.assertEqual(self.order.status, Order.Status.CONFIRMED)

        # Le stock ne doit pas être modifié une seconde fois.
        self.assertEqual(self.stock.quantity, 8)
        self.assertEqual(self.stock.reserved_quantity, 0)

        # L'historique de transaction doit rester intact.
        self.assertEqual(self.transaction.status, previous_status)
        self.assertEqual(
            self.transaction.external_reference,
            previous_reference,
        )
        self.assertEqual(
            self.transaction.response_message,
            previous_message,
        )




class PaymentMethodPermissionTests(APITestCase):

    URL = "/api/payment-methods/"

    def setUp(self):
        from apps.accounts.models import Permission, Role

        self.client_user = User.objects.create_user(
            email="method-client@example.com",
            password="TestPassword123!",
            first_name="Client",
            last_name="Method",
        )

        self.admin_user = User.objects.create_user(
            email="method-admin@example.com",
            password="TestPassword123!",
            first_name="Admin",
            last_name="Method",
        )

        role = Role.objects.create(
            name="TEST_PAYMENTS_ADMIN",
            description="Rôle de test pour les moyens de paiement",
        )

        permission = Permission.objects.create(
            name="payments.update",
            description="Modifier les paiements",
        )

        role.permissions.add(permission)
        self.admin_user.roles.add(role)

        self.active_method = PaymentMethod.objects.create(
            name="Moyen actif",
            code="TEST_ACTIVE",
            is_active=True,
        )

        self.inactive_method = PaymentMethod.objects.create(
            name="Moyen inactif",
            code="TEST_INACTIVE",
            is_active=False,
        )

    def test_client_only_sees_active_methods(self):
        self.client.force_authenticate(self.client_user)

        response = self.client.get(self.URL)

        self.assertEqual(response.status_code, 200)

        codes = [
            method["code"]
            for method in response.data["results"]
        ]

        self.assertIn(self.active_method.code, codes)
        self.assertNotIn(self.inactive_method.code, codes)

    def test_admin_sees_active_and_inactive_methods(self):
        self.client.force_authenticate(self.admin_user)

        response = self.client.get(self.URL)

        self.assertEqual(response.status_code, 200)

        codes = [
            method["code"]
            for method in response.data["results"]
        ]

        self.assertIn(self.active_method.code, codes)
        self.assertIn(self.inactive_method.code, codes)

    def test_client_cannot_create_payment_method(self):
        self.client.force_authenticate(self.client_user)

        response = self.client.post(
            self.URL,
            {
                "name": "Moyen pirate",
                "code": "PIRATE",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            PaymentMethod.objects.filter(code="PIRATE").exists()
        )

    def test_admin_can_create_payment_method(self):
        self.client.force_authenticate(self.admin_user)

        response = self.client.post(
            self.URL,
            {
                "name": "Nouveau moyen",
                "code": "NEW_METHOD",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            PaymentMethod.objects.filter(
                code="NEW_METHOD"
            ).exists()
        )

    def test_anonymous_cannot_list_payment_methods(self):
        response = self.client.get(self.URL)

        self.assertIn(response.status_code, [401, 403])


class PaymentCreationRulesTests(TestCase):

    def setUp(self):
        from apps.accounts.models import User
        from apps.catalog.models import Product, ProductVariant
        from apps.stocks.models import Stock
        from apps.orders.models import Order

        self.user = User.objects.create_user(
            email="payment-rules@example.com",
            password="TestPassword123!",
            first_name="Payment",
            last_name="Rules",
            phone="+22890000021",
        )

        self.product = Product.objects.create(
            name="Produit règles",
            slug="produit-regles",
            base_price=Decimal("5000.00"),
        )

        self.variant = ProductVariant.objects.create(
            product=self.product,
            sku="RULES-001",
            price=Decimal("5000.00"),
        )

        Stock.objects.create(
            variant=self.variant,
            quantity=10,
            reserved_quantity=0,
        )

        self.method = PaymentMethod.objects.create(
            name="Mobile Money règles",
            code="RULES_MOBILE_MONEY",
            is_active=True,
        )

    def create_order(self, status=Order.Status.PENDING):
        from apps.orders.models import Order, OrderItem

        order = Order.objects.create(
            user=self.user,
            reference=f"CMD-RULES-{status}",
            status=status,
            subtotal=Decimal("10000.00"),
            shipping_cost=Decimal("0.00"),
            discount_amount=Decimal("0.00"),
            total_amount=Decimal("10000.00"),
            currency="XOF",
        )

        OrderItem.objects.create(
            order=order,
            variant=self.variant,
            product_name=self.product.name,
            variant_description=self.variant.sku,
            sku=self.variant.sku,
            quantity=2,
            unit_price=self.variant.price,
            subtotal=Decimal("10000.00"),
        )

        return order

    def test_payment_rejected_on_confirmed_order(self):
        order = self.create_order(
            status=Order.Status.CONFIRMED,
        )

        with self.assertRaises(ValueError):
            PaymentService.create_payment(
                order=order,
                payment_method=self.method,
            )

        self.assertFalse(
            Payment.objects.filter(order=order).exists()
        )

    def test_payment_rejected_when_order_already_successful(self):
        order = self.create_order()

        Payment.objects.create(
            order=order,
            payment_method=self.method,
            reference="PAY-ALREADY-SUCCESS",
            amount=order.total_amount,
            currency="XOF",
            status=Payment.Status.SUCCESS,
        )

        with self.assertRaises(ValueError):
            PaymentService.create_payment(
                order=order,
                payment_method=self.method,
            )

    def test_payment_allowed_on_pending_order(self):
        order = self.create_order()

        payment = PaymentService.create_payment(
            order=order,
            payment_method=self.method,
        )

        self.assertEqual(payment.status, Payment.Status.PENDING)
        self.assertEqual(payment.amount, order.total_amount)
        self.assertEqual(
            payment.transactions.count(),
            1,
        )


class PaymentEndpointPermissionsTests(APITestCase):

    def test_payment_creation_requires_payment_create_permission(self):
        user = User.objects.create_user(
            email="payment-no-role@example.com",
            password="TestPassword123!",
            first_name="Sans",
            last_name="Permission",
            phone="+22890000022",
        )

        self.client.force_authenticate(user)

        response = self.client.post(
            "/api/payments/create/",
            {},
            format="json",
        )

        self.assertEqual(response.status_code, 403)


class PaymentCountryMethodTests(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            email="payment-country@example.com",
            password="TestPassword123!",
            first_name="Payment",
            last_name="Country",
            phone="+22890000033",
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

        self.france = Country.objects.create(
            name="France",
            code="FR",
            phone_code="+33",
            currency=self.xof,
        )

        self.mobile = PaymentMethod.objects.create(
            name="Mobile Money pays",
            code="COUNTRY_MOBILE",
            is_active=True,
        )

        self.card = PaymentMethod.objects.create(
            name="Carte pays",
            code="COUNTRY_CARD",
            is_active=True,
        )

        self.global_method = PaymentMethod.objects.create(
            name="Espèces pays",
            code="COUNTRY_CASH",
            is_active=True,
        )

        self.togo.payment_methods.add(self.mobile)
        self.france.payment_methods.add(self.card)

        self.order = Order.objects.create(
            user=self.user,
            reference="CMD-PAYMENT-COUNTRY",
            status=Order.Status.PENDING,
            subtotal=Decimal("10000.00"),
            shipping_cost=Decimal("0.00"),
            discount_amount=Decimal("0.00"),
            total_amount=Decimal("10000.00"),
            currency="XOF",
        )

        OrderAddress.objects.create(
            order=self.order,
            recipient_name="Payment Country",
            phone="+22890000033",
            address_line1="1 rue du Test",
            city="Lomé",
            country_name="Togo",
            country_code="TG",
        )

    def test_payment_method_list_filters_by_country(self):
        self.client.force_authenticate(self.user)

        response = self.client.get(
            "/api/payment-methods/?country=TG"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            {
                method["code"]
                for method in response.data["results"]
            },
            {"COUNTRY_MOBILE", "COUNTRY_CASH"},
        )

        response = self.client.get(
            "/api/payment-methods/?country=FR"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            {
                method["code"]
                for method in response.data["results"]
            },
            {"COUNTRY_CARD", "COUNTRY_CASH"},
        )

    def test_payment_rejects_method_restricted_to_another_country(self):
        with self.assertRaisesRegex(ValueError, "Togo"):
            PaymentService.create_payment(
                order=self.order,
                payment_method=self.card,
            )

        self.assertFalse(
            Payment.objects.filter(order=self.order).exists()
        )

    def test_payment_accepts_method_assigned_to_order_country(self):
        payment = PaymentService.create_payment(
            order=self.order,
            payment_method=self.mobile,
        )

        self.assertEqual(payment.payment_method, self.mobile)
        self.assertEqual(payment.status, Payment.Status.PENDING)

    def test_payment_accepts_global_method(self):
        payment = PaymentService.create_payment(
            order=self.order,
            payment_method=self.global_method,
        )

        self.assertEqual(
            payment.payment_method,
            self.global_method,
        )
