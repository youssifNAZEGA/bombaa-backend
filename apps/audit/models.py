from django.conf import settings
from django.db import models


class AuditLog(models.Model):

    class Action(models.TextChoices):
        CREATE = "CREATE", "Création"
        UPDATE = "UPDATE", "Modification"
        DELETE = "DELETE", "Suppression"
        ACTIVATE = "ACTIVATE", "Activation"
        DEACTIVATE = "DEACTIVATE", "Désactivation"
        STATUS_CHANGE = "STATUS_CHANGE", "Changement de statut"
        CANCEL = "CANCEL", "Annulation"
        ASSIGN = "ASSIGN", "Attribution"
        LOGIN = "LOGIN", "Connexion"
        LOGOUT = "LOGOUT", "Déconnexion"
        OTHER = "OTHER", "Autre"

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
        db_column="actor_id",
    )

    actor_email = models.CharField(
        max_length=255,
        blank=True,
    )

    action = models.CharField(
        max_length=30,
        choices=Action.choices,
    )

    target_type = models.CharField(
        max_length=100,
        blank=True,
    )

    target_id = models.CharField(
        max_length=64,
        blank=True,
    )

    target_repr = models.CharField(
        max_length=255,
        blank=True,
    )

    changes = models.JSONField(
        default=dict,
        blank=True,
    )

    metadata = models.JSONField(
        default=dict,
        blank=True,
    )

    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
    )

    user_agent = models.CharField(
        max_length=500,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        db_table = "audit_logs"
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["actor", "-created_at"],
                name="idx_audit_actor_created",
            ),
            models.Index(
                fields=["target_type", "target_id"],
                name="idx_audit_target",
            ),
            models.Index(
                fields=["action", "-created_at"],
                name="idx_audit_action_created",
            ),
        ]

    def __str__(self):
        return (
            f"{self.action} - {self.target_type} "
            f"{self.target_id}"
        )
