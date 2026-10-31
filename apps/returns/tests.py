from decimal import Decimal
from uuid import uuid4

from django.utils import timezone

from rest_framework.test import APITestCase

from apps.accounts.models import Permission, Role, User
from apps.audit.models import AuditLog
from apps.catalog.models import Brand, Product, ProductVariant
from apps.notifications.models import Notification
from apps.orders.models import Order, OrderItem
from apps.payments.models import Payment, PaymentMethod
from apps.stocks.models import Stock, StockMovement

from .models import Refund, ReturnItem, ReturnRequest
from .services import RefundService, ReturnService


PERMISSION_NAMES = [
    "returns.view",
    "returns.create",
    "returns.update",
    "refunds.view",
    "refunds.create",
    "refunds.update",
]


class ReturnTestBase(APITestCase):
    def setUp(self):
        self.permissions = {
            name: Permission.objects.create(name=name)
            for name in PERMISSION_NAMES
        }

        self.client_role = Role.objects.create(
            name="RETURN_CLIENT",
            description="Client de test",
        )
        self.client_role.permissions.set([
            self.permissions["returns.view"],
            self.permissions["returns.create"],
            self.permissions["refunds.view"],
        ])

        self.agent_role = Role.objects.create(
            name="RETURN_AGENT",
            description="Agent de test",
        )
        self.agent_role.permissions.set(
            self.permissions.values()
        )

        self.client_user = self.create_user(
            "return-client@example.com",
            self.client_role,
        )
        self.other_client = self.create_user(
            "return-other@example.com",
            self.client_role,
        )
        self.agent = self.create_user(
            "return-agent@example.com",
            self.agent_role,
        )
        self.finance = self.create_user(
            "return-finance@example.com",
            self.agent_role,
        )

        self.brand = Brand.objects.create(
            name="Marque retour",
        )
        self.product = Product.objects.create(
            brand=self.brand,
            name="Produit retour",
            slug="produit-retour",
            base_price=Decimal("10000.00"),
            weight_grams=100,
        )
        self.variant = ProductVariant.objects.create(
            product=self.product,
            sku="RETURN-001",
            price=Decimal("10000.00"),
        )
        self.stock = Stock.objects.create(
            variant=self.variant,
            quantity=10,
            reserved_quantity=0,
            minimum_quantity=1,
        )

        self.order, self.item = self.create_order(
            user=self.client_user,
            reference="RET-ORDER-0001",
        )
        self.other_order, self.other_item = self.create_order(
            user=self.other_client,
            reference="RET-ORDER-0002",
        )
        self.payment_method = PaymentMethod.objects.create(
            name="Mobile Money",
            code="MOMO-RETURN",
        )
        self.payment = Payment.objects.create(
            order=self.order,
            payment_method=self.payment_method,
            reference="PAY-RETURN-0001",
            amount=self.order.total_amount,
            currency="XOF",
            status=Payment.Status.SUCCESS,
            paid_at=timezone.now(),
        )

    def create_user(self, email, role):
        user = User.objects.create_user(
            email=email,
            password="TestPassword123!",
            first_name="Test",
            last_name="Retour",
            phone=f"+228{abs(hash(email)) % 100000000:08d}",
        )
        user.roles.add(role)
        return user

    def create_order(
        self,
        *,
        user,
        reference=None,
        status=Order.Status.DELIVERED,
        quantity=2,
        unit_price=Decimal("10000.00"),
        discount=Decimal("0.00"),
    ):
        subtotal = unit_price * quantity
        total_amount = subtotal - discount

        order = Order.objects.create(
            user=user,
            reference=(
                reference
                or f"RET-ORD-{uuid4().hex[:8].upper()}"
            ),
            status=status,
            subtotal=subtotal,
            total_amount=total_amount,
            currency="XOF",
        )

        item = OrderItem.objects.create(
            order=order,
            variant=self.variant,
            product_name=self.product.name,
            sku=self.variant.sku,
            quantity=quantity,
            unit_price=unit_price,
            subtotal=subtotal,
            discount_amount=discount,
        )

        return order, item

    def create_payment(self, order, *, amount=None):
        return Payment.objects.create(
            order=order,
            payment_method=self.payment_method,
            reference=f"PAY-{uuid4().hex[:8].upper()}",
            amount=amount or order.total_amount,
            currency=order.currency,
            status=Payment.Status.SUCCESS,
            paid_at=timezone.now(),
        )

    def create_return(
        self,
        *,
        order=None,
        item=None,
        quantity=1,
        user=None,
        reason="Produit non conforme.",
    ):
        return ReturnService.create_return(
            order=order or self.order,
            items=[
                {
                    "order_item": item or self.item,
                    "quantity": quantity,
                }
            ],
            reason=reason,
            actor=user or self.client_user,
        )

    def create_received_return(
        self,
        *,
        order=None,
        item=None,
        quantity=1,
    ):
        return_request = self.create_return(
            order=order,
            item=item,
            quantity=quantity,
        )
        return_request = ReturnService.approve(
            return_request=return_request,
            actor=self.agent,
        )
        return ReturnService.receive(
            return_request=return_request,
            actor=self.agent,
        )

    def create_refund(
        self,
        *,
        order=None,
        return_request=None,
        amount=None,
        payment=None,
        actor=None,
    ):
        return RefundService.create_refund(
            order=order or self.order,
            actor=actor or self.agent,
            reason="Remboursement de test.",
            amount=amount,
            payment=payment,
            return_request=return_request,
        )


class ReturnCreationTests(ReturnTestBase):
    def test_client_can_create_return_for_delivered_order(self):
        self.client.force_authenticate(self.client_user)

        response = self.client.post(
            "/api/returns/",
            {
                "order": self.order.id,
                "reason": "Le produit ne correspond pas.",
                "total_amount": "1.00",
                "items": [
                    {
                        "order_item": self.item.id,
                        "quantity": 1,
                        "unit_price": "1.00",
                        "subtotal": "1.00",
                    }
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], "REQUESTED")
        self.assertEqual(
            Decimal(response.data["total_amount"]),
            Decimal("10000.00"),
        )
        self.assertEqual(response.data["currency"], "XOF")
        self.assertEqual(len(response.data["items"]), 1)
        self.assertEqual(
            Decimal(response.data["items"][0]["subtotal"]),
            Decimal("10000.00"),
        )
        self.assertTrue(
            response.data["reference"].startswith("RET-")
        )

        return_request = ReturnRequest.objects.get(
            pk=response.data["id"]
        )
        self.assertEqual(
            return_request.order,
            self.order,
        )
        self.assertEqual(return_request.items.count(), 1)
        self.assertTrue(
            AuditLog.objects.filter(
                action=AuditLog.Action.CREATE,
                target_type="returns.returnrequest",
                target_id=str(return_request.id),
            ).exists()
        )

    def test_return_requires_delivered_order(self):
        order, item = self.create_order(
            user=self.client_user,
            status=Order.Status.PROCESSING,
        )
        self.client.force_authenticate(self.client_user)

        response = self.client.post(
            "/api/returns/",
            {
                "order": order.id,
                "reason": "Trop tôt.",
                "items": [
                    {
                        "order_item": item.id,
                        "quantity": 1,
                    }
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("order", response.data)

    def test_return_rejects_another_users_order(self):
        self.client.force_authenticate(self.client_user)

        response = self.client.post(
            "/api/returns/",
            {
                "order": self.other_order.id,
                "reason": "Piratage.",
                "items": [
                    {
                        "order_item": self.other_item.id,
                        "quantity": 1,
                    }
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("order", response.data)

    def test_return_requires_items(self):
        self.client.force_authenticate(self.client_user)

        response = self.client.post(
            "/api/returns/",
            {
                "order": self.order.id,
                "reason": "Aucun article.",
                "items": [],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("items", response.data)

    def test_return_item_must_belong_to_order(self):
        self.client.force_authenticate(self.client_user)

        response = self.client.post(
            "/api/returns/",
            {
                "order": self.order.id,
                "reason": "Mauvais article.",
                "items": [
                    {
                        "order_item": self.other_item.id,
                        "quantity": 1,
                    }
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("items", response.data)

    def test_return_quantity_cannot_exceed_ordered(self):
        self.client.force_authenticate(self.client_user)

        response = self.client.post(
            "/api/returns/",
            {
                "order": self.order.id,
                "reason": "Trop de quantité.",
                "items": [
                    {
                        "order_item": self.item.id,
                        "quantity": 3,
                    }
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("items", response.data)

    def test_quantity_available_decreases_after_return(self):
        self.create_return(quantity=2)
        self.client.force_authenticate(self.client_user)

        response = self.client.post(
            "/api/returns/",
            {
                "order": self.order.id,
                "reason": "Deuxième retour.",
                "items": [
                    {
                        "order_item": self.item.id,
                        "quantity": 1,
                    }
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("items", response.data)

    def test_duplicate_items_are_rejected(self):
        self.client.force_authenticate(self.client_user)

        response = self.client.post(
            "/api/returns/",
            {
                "order": self.order.id,
                "reason": "Doublon.",
                "items": [
                    {
                        "order_item": self.item.id,
                        "quantity": 1,
                    },
                    {
                        "order_item": self.item.id,
                        "quantity": 1,
                    },
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("items", response.data)

    def test_return_amount_accounts_for_discount(self):
        order, item = self.create_order(
            user=self.client_user,
            quantity=2,
            unit_price=Decimal("10000.00"),
            discount=Decimal("2000.00"),
        )
        self.client.force_authenticate(self.client_user)

        response = self.client.post(
            "/api/returns/",
            {
                "order": order.id,
                "reason": "Article avec remise.",
                "items": [
                    {
                        "order_item": item.id,
                        "quantity": 1,
                    }
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            Decimal(response.data["total_amount"]),
            Decimal("9000.00"),
        )
        self.assertEqual(
            Decimal(response.data["items"][0]["subtotal"]),
            Decimal("9000.00"),
        )

    def test_anonymous_cannot_create_return(self):
        response = self.client.post(
            "/api/returns/",
            {
                "order": self.order.id,
                "reason": "Anonyme.",
                "items": [
                    {
                        "order_item": self.item.id,
                        "quantity": 1,
                    }
                ],
            },
            format="json",
        )

        self.assertIn(response.status_code, (401, 403))
        self.assertEqual(ReturnRequest.objects.count(), 0)

    def test_agent_can_create_return_for_client(self):
        self.client.force_authenticate(self.agent)

        response = self.client.post(
            "/api/returns/",
            {
                "order": self.order.id,
                "reason": "Créé par le service client.",
                "items": [
                    {
                        "order_item": self.item.id,
                        "quantity": 1,
                    }
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            ReturnRequest.objects.get(
                pk=response.data["id"]
            ).order,
            self.order,
        )


class ReturnVisibilityTests(ReturnTestBase):
    def setUp(self):
        super().setUp()
        self.client_return = self.create_return(
            order=self.order,
            item=self.item,
        )
        self.other_return = self.create_return(
            order=self.other_order,
            item=self.other_item,
            user=self.other_client,
        )

    def test_client_only_sees_own_returns(self):
        self.client.force_authenticate(self.client_user)

        response = self.client.get("/api/returns/")

        self.assertEqual(response.status_code, 200)
        identifiers = [
            row["id"] for row in response.data["results"]
        ]
        self.assertIn(self.client_return.id, identifiers)
        self.assertNotIn(self.other_return.id, identifiers)

    def test_agent_sees_all_returns(self):
        self.client.force_authenticate(self.agent)

        response = self.client.get("/api/returns/")

        self.assertEqual(response.status_code, 200)
        identifiers = {
            row["id"] for row in response.data["results"]
        }
        self.assertEqual(
            identifiers,
            {self.client_return.id, self.other_return.id},
        )

    def test_client_cannot_retrieve_another_return(self):
        self.client.force_authenticate(self.client_user)

        response = self.client.get(
            f"/api/returns/{self.other_return.id}/"
        )

        self.assertEqual(response.status_code, 404)

    def test_return_filters(self):
        self.client.force_authenticate(self.agent)

        response = self.client.get(
            f"/api/returns/?order={self.order.id}"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(
            response.data["results"][0]["id"],
            self.client_return.id,
        )

        response = self.client.get(
            "/api/returns/?status=REQUESTED"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 2)

    def test_return_eligibility(self):
        self.client.force_authenticate(self.client_user)

        response = self.client.get(
            f"/api/returns/eligibility/?order={self.order.id}"
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["can_return"])
        self.assertEqual(len(response.data["items"]), 1)
        self.assertEqual(
            response.data["items"][0]["available_quantity"],
            1,
        )

    def test_eligibility_requires_order_parameter(self):
        self.client.force_authenticate(self.client_user)

        response = self.client.get("/api/returns/eligibility/")

        self.assertEqual(response.status_code, 400)

    def test_eligibility_hides_other_orders_from_client(self):
        self.client.force_authenticate(self.client_user)

        response = self.client.get(
            "/api/returns/eligibility/"
            f"?order={self.other_order.id}"
        )

        self.assertEqual(response.status_code, 404)

    def test_eligibility_for_not_delivered_order(self):
        order, _item = self.create_order(
            user=self.client_user,
            status=Order.Status.PENDING,
        )
        self.client.force_authenticate(self.client_user)

        response = self.client.get(
            f"/api/returns/eligibility/?order={order.id}"
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["can_return"])
        self.assertIn("reason", response.data)


class ReturnWorkflowTests(ReturnTestBase):
    def setUp(self):
        super().setUp()
        self.return_request = self.create_return()

    def test_client_cannot_approve_reject_or_receive(self):
        self.client.force_authenticate(self.client_user)

        for action_name in ("approve", "reject", "receive"):
            response = self.client.post(
                f"/api/returns/{self.return_request.id}/"
                f"{action_name}/",
                {},
                format="json",
            )
            self.assertEqual(response.status_code, 403)

    def test_agent_can_approve_return(self):
        self.client.force_authenticate(self.agent)

        response = self.client.post(
            f"/api/returns/{self.return_request.id}/approve/"
        )

        self.assertEqual(response.status_code, 200)
        self.return_request.refresh_from_db()
        self.assertEqual(
            self.return_request.status,
            ReturnRequest.Status.APPROVED,
        )
        self.assertIsNotNone(
            self.return_request.approved_at
        )
        self.assertEqual(
            self.return_request.processed_by,
            self.agent,
        )
        self.assertTrue(
            AuditLog.objects.filter(
                action=AuditLog.Action.STATUS_CHANGE,
                target_id=str(self.return_request.id),
            ).exists()
        )

    def test_agent_can_reject_return(self):
        self.client.force_authenticate(self.agent)

        response = self.client.post(
            f"/api/returns/{self.return_request.id}/reject/",
            {"admin_note": "Produit non éligible."},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.return_request.refresh_from_db()
        self.assertEqual(
            self.return_request.status,
            ReturnRequest.Status.REJECTED,
        )
        self.assertEqual(
            self.return_request.admin_note,
            "Produit non éligible.",
        )
        self.assertIsNotNone(
            self.return_request.rejected_at
        )

    def test_receive_requires_approval(self):
        self.client.force_authenticate(self.agent)

        response = self.client.post(
            f"/api/returns/{self.return_request.id}/receive/"
        )

        self.assertEqual(response.status_code, 400)
        self.return_request.refresh_from_db()
        self.assertEqual(
            self.return_request.status,
            ReturnRequest.Status.REQUESTED,
        )

    def test_receive_restocks_and_updates_order(self):
        ReturnService.approve(
            return_request=self.return_request,
            actor=self.agent,
        )
        initial_stock = self.stock.quantity
        self.client.force_authenticate(self.agent)

        response = self.client.post(
            f"/api/returns/{self.return_request.id}/receive/"
        )

        self.assertEqual(response.status_code, 200)
        self.return_request.refresh_from_db()
        self.order.refresh_from_db()
        self.stock.refresh_from_db()

        self.assertEqual(
            self.return_request.status,
            ReturnRequest.Status.RECEIVED,
        )
        self.assertIsNotNone(
            self.return_request.received_at
        )
        self.assertEqual(
            self.order.status,
            Order.Status.RETURNED,
        )
        self.assertEqual(
            self.stock.quantity,
            initial_stock + 1,
        )
        self.assertTrue(
            StockMovement.objects.filter(
                stock=self.stock,
                movement_type=StockMovement.MOVEMENT_IN,
                quantity=1,
                reason__contains=self.return_request.reference,
            ).exists()
        )

    def test_receive_twice_is_rejected(self):
        self.create_received_return()
        self.client.force_authenticate(self.agent)

        response = self.client.post(
            f"/api/returns/{self.return_request.id}/receive/"
        )

        self.assertEqual(response.status_code, 400)

    def test_client_can_cancel_requested_return(self):
        self.client.force_authenticate(self.client_user)

        response = self.client.post(
            f"/api/returns/{self.return_request.id}/cancel/"
        )

        self.assertEqual(response.status_code, 200)
        self.return_request.refresh_from_db()
        self.assertEqual(
            self.return_request.status,
            ReturnRequest.Status.CANCELLED,
        )
        self.assertIsNotNone(
            self.return_request.cancelled_at
        )

        response = self.client.post(
            "/api/returns/",
            {
                "order": self.order.id,
                "reason": "Nouvelle demande.",
                "items": [
                    {
                        "order_item": self.item.id,
                        "quantity": 1,
                    }
                ],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)

    def test_cannot_cancel_approved_return(self):
        ReturnService.approve(
            return_request=self.return_request,
            actor=self.agent,
        )
        self.client.force_authenticate(self.client_user)

        response = self.client.post(
            f"/api/returns/{self.return_request.id}/cancel/"
        )

        self.assertEqual(response.status_code, 400)

    def test_other_client_cannot_cancel_return(self):
        self.client.force_authenticate(self.other_client)

        response = self.client.post(
            f"/api/returns/{self.return_request.id}/cancel/"
        )

        self.assertEqual(response.status_code, 404)


class RefundTests(ReturnTestBase):
    def setUp(self):
        super().setUp()
        self.return_request = self.create_received_return()

    def test_client_cannot_create_refund(self):
        self.client.force_authenticate(self.client_user)

        response = self.client.post(
            "/api/refunds/",
            {
                "order": self.order.id,
                "reason": "Remboursement pirate.",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(Refund.objects.count(), 0)

    def test_agent_can_create_refund_from_return(self):
        self.client.force_authenticate(self.agent)

        response = self.client.post(
            "/api/refunds/",
            {
                "order": self.order.id,
                "return_request": self.return_request.id,
                "payment": self.payment.id,
                "reason": "Retour réceptionné.",
                "method": Refund.Method.ORIGINAL_PAYMENT,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], "PENDING")
        self.assertEqual(
            Decimal(response.data["amount"]),
            self.return_request.total_amount,
        )
        self.assertEqual(
            response.data["requested_by"],
            self.agent.id,
        )
        self.assertTrue(
            response.data["reference"].startswith("REF-")
        )
        self.assertTrue(
            AuditLog.objects.filter(
                action=AuditLog.Action.CREATE,
                target_type="returns.refund",
            ).exists()
        )

    def test_refund_cannot_exceed_return_amount(self):
        self.client.force_authenticate(self.agent)

        response = self.client.post(
            "/api/refunds/",
            {
                "order": self.order.id,
                "return_request": self.return_request.id,
                "amount": "15000.00",
                "reason": "Trop élevé.",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("amount", response.data)

    def test_refund_requires_received_return(self):
        pending_return = self.create_return(
            order=self.other_order,
            item=self.other_item,
            user=self.other_client,
        )
        self.client.force_authenticate(self.agent)

        response = self.client.post(
            "/api/refunds/",
            {
                "order": self.other_order.id,
                "return_request": pending_return.id,
                "reason": "Retour non reçu.",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("return_request", response.data)

    def test_refund_rejects_mismatched_return(self):
        self.client.force_authenticate(self.agent)

        response = self.client.post(
            "/api/refunds/",
            {
                "order": self.other_order.id,
                "return_request": self.return_request.id,
                "reason": "Mauvais retour.",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("return_request", response.data)

    def test_refund_rejects_mismatched_payment(self):
        other_payment = self.create_payment(self.other_order)
        self.client.force_authenticate(self.agent)

        response = self.client.post(
            "/api/refunds/",
            {
                "order": self.order.id,
                "return_request": self.return_request.id,
                "payment": other_payment.id,
                "reason": "Mauvais paiement.",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("payment", response.data)

    def test_refund_rejects_non_success_payment(self):
        failed_payment = Payment.objects.create(
            order=self.order,
            payment_method=self.payment_method,
            reference="PAY-FAILED-RETURN",
            amount=Decimal("10000.00"),
            currency="XOF",
            status=Payment.Status.FAILED,
        )
        self.client.force_authenticate(self.agent)

        response = self.client.post(
            "/api/refunds/",
            {
                "order": self.order.id,
                "return_request": self.return_request.id,
                "payment": failed_payment.id,
                "reason": "Paiement échoué.",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("payment", response.data)

    def test_standalone_refund_defaults_to_remaining_amount(self):
        order, _item = self.create_order(
            user=self.client_user,
            reference="RET-ORDER-STANDALONE",
            quantity=1,
        )
        self.client.force_authenticate(self.agent)

        response = self.client.post(
            "/api/refunds/",
            {
                "order": order.id,
                "reason": "Geste commercial.",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            Decimal(response.data["amount"]),
            order.total_amount,
        )

    def test_agent_can_approve_refund(self):
        refund = self.create_refund(
            return_request=self.return_request,
            amount=Decimal("10000.00"),
        )
        self.client.force_authenticate(self.agent)

        response = self.client.post(
            f"/api/refunds/{refund.id}/approve/"
        )

        self.assertEqual(response.status_code, 200)
        refund.refresh_from_db()
        self.assertEqual(
            refund.status,
            Refund.Status.APPROVED,
        )
        self.assertIsNotNone(refund.approved_at)
        self.assertEqual(refund.processed_by, self.agent)

    def test_process_full_return_refund(self):
        order, item = self.create_order(
            user=self.client_user,
            reference="RET-ORDER-FULL",
            quantity=1,
        )
        payment = self.create_payment(order)
        self.stock.refresh_from_db()
        stock_before_return = self.stock.quantity
        return_request = self.create_received_return(
            order=order,
            item=item,
            quantity=1,
        )
        self.stock.refresh_from_db()
        self.assertEqual(
            self.stock.quantity,
            stock_before_return + 1,
        )
        initial_stock = self.stock.quantity
        refund = self.create_refund(
            order=order,
            return_request=return_request,
            amount=return_request.total_amount,
            payment=payment,
        )
        self.client.force_authenticate(self.agent)

        response = self.client.post(
            f"/api/refunds/{refund.id}/process/",
            {"external_reference": "MOMO-REFUND-0001"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        refund.refresh_from_db()
        return_request.refresh_from_db()
        order.refresh_from_db()
        payment.refresh_from_db()
        self.stock.refresh_from_db()

        self.assertEqual(
            refund.status,
            Refund.Status.PROCESSED,
        )
        self.assertEqual(
            refund.external_reference,
            "MOMO-REFUND-0001",
        )
        self.assertIsNotNone(refund.processed_at)
        self.assertEqual(
            return_request.status,
            ReturnRequest.Status.REFUNDED,
        )
        self.assertEqual(
            order.status,
            Order.Status.REFUNDED,
        )
        self.assertEqual(
            payment.status,
            Payment.Status.REFUNDED,
        )
        self.assertEqual(
            self.stock.quantity,
            initial_stock,
        )
        self.assertTrue(
            Notification.objects.filter(
                user=self.client_user,
                event=Notification.Event.REFUND,
            ).exists()
        )
        self.assertTrue(
            AuditLog.objects.filter(
                action=AuditLog.Action.STATUS_CHANGE,
                target_type="returns.refund",
                target_id=str(refund.id),
            ).exists()
        )

    def test_partial_refund_keeps_return_received(self):
        order = self.order
        refund = self.create_refund(
            order=order,
            return_request=self.return_request,
            amount=Decimal("5000.00"),
        )
        self.client.force_authenticate(self.agent)

        response = self.client.post(
            f"/api/refunds/{refund.id}/process/"
        )

        self.assertEqual(response.status_code, 200)
        self.return_request.refresh_from_db()
        order.refresh_from_db()
        self.payment.refresh_from_db()

        self.assertEqual(
            self.return_request.status,
            ReturnRequest.Status.RECEIVED,
        )
        self.assertEqual(
            order.status,
            Order.Status.RETURNED,
        )
        self.assertEqual(
            self.payment.status,
            Payment.Status.SUCCESS,
        )

    def test_agent_can_reject_refund(self):
        refund = self.create_refund(
            return_request=self.return_request,
        )
        self.client.force_authenticate(self.agent)

        response = self.client.post(
            f"/api/refunds/{refund.id}/reject/",
            {"notes": "Justificatif manquant."},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        refund.refresh_from_db()
        self.assertEqual(
            refund.status,
            Refund.Status.REJECTED,
        )
        self.assertEqual(
            refund.notes,
            "Justificatif manquant.",
        )
        self.assertIsNotNone(refund.rejected_at)

    def test_client_sees_only_own_refunds(self):
        own_refund = self.create_refund(
            return_request=self.return_request,
        )
        other_return = self.create_received_return(
            order=self.other_order,
            item=self.other_item,
        )
        other_refund = self.create_refund(
            order=self.other_order,
            return_request=other_return,
        )
        self.client.force_authenticate(self.client_user)

        response = self.client.get("/api/refunds/")

        self.assertEqual(response.status_code, 200)
        identifiers = [
            row["id"] for row in response.data["results"]
        ]
        self.assertIn(own_refund.id, identifiers)
        self.assertNotIn(other_refund.id, identifiers)

        response = self.client.get(
            f"/api/refunds/{other_refund.id}/"
        )
        self.assertEqual(response.status_code, 404)

    def test_client_cannot_process_refund(self):
        refund = self.create_refund(
            return_request=self.return_request,
        )
        self.client.force_authenticate(self.client_user)

        response = self.client.post(
            f"/api/refunds/{refund.id}/process/"
        )

        self.assertEqual(response.status_code, 403)

    def test_agent_sees_all_refunds_and_filters(self):
        own_refund = self.create_refund(
            return_request=self.return_request,
        )
        other_return = self.create_received_return(
            order=self.other_order,
            item=self.other_item,
        )
        other_refund = self.create_refund(
            order=self.other_order,
            return_request=other_return,
        )
        self.client.force_authenticate(self.agent)

        response = self.client.get("/api/refunds/")

        self.assertEqual(response.status_code, 200)
        identifiers = {
            row["id"] for row in response.data["results"]
        }
        self.assertEqual(
            identifiers,
            {own_refund.id, other_refund.id},
        )

        response = self.client.get(
            f"/api/refunds/?order={self.order.id}"
        )

        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(
            response.data["results"][0]["id"],
            own_refund.id,
        )


class ReturnModelTests(ReturnTestBase):
    def test_references_have_expected_format(self):
        return_request = self.create_received_return()
        refund = self.create_refund(
            return_request=return_request,
        )

        self.assertRegex(
            return_request.reference,
            r"^RET-[0-9A-F]{8}$",
        )
        self.assertRegex(
            refund.reference,
            r"^REF-[0-9A-F]{8}$",
        )

    def test_string_representations(self):
        return_request = self.create_received_return()
        item = return_request.items.first()
        refund = self.create_refund(
            return_request=return_request,
        )

        self.assertIn(return_request.reference, str(return_request))
        self.assertIn(item.sku, str(item))
        self.assertIn(refund.reference, str(refund))

    def test_order_has_return_and_refund_statuses(self):
        statuses = {
            value
            for value, _label in Order.Status.choices
        }

        self.assertIn(Order.Status.RETURNED, statuses)
        self.assertIn(Order.Status.REFUNDED, statuses)

    def test_return_item_quantity_must_be_positive(self):
        return_request = self.create_return()
        item = return_request.items.first()
        item.quantity = 0

        from django.core.exceptions import ValidationError

        with self.assertRaises(ValidationError):
            item.full_clean()

        self.assertEqual(
            ReturnItem.objects.filter(
                pk=item.pk
            ).count(),
            1,
        )
