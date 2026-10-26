from decimal import Decimal
from uuid import uuid4

from rest_framework.test import APITestCase

from apps.accounts.models import Permission, Role, User
from apps.audit.models import AuditLog
from apps.orders.models import Order

from .models import (
    FaqEntry,
    SupportEvent,
    SupportMessage,
    SupportTicket,
)
from .services import SupportService


PERMISSION_NAMES = [
    "support.view",
    "support.create",
    "support.update",
    "support.manage",
]


class SupportTestBase(APITestCase):
    def setUp(self):
        self.permissions = {
            name: Permission.objects.create(name=name)
            for name in PERMISSION_NAMES
        }

        self.client_role = Role.objects.create(
            name="SUPPORT_CLIENT",
            description="Client de test",
        )
        self.client_role.permissions.set([
            self.permissions["support.view"],
            self.permissions["support.create"],
            self.permissions["support.update"],
        ])

        self.agent_role = Role.objects.create(
            name="SUPPORT_AGENT",
            description="Agent de test",
        )
        self.agent_role.permissions.set(
            self.permissions.values()
        )

        self.client_user = self.create_user(
            "support-client@example.com",
            self.client_role,
        )
        self.other_client = self.create_user(
            "support-other@example.com",
            self.client_role,
        )
        self.agent = self.create_user(
            "support-agent@example.com",
            self.agent_role,
        )
        self.staff_user = self.create_user(
            "support-staff@example.com",
            self.agent_role,
            is_staff=True,
        )

        self.order = self.create_order(
            user=self.client_user,
            reference="SUP-ORDER-0001",
        )
        self.other_order = self.create_order(
            user=self.other_client,
            reference="SUP-ORDER-0002",
        )

    def create_user(self, email, role, is_staff=False):
        user = User.objects.create_user(
            email=email,
            password="TestPassword123!",
            first_name="Test",
            last_name="Support",
            phone=f"+228{abs(hash(email)) % 100000000:08d}",
            is_staff=is_staff,
        )
        user.roles.add(role)
        return user

    def create_order(
        self,
        *,
        user=None,
        reference=None,
        status=Order.Status.CONFIRMED,
    ):
        return Order.objects.create(
            user=user or self.client_user,
            reference=(
                reference
                or f"SUP-ORD-{uuid4().hex[:8].upper()}"
            ),
            status=status,
            subtotal=Decimal("10000.00"),
            total_amount=Decimal("10000.00"),
        )

    def create_ticket(
        self,
        *,
        user=None,
        order=None,
        ticket_type=SupportTicket.Type.QUESTION,
        ticket_status=SupportTicket.Status.OPEN,
        priority=SupportTicket.Priority.NORMAL,
        subject="Demande de test",
        description="Description de la demande.",
        contact_name=None,
        contact_email=None,
        contact_phone="+22890000099",
        assigned_to=None,
    ):
        if user is not None:
            default_name, default_email = (
                SupportService.contact_snapshot(user)
            )
            contact_phone = user.phone
        else:
            default_name = "Visiteur"
            default_email = "visiteur@example.com"

        return SupportTicket.objects.create(
            user=user,
            order=order,
            type=ticket_type,
            status=ticket_status,
            priority=priority,
            subject=subject,
            description=description,
            contact_name=contact_name or default_name,
            contact_email=contact_email or default_email,
            contact_phone=contact_phone,
            assigned_to=assigned_to,
        )

    def add_message(
        self,
        ticket,
        author,
        body="Bonjour, pouvez-vous m'aider ?",
        is_internal=False,
    ):
        return SupportService.add_message(
            ticket=ticket,
            author=author,
            body=body,
            is_internal=is_internal,
        )


class SupportContactTests(SupportTestBase):
    def test_contact_information_is_public(self):
        response = self.client.get("/api/support/contact/")

        self.assertEqual(response.status_code, 200)
        self.assertIn("email", response.data)
        self.assertIn("phone", response.data)
        self.assertIn("hours", response.data)
        self.assertEqual(
            response.data["faq_endpoint"],
            "/api/support/faq/",
        )


class FaqTests(SupportTestBase):
    def setUp(self):
        super().setUp()
        self.active_entry = FaqEntry.objects.create(
            question="Comment commander ?",
            answer="Ajoutez un produit au panier.",
            category="Commandes",
            display_order=1,
        )
        self.inactive_entry = FaqEntry.objects.create(
            question="Ancienne question",
            answer="Ancienne réponse",
            category="Divers",
            display_order=2,
            is_active=False,
        )

    def test_public_list_returns_only_active_entries(self):
        response = self.client.get("/api/support/faq/")

        self.assertEqual(response.status_code, 200)
        identifiers = [item["id"] for item in response.data]

        self.assertIn(self.active_entry.id, identifiers)
        self.assertNotIn(self.inactive_entry.id, identifiers)

    def test_faq_search_and_category_filter(self):
        FaqEntry.objects.create(
            question="Suivi de livraison",
            answer="Consultez votre commande.",
            category="Livraison",
            display_order=3,
        )

        response = self.client.get(
            "/api/support/faq/?category=Livraison"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(
            response.data[0]["category"],
            "Livraison",
        )

        response = self.client.get(
            "/api/support/faq/?search=commander"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(
            response.data[0]["id"],
            self.active_entry.id,
        )

    def test_agent_sees_inactive_entries(self):
        self.client.force_authenticate(self.agent)

        response = self.client.get("/api/support/faq/")

        self.assertEqual(response.status_code, 200)
        identifiers = [item["id"] for item in response.data]

        self.assertIn(self.inactive_entry.id, identifiers)

    def test_agent_can_create_update_and_delete_faq(self):
        self.client.force_authenticate(self.agent)

        response = self.client.post(
            "/api/support/faq/",
            {
                "question": "Puis-je annuler une commande ?",
                "answer": "Oui, tant qu'elle n'est pas expédiée.",
                "category": "Commandes",
                "display_order": 10,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        entry = FaqEntry.objects.get(pk=response.data["id"])
        self.assertTrue(entry.is_active)

        response = self.client.patch(
            f"/api/support/faq/{entry.id}/",
            {
                "answer": "Oui, avant l'expédition.",
                "is_active": False,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        entry.refresh_from_db()
        self.assertFalse(entry.is_active)
        self.assertEqual(
            entry.answer,
            "Oui, avant l'expédition.",
        )

        entry_id = entry.id
        response = self.client.delete(
            f"/api/support/faq/{entry_id}/"
        )
        self.assertEqual(response.status_code, 204)
        self.assertFalse(
            FaqEntry.objects.filter(pk=entry_id).exists()
        )

        self.assertTrue(
            AuditLog.objects.filter(
                action=AuditLog.Action.CREATE,
                target_type="support.faqentry",
            ).exists()
        )
        self.assertTrue(
            AuditLog.objects.filter(
                action=AuditLog.Action.UPDATE,
                target_type="support.faqentry",
            ).exists()
        )
        self.assertTrue(
            AuditLog.objects.filter(
                action=AuditLog.Action.DELETE,
                target_type="support.faqentry",
            ).exists()
        )

    def test_client_cannot_manage_faq(self):
        self.client.force_authenticate(self.client_user)

        response = self.client.post(
            "/api/support/faq/",
            {
                "question": "Question pirate",
                "answer": "Réponse pirate",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            FaqEntry.objects.filter(
                question="Question pirate"
            ).exists()
        )

    def test_faq_requires_question_and_answer(self):
        self.client.force_authenticate(self.agent)

        response = self.client.post(
            "/api/support/faq/",
            {
                "question": "   ",
                "answer": "   ",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("question", response.data)
        self.assertIn("answer", response.data)


class TicketCreationTests(SupportTestBase):
    def test_anonymous_contact_form_creates_ticket(self):
        response = self.client.post(
            "/api/support/tickets/",
            {
                "type": SupportTicket.Type.QUESTION,
                "subject": "Question depuis le site",
                "description": "Bonjour, j'ai une question.",
                "contact_name": "Awa Diallo",
                "contact_email": "awa@example.com",
                "contact_phone": "+221770000000",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertIsNone(response.data["user"])
        self.assertEqual(response.data["status"], "OPEN")
        self.assertEqual(response.data["priority"], "NORMAL")
        self.assertTrue(
            response.data["reference"].startswith("SUP-")
        )

        ticket = SupportTicket.objects.get(
            pk=response.data["id"]
        )
        self.assertIsNone(ticket.user)
        self.assertEqual(ticket.contact_name, "Awa Diallo")
        self.assertEqual(ticket.contact_email, "awa@example.com")
        self.assertTrue(ticket.events.filter(
            action=SupportEvent.Action.CREATED
        ).exists())
        self.assertTrue(
            AuditLog.objects.filter(
                action=AuditLog.Action.CREATE,
                target_type="support.supportticket",
                target_id=str(ticket.id),
            ).exists()
        )

    def test_anonymous_ticket_requires_contact_details(self):
        response = self.client.post(
            "/api/support/tickets/",
            {
                "subject": "Sans coordonnées",
                "description": "Bonjour.",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("contact_name", response.data)
        self.assertIn("contact_email", response.data)

    def test_anonymous_cannot_request_return_or_refund(self):
        for ticket_type in [
            SupportTicket.Type.RETURN,
            SupportTicket.Type.REFUND,
        ]:
            response = self.client.post(
                "/api/support/tickets/",
                {
                    "type": ticket_type,
                    "subject": "Retour",
                    "description": "Je veux un retour.",
                    "contact_name": "Awa",
                    "contact_email": "awa@example.com",
                },
                format="json",
            )

            self.assertEqual(response.status_code, 400)
            self.assertIn("type", response.data)

        self.assertEqual(SupportTicket.objects.count(), 0)

    def test_anonymous_cannot_attach_order(self):
        response = self.client.post(
            "/api/support/tickets/",
            {
                "subject": "Question",
                "description": "Bonjour.",
                "contact_name": "Awa",
                "contact_email": "awa@example.com",
                "order": self.order.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("order", response.data)

    def test_authenticated_client_creates_ticket(self):
        self.client.force_authenticate(self.client_user)

        response = self.client.post(
            "/api/support/tickets/",
            {
                "type": SupportTicket.Type.RETURN,
                "priority": SupportTicket.Priority.URGENT,
                "subject": "Échange de taille",
                "description": "Le produit est trop petit.",
                "order": self.order.id,
                "user": self.other_client.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["user"], self.client_user.id)
        self.assertEqual(response.data["priority"], "NORMAL")
        self.assertEqual(
            response.data["contact_email"],
            self.client_user.email,
        )

        ticket = SupportTicket.objects.get(
            pk=response.data["id"]
        )
        self.assertEqual(ticket.user, self.client_user)
        self.assertEqual(ticket.order, self.order)
        self.assertEqual(ticket.status, SupportTicket.Status.OPEN)

    def test_client_cannot_attach_another_users_order(self):
        self.client.force_authenticate(self.client_user)

        response = self.client.post(
            "/api/support/tickets/",
            {
                "type": SupportTicket.Type.COMPLAINT,
                "subject": "Réclamation",
                "description": "Problème.",
                "order": self.other_order.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("order", response.data)

    def test_ticket_requires_subject_and_description(self):
        self.client.force_authenticate(self.client_user)

        response = self.client.post(
            "/api/support/tickets/",
            {
                "subject": "   ",
                "description": "   ",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("subject", response.data)
        self.assertIn("description", response.data)

    def test_ticket_reference_is_unique(self):
        first = self.create_ticket(user=self.client_user)
        second = self.create_ticket(user=self.client_user)

        self.assertNotEqual(first.reference, second.reference)
        self.assertTrue(
            first.reference.startswith("SUP-")
        )


class TicketVisibilityTests(SupportTestBase):
    def setUp(self):
        super().setUp()
        self.client_ticket = self.create_ticket(
            user=self.client_user,
            order=self.order,
            subject="Ticket du client",
        )
        self.other_ticket = self.create_ticket(
            user=self.other_client,
            order=self.other_order,
            subject="Ticket de l'autre client",
        )

    def test_anonymous_cannot_list_tickets(self):
        response = self.client.get("/api/support/tickets/")

        self.assertIn(response.status_code, (401, 403))

    def test_client_only_sees_own_tickets(self):
        self.client.force_authenticate(self.client_user)

        response = self.client.get("/api/support/tickets/")

        self.assertEqual(response.status_code, 200)
        identifiers = [
            item["id"] for item in response.data["results"]
        ]
        self.assertIn(self.client_ticket.id, identifiers)
        self.assertNotIn(self.other_ticket.id, identifiers)

    def test_client_cannot_retrieve_another_ticket(self):
        self.client.force_authenticate(self.client_user)

        response = self.client.get(
            f"/api/support/tickets/{self.other_ticket.id}/"
        )

        self.assertEqual(response.status_code, 404)

    def test_agent_sees_all_tickets(self):
        self.client.force_authenticate(self.agent)

        response = self.client.get("/api/support/tickets/")

        self.assertEqual(response.status_code, 200)
        identifiers = {
            item["id"] for item in response.data["results"]
        }
        self.assertEqual(
            identifiers,
            {self.client_ticket.id, self.other_ticket.id},
        )

    def test_list_filters(self):
        self.create_ticket(
            user=self.client_user,
            ticket_type=SupportTicket.Type.COMPLAINT,
            priority=SupportTicket.Priority.HIGH,
            subject="Réclamation urgente",
        )
        self.client.force_authenticate(self.agent)

        response = self.client.get(
            "/api/support/tickets/"
            f"?type={SupportTicket.Type.COMPLAINT}"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(
            response.data["results"][0]["type"],
            SupportTicket.Type.COMPLAINT,
        )

        response = self.client.get(
            "/api/support/tickets/?search=urgente"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)

        response = self.client.get(
            f"/api/support/tickets/?order={self.order.id}"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(
            response.data["results"][0]["id"],
            self.client_ticket.id,
        )

    def test_messages_count_excludes_internal_for_client(self):
        self.add_message(
            self.client_ticket,
            self.client_user,
            body="Message public",
        )
        self.add_message(
            self.client_ticket,
            self.agent,
            body="Note interne",
            is_internal=True,
        )

        self.client.force_authenticate(self.client_user)
        response = self.client.get("/api/support/tickets/")

        self.assertEqual(response.status_code, 200)
        item = response.data["results"][0]
        self.assertEqual(item["messages_count"], 1)

        self.client.force_authenticate(self.agent)
        response = self.client.get("/api/support/tickets/")

        item = next(
            row
            for row in response.data["results"]
            if row["id"] == self.client_ticket.id
        )
        self.assertEqual(item["messages_count"], 2)


class TicketManagementTests(SupportTestBase):
    def setUp(self):
        super().setUp()
        self.ticket = self.create_ticket(
            user=self.client_user,
            order=self.order,
        )

    def test_client_cannot_update_ticket(self):
        self.client.force_authenticate(self.client_user)

        response = self.client.patch(
            f"/api/support/tickets/{self.ticket.id}/",
            {"priority": SupportTicket.Priority.URGENT},
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        self.ticket.refresh_from_db()
        self.assertEqual(
            self.ticket.priority,
            SupportTicket.Priority.NORMAL,
        )

    def test_agent_can_update_ticket(self):
        self.client.force_authenticate(self.agent)

        response = self.client.patch(
            f"/api/support/tickets/{self.ticket.id}/",
            {
                "priority": SupportTicket.Priority.HIGH,
                "subject": "Sujet corrigé",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.ticket.refresh_from_db()
        self.assertEqual(
            self.ticket.priority,
            SupportTicket.Priority.HIGH,
        )
        self.assertEqual(self.ticket.subject, "Sujet corrigé")
        self.assertTrue(
            AuditLog.objects.filter(
                action=AuditLog.Action.UPDATE,
                target_type="support.supportticket",
                target_id=str(self.ticket.id),
            ).exists()
        )

    def test_agent_can_assign_ticket(self):
        self.client.force_authenticate(self.agent)

        response = self.client.post(
            f"/api/support/tickets/{self.ticket.id}/assign/",
            {"assigned_to": self.staff_user.id},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.assigned_to, self.staff_user)
        self.assertEqual(
            self.ticket.status,
            SupportTicket.Status.IN_PROGRESS,
        )
        self.assertTrue(self.ticket.events.filter(
            action=SupportEvent.Action.ASSIGNED
        ).exists())
        self.assertTrue(
            AuditLog.objects.filter(
                action=AuditLog.Action.ASSIGN,
                target_id=str(self.ticket.id),
            ).exists()
        )

    def test_assignment_requires_support_agent(self):
        self.client.force_authenticate(self.agent)

        response = self.client.post(
            f"/api/support/tickets/{self.ticket.id}/assign/",
            {"assigned_to": self.client_user.id},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("assigned_to", response.data)

    def test_agent_can_unassign_ticket(self):
        self.ticket.assigned_to = self.agent
        self.ticket.save(update_fields=["assigned_to"])
        self.client.force_authenticate(self.agent)

        response = self.client.post(
            f"/api/support/tickets/{self.ticket.id}/assign/",
            {"assigned_to": None},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.ticket.refresh_from_db()
        self.assertIsNone(self.ticket.assigned_to)

    def test_client_cannot_assign_or_resolve_or_close(self):
        self.client.force_authenticate(self.client_user)

        for action_name in ("assign", "resolve", "close"):
            response = self.client.post(
                f"/api/support/tickets/{self.ticket.id}/"
                f"{action_name}/",
                {},
                format="json",
            )
            self.assertEqual(response.status_code, 403)

    def test_resolve_requires_resolution(self):
        self.client.force_authenticate(self.agent)

        response = self.client.post(
            f"/api/support/tickets/{self.ticket.id}/resolve/",
            {},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("resolution", response.data)
        self.ticket.refresh_from_db()
        self.assertEqual(
            self.ticket.status,
            SupportTicket.Status.OPEN,
        )

    def test_agent_can_resolve_ticket(self):
        self.client.force_authenticate(self.agent)

        response = self.client.post(
            f"/api/support/tickets/{self.ticket.id}/resolve/",
            {"resolution": "Problème résolu par téléphone."},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.ticket.refresh_from_db()
        self.assertEqual(
            self.ticket.status,
            SupportTicket.Status.RESOLVED,
        )
        self.assertEqual(
            self.ticket.resolution,
            "Problème résolu par téléphone.",
        )
        self.assertIsNotNone(self.ticket.resolved_at)
        self.assertTrue(self.ticket.events.filter(
            action=SupportEvent.Action.RESOLVED
        ).exists())
        self.assertTrue(
            AuditLog.objects.filter(
                action=AuditLog.Action.STATUS_CHANGE,
                target_id=str(self.ticket.id),
                changes__status__after="RESOLVED",
            ).exists()
        )

    def test_agent_can_close_ticket(self):
        self.client.force_authenticate(self.agent)

        response = self.client.post(
            f"/api/support/tickets/{self.ticket.id}/close/",
            {"note": "Dossier clos"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.ticket.refresh_from_db()
        self.assertEqual(
            self.ticket.status,
            SupportTicket.Status.CLOSED,
        )
        self.assertIsNotNone(self.ticket.closed_at)
        self.assertTrue(self.ticket.events.filter(
            action=SupportEvent.Action.CLOSED
        ).exists())

    def test_close_is_idempotent(self):
        self.client.force_authenticate(self.agent)

        self.client.post(
            f"/api/support/tickets/{self.ticket.id}/close/"
        )
        self.ticket.refresh_from_db()
        first_closed_at = self.ticket.closed_at

        response = self.client.post(
            f"/api/support/tickets/{self.ticket.id}/close/"
        )

        self.assertEqual(response.status_code, 200)
        self.ticket.refresh_from_db()
        self.assertEqual(
            self.ticket.closed_at,
            first_closed_at,
        )

    def test_client_can_reopen_own_resolved_ticket(self):
        SupportService.resolve(
            ticket=self.ticket,
            actor=self.agent,
            resolution="Résolu.",
        )
        self.client.force_authenticate(self.client_user)

        response = self.client.post(
            f"/api/support/tickets/{self.ticket.id}/reopen/",
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.ticket.refresh_from_db()
        self.assertEqual(
            self.ticket.status,
            SupportTicket.Status.OPEN,
        )
        self.assertIsNone(self.ticket.resolved_at)
        self.assertIsNone(self.ticket.closed_at)
        self.assertTrue(self.ticket.events.filter(
            action=SupportEvent.Action.REOPENED
        ).exists())

    def test_other_client_cannot_reopen_ticket(self):
        SupportService.resolve(
            ticket=self.ticket,
            actor=self.agent,
            resolution="Résolu.",
        )
        self.client.force_authenticate(self.other_client)

        response = self.client.post(
            f"/api/support/tickets/{self.ticket.id}/reopen/",
            format="json",
        )

        self.assertEqual(response.status_code, 404)

    def test_stats_are_reserved_to_agents(self):
        self.client.force_authenticate(self.client_user)

        response = self.client.get("/api/support/tickets/stats/")

        self.assertEqual(response.status_code, 403)

    def test_agent_can_view_stats(self):
        self.create_ticket(
            user=self.client_user,
            ticket_status=SupportTicket.Status.RESOLVED,
        )
        self.create_ticket(
            user=self.client_user,
            ticket_status=SupportTicket.Status.CLOSED,
            priority=SupportTicket.Priority.URGENT,
        )
        self.client.force_authenticate(self.agent)

        response = self.client.get("/api/support/tickets/stats/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total"], 3)
        self.assertEqual(response.data["open"], 1)
        self.assertEqual(response.data["resolved"], 1)
        self.assertEqual(response.data["closed"], 1)
        self.assertEqual(response.data["urgent"], 0)
        self.assertEqual(
            response.data["by_type"][
                SupportTicket.Type.QUESTION
            ],
            3,
        )


class MessageTests(SupportTestBase):
    def setUp(self):
        super().setUp()
        self.ticket = self.create_ticket(
            user=self.client_user,
            order=self.order,
        )

    def test_client_can_add_message(self):
        self.client.force_authenticate(self.client_user)

        response = self.client.post(
            f"/api/support/tickets/{self.ticket.id}/messages/",
            {"body": "  Message du client  "},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            response.data["body"],
            "Message du client",
        )
        self.assertEqual(
            response.data["author_name"],
            "Test Support",
        )
        self.assertFalse(response.data["is_internal"])

        self.assertTrue(
            AuditLog.objects.filter(
                action=AuditLog.Action.CREATE,
                target_type="support.supportmessage",
            ).exists()
        )

    def test_other_client_cannot_add_message(self):
        self.client.force_authenticate(self.other_client)

        response = self.client.post(
            f"/api/support/tickets/{self.ticket.id}/messages/",
            {"body": "Piratage"},
            format="json",
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(SupportMessage.objects.count(), 0)

    def test_empty_message_is_rejected(self):
        self.client.force_authenticate(self.client_user)

        response = self.client.post(
            f"/api/support/tickets/{self.ticket.id}/messages/",
            {"body": "   "},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("body", response.data)

    def test_agent_reply_moves_ticket_in_progress(self):
        self.client.force_authenticate(self.agent)

        response = self.client.post(
            f"/api/support/tickets/{self.ticket.id}/messages/",
            {"body": "Nous traitons votre demande."},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.ticket.refresh_from_db()
        self.assertEqual(
            self.ticket.status,
            SupportTicket.Status.IN_PROGRESS,
        )
        self.assertTrue(self.ticket.events.filter(
            action=SupportEvent.Action.STATUS_CHANGED
        ).exists())

    def test_internal_note_is_hidden_from_client(self):
        self.add_message(
            self.ticket,
            self.client_user,
            body="Message public",
        )

        self.client.force_authenticate(self.agent)
        response = self.client.post(
            f"/api/support/tickets/{self.ticket.id}/messages/",
            {
                "body": "Note interne",
                "is_internal": True,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["is_internal"])

        self.client.force_authenticate(self.client_user)
        response = self.client.get(
            f"/api/support/tickets/{self.ticket.id}/messages/"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(
            response.data[0]["body"],
            "Message public",
        )

        response = self.client.get(
            f"/api/support/tickets/{self.ticket.id}/"
        )
        self.assertEqual(len(response.data["messages"]), 1)

    def test_client_cannot_add_internal_note(self):
        self.client.force_authenticate(self.client_user)

        response = self.client.post(
            f"/api/support/tickets/{self.ticket.id}/messages/",
            {
                "body": "Note cachée",
                "is_internal": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("is_internal", response.data)
        self.assertEqual(SupportMessage.objects.count(), 0)

    def test_client_reply_reopens_resolved_ticket(self):
        SupportService.resolve(
            ticket=self.ticket,
            actor=self.agent,
            resolution="Résolu.",
        )
        self.client.force_authenticate(self.client_user)

        response = self.client.post(
            f"/api/support/tickets/{self.ticket.id}/messages/",
            {"body": "Le problème persiste."},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.ticket.refresh_from_db()
        self.assertEqual(
            self.ticket.status,
            SupportTicket.Status.OPEN,
        )
        self.assertIsNone(self.ticket.resolved_at)
        self.assertTrue(self.ticket.events.filter(
            action=SupportEvent.Action.REOPENED
        ).exists())

    def test_message_history_is_chronological(self):
        self.add_message(
            self.ticket,
            self.client_user,
            body="Premier message",
        )
        self.add_message(
            self.ticket,
            self.agent,
            body="Deuxième message",
        )
        self.client.force_authenticate(self.client_user)

        response = self.client.get(
            f"/api/support/tickets/{self.ticket.id}/messages/"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["body"] for item in response.data],
            ["Premier message", "Deuxième message"],
        )


class SupportModelTests(SupportTestBase):
    def test_string_representations(self):
        ticket = self.create_ticket(user=self.client_user)
        message = self.add_message(ticket, self.client_user)
        faq = FaqEntry.objects.create(
            question="Question ?",
            answer="Réponse.",
        )

        self.assertIn(ticket.reference, str(ticket))
        self.assertIn(ticket.subject, str(ticket))
        self.assertIn(ticket.reference, str(message))
        self.assertEqual(str(faq), "Question ?")

    def test_deleting_user_preserves_ticket_history(self):
        deletion_user = self.create_user(
            "support-deletion@example.com",
            self.client_role,
        )
        ticket = self.create_ticket(user=deletion_user)
        message = self.add_message(
            ticket,
            deletion_user,
            body="Historique conservé",
        )
        ticket_contact_name = ticket.contact_name
        message_author_name = message.author_name

        deletion_user.delete()

        ticket.refresh_from_db()
        message.refresh_from_db()

        self.assertIsNone(ticket.user_id)
        self.assertEqual(ticket.contact_name, ticket_contact_name)
        self.assertIsNone(message.author_id)
        self.assertEqual(message.author_name, message_author_name)

    def test_generated_reference_has_expected_format(self):
        ticket = self.create_ticket(user=self.client_user)

        self.assertRegex(
            ticket.reference,
            r"^SUP-[0-9A-F]{8}$",
        )
