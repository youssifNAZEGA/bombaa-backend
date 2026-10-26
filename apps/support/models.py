from uuid import uuid4

from django.db import models
from django.utils import timezone


class FaqEntry(models.Model):
    """
    Question fréquente affichée publiquement sur le site.
    """

    question = models.CharField(
        max_length=255,
    )

    answer = models.TextField()

    category = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )

    display_order = models.PositiveIntegerField(
        default=0,
    )

    is_active = models.BooleanField(
        default=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        db_table = "support_faq_entries"
        ordering = ["display_order", "id"]
        indexes = [
            models.Index(
                fields=["is_active", "display_order"],
                name="idx_faq_active_order",
            ),
        ]

    def __str__(self):
        return self.question


class SupportTicket(models.Model):
    """
    Demande envoyée au service client.

    Le ticket peut être créé par un utilisateur connecté ou via
    le formulaire de contact public. Les coordonnées sont
    conservées même si le compte est supprimé.
    """

    class Type(models.TextChoices):
        QUESTION = "QUESTION", "Question"
        COMPLAINT = "COMPLAINT", "Réclamation"
        RETURN = "RETURN", "Retour"
        REFUND = "REFUND", "Remboursement"
        OTHER = "OTHER", "Autre"

    class Status(models.TextChoices):
        OPEN = "OPEN", "Ouvert"
        IN_PROGRESS = "IN_PROGRESS", "En cours"
        RESOLVED = "RESOLVED", "Résolu"
        CLOSED = "CLOSED", "Fermé"

    class Priority(models.TextChoices):
        LOW = "LOW", "Basse"
        NORMAL = "NORMAL", "Normale"
        HIGH = "HIGH", "Haute"
        URGENT = "URGENT", "Urgente"

    reference = models.CharField(
        max_length=30,
        unique=True,
        editable=False,
    )

    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        related_name="support_tickets",
        db_column="user_id",
        blank=True,
        null=True,
    )

    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.SET_NULL,
        related_name="support_tickets",
        db_column="order_id",
        blank=True,
        null=True,
    )

    type = models.CharField(
        max_length=20,
        choices=Type.choices,
        default=Type.QUESTION,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.OPEN,
    )

    priority = models.CharField(
        max_length=20,
        choices=Priority.choices,
        default=Priority.NORMAL,
    )

    subject = models.CharField(
        max_length=255,
    )

    description = models.TextField()

    contact_name = models.CharField(
        max_length=200,
    )

    contact_email = models.EmailField(
        max_length=255,
    )

    contact_phone = models.CharField(
        max_length=30,
        blank=True,
        null=True,
    )

    assigned_to = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        related_name="assigned_support_tickets",
        db_column="assigned_to_id",
        blank=True,
        null=True,
    )

    resolution = models.TextField(
        blank=True,
        null=True,
    )

    resolved_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    closed_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        db_table = "support_tickets"
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["status", "-created_at"],
                name="idx_tickets_status_created",
            ),
            models.Index(
                fields=["type", "status"],
                name="idx_tickets_type_status",
            ),
            models.Index(
                fields=["user", "-created_at"],
                name="idx_tickets_user_created",
            ),
            models.Index(
                fields=["assigned_to", "status"],
                name="idx_tickets_assignee_status",
            ),
        ]

    @classmethod
    def generate_reference(cls):
        while True:
            reference = f"SUP-{uuid4().hex[:8].upper()}"

            if not cls.objects.filter(
                reference=reference
            ).exists():
                return reference

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = self.generate_reference()

        super().save(*args, **kwargs)

    def is_closed(self):
        return self.status == self.Status.CLOSED

    def __str__(self):
        return f"{self.reference} - {self.subject}"


class SupportMessage(models.Model):
    """
    Message échangé dans le fil d'un ticket.

    Les notes internes ne sont visibles que par les agents du
    service client.
    """

    ticket = models.ForeignKey(
        SupportTicket,
        on_delete=models.CASCADE,
        related_name="messages",
        db_column="ticket_id",
    )

    author = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        related_name="support_messages",
        db_column="author_id",
        blank=True,
        null=True,
    )

    author_name = models.CharField(
        max_length=200,
    )

    author_email = models.EmailField(
        max_length=255,
        blank=True,
        null=True,
    )

    body = models.TextField()

    is_internal = models.BooleanField(
        default=False,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        db_table = "support_messages"
        ordering = ["created_at", "id"]
        indexes = [
            models.Index(
                fields=["ticket", "created_at"],
                name="idx_messages_ticket_created",
            ),
            models.Index(
                fields=["ticket", "is_internal"],
                name="idx_messages_ticket_internal",
            ),
        ]

    def __str__(self):
        return (
            f"{self.ticket.reference} - "
            f"{self.author_name or 'Support'}"
        )


class SupportEvent(models.Model):
    """
    Historique des changements de statut d'un ticket.

    Il complète le fil des messages pour conserver une trace
    lisible des affectations, résolutions et fermetures.
    """

    class Action(models.TextChoices):
        CREATED = "CREATED", "Création"
        ASSIGNED = "ASSIGNED", "Affectation"
        STATUS_CHANGED = "STATUS_CHANGED", "Changement de statut"
        RESOLVED = "RESOLVED", "Résolution"
        CLOSED = "CLOSED", "Fermeture"
        REOPENED = "REOPENED", "Réouverture"

    ticket = models.ForeignKey(
        SupportTicket,
        on_delete=models.CASCADE,
        related_name="events",
        db_column="ticket_id",
    )

    action = models.CharField(
        max_length=20,
        choices=Action.choices,
    )

    actor = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        related_name="support_events",
        db_column="actor_id",
        blank=True,
        null=True,
    )

    actor_name = models.CharField(
        max_length=200,
        blank=True,
        null=True,
    )

    previous_status = models.CharField(
        max_length=20,
        blank=True,
        null=True,
    )

    new_status = models.CharField(
        max_length=20,
        blank=True,
        null=True,
    )

    note = models.TextField(
        blank=True,
        null=True,
    )

    created_at = models.DateTimeField(
        default=timezone.now,
    )

    class Meta:
        db_table = "support_events"
        ordering = ["created_at", "id"]
        indexes = [
            models.Index(
                fields=["ticket", "created_at"],
                name="idx_support_events_ticket",
            ),
        ]

    def __str__(self):
        return f"{self.ticket.reference} - {self.action}"
