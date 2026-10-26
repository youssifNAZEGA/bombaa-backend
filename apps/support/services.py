from django.db.models import Count, Q
from django.utils import timezone

from apps.accounts.permissions import user_has_permission

from .models import SupportEvent, SupportMessage, SupportTicket


class SupportService:
    """
    Règles métier du service client BOMBAA.
    """

    @staticmethod
    def is_agent(user):
        if not user or not user.is_authenticated:
            return False

        return (
            user.is_staff
            or user.is_superuser
            or user_has_permission(user, "support.manage")
        )

    @staticmethod
    def contact_snapshot(user):
        if user is None:
            return "", ""

        name = (
            f"{user.first_name} {user.last_name}"
        ).strip()

        return name or user.email, user.email

    @classmethod
    def record_event(
        cls,
        *,
        ticket,
        action,
        actor=None,
        previous_status=None,
        new_status=None,
        note=None,
    ):
        actor_name = ""

        if actor is not None:
            actor_name, _email = cls.contact_snapshot(actor)

        return SupportEvent.objects.create(
            ticket=ticket,
            action=action,
            actor=actor,
            actor_name=actor_name,
            previous_status=previous_status,
            new_status=new_status,
            note=note,
        )

    @classmethod
    def add_message(
        cls,
        *,
        ticket,
        author,
        body,
        is_internal=False,
    ):
        author_name, author_email = cls.contact_snapshot(
            author
        )

        message = SupportMessage.objects.create(
            ticket=ticket,
            author=author,
            author_name=author_name,
            author_email=author_email,
            body=body.strip(),
            is_internal=is_internal,
        )

        if is_internal:
            return message

        if cls.is_agent(author):
            if ticket.status == SupportTicket.Status.OPEN:
                previous_status = ticket.status
                ticket.status = (
                    SupportTicket.Status.IN_PROGRESS
                )
                ticket.save(
                    update_fields=["status", "updated_at"]
                )
                cls.record_event(
                    ticket=ticket,
                    action=SupportEvent.Action.STATUS_CHANGED,
                    actor=author,
                    previous_status=previous_status,
                    new_status=ticket.status,
                    note="Réponse du service client",
                )
        elif ticket.status in [
            SupportTicket.Status.RESOLVED,
            SupportTicket.Status.CLOSED,
        ]:
            cls.reopen(
                ticket=ticket,
                actor=author,
                note="Réponse du client",
            )

        return message

    @classmethod
    def assign(cls, *, ticket, assignee, actor):
        previous_status = ticket.status
        ticket.assigned_to = assignee

        update_fields = ["assigned_to", "updated_at"]

        if (
            assignee is not None
            and ticket.status == SupportTicket.Status.OPEN
        ):
            ticket.status = SupportTicket.Status.IN_PROGRESS
            update_fields.append("status")

        ticket.save(update_fields=update_fields)

        assignee_name = ""

        if assignee is not None:
            assignee_name, _email = cls.contact_snapshot(
                assignee
            )

        cls.record_event(
            ticket=ticket,
            action=SupportEvent.Action.ASSIGNED,
            actor=actor,
            previous_status=previous_status,
            new_status=ticket.status,
            note=(
                f"Affecté à {assignee_name}"
                if assignee_name
                else "Désaffecté"
            ),
        )

        return ticket

    @classmethod
    def resolve(cls, *, ticket, actor, resolution):
        previous_status = ticket.status
        ticket.status = SupportTicket.Status.RESOLVED
        ticket.resolution = resolution.strip()
        ticket.resolved_at = timezone.now()
        ticket.closed_at = None
        ticket.save(
            update_fields=[
                "status",
                "resolution",
                "resolved_at",
                "closed_at",
                "updated_at",
            ]
        )

        cls.record_event(
            ticket=ticket,
            action=SupportEvent.Action.RESOLVED,
            actor=actor,
            previous_status=previous_status,
            new_status=ticket.status,
            note=ticket.resolution,
        )

        return ticket

    @classmethod
    def close(cls, *, ticket, actor, note=None):
        previous_status = ticket.status
        ticket.status = SupportTicket.Status.CLOSED
        ticket.closed_at = timezone.now()
        ticket.save(
            update_fields=[
                "status",
                "closed_at",
                "updated_at",
            ]
        )

        cls.record_event(
            ticket=ticket,
            action=SupportEvent.Action.CLOSED,
            actor=actor,
            previous_status=previous_status,
            new_status=ticket.status,
            note=note,
        )

        return ticket

    @classmethod
    def reopen(cls, *, ticket, actor, note=None):
        previous_status = ticket.status
        ticket.status = SupportTicket.Status.OPEN
        ticket.resolved_at = None
        ticket.closed_at = None
        ticket.save(
            update_fields=[
                "status",
                "resolved_at",
                "closed_at",
                "updated_at",
            ]
        )

        cls.record_event(
            ticket=ticket,
            action=SupportEvent.Action.REOPENED,
            actor=actor,
            previous_status=previous_status,
            new_status=ticket.status,
            note=note,
        )

        return ticket

    @staticmethod
    def visible_messages(ticket, *, include_internal=False):
        queryset = ticket.messages.select_related("author")

        if not include_internal:
            queryset = queryset.filter(is_internal=False)

        return queryset

    @staticmethod
    def stats():
        base = SupportTicket.objects.all()

        counts = base.aggregate(
            total=Count("id"),
            open=Count(
                "id",
                filter=Q(
                    status=SupportTicket.Status.OPEN
                ),
            ),
            in_progress=Count(
                "id",
                filter=Q(
                    status=SupportTicket.Status.IN_PROGRESS
                ),
            ),
            resolved=Count(
                "id",
                filter=Q(
                    status=SupportTicket.Status.RESOLVED
                ),
            ),
            closed=Count(
                "id",
                filter=Q(
                    status=SupportTicket.Status.CLOSED
                ),
            ),
            unassigned=Count(
                "id",
                filter=Q(assigned_to__isnull=True)
                & ~Q(
                    status=SupportTicket.Status.CLOSED
                ),
            ),
            urgent=Count(
                "id",
                filter=Q(
                    priority=SupportTicket.Priority.URGENT
                )
                & ~Q(
                    status__in=[
                        SupportTicket.Status.RESOLVED,
                        SupportTicket.Status.CLOSED,
                    ]
                ),
            ),
        )

        by_type = {
            value: base.filter(type=value).count()
            for value, _label in SupportTicket.Type.choices
        }

        return {
            "total": counts["total"],
            "open": counts["open"],
            "in_progress": counts["in_progress"],
            "resolved": counts["resolved"],
            "closed": counts["closed"],
            "unassigned": counts["unassigned"],
            "urgent": counts["urgent"],
            "by_type": by_type,
        }
