from django.db.models import Q
from django.utils.dateparse import parse_date

from rest_framework import viewsets

from apps.accounts.permissions import HasPermission

from .models import AuditLog
from .serializers import AuditLogSerializer


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):

    serializer_class = AuditLogSerializer
    permission_classes = [HasPermission("audit.view")]

    def get_queryset(self):
        queryset = AuditLog.objects.select_related(
            "actor"
        ).all()

        actor = self.request.query_params.get("actor")

        if actor:
            actor = actor.strip()

            if actor.isdigit():
                queryset = queryset.filter(
                    actor_id=int(actor)
                )
            else:
                queryset = queryset.filter(
                    actor_email__iexact=actor
                )

        action = self.request.query_params.get("action")

        if action:
            action = action.strip().upper()

            valid_actions = {
                value
                for value, _label in AuditLog.Action.choices
            }

            if action not in valid_actions:
                return queryset.none()

            queryset = queryset.filter(action=action)

        target_type = self.request.query_params.get(
            "target_type"
        )

        if target_type:
            queryset = queryset.filter(
                target_type=target_type
            )

        target_id = self.request.query_params.get("target_id")

        if target_id:
            queryset = queryset.filter(
                target_id=str(target_id)
            )

        date_from = self.request.query_params.get("date_from")

        if date_from:
            parsed_date = parse_date(date_from)

            if parsed_date is None:
                return queryset.none()

            queryset = queryset.filter(
                created_at__date__gte=parsed_date
            )

        date_to = self.request.query_params.get("date_to")

        if date_to:
            parsed_date = parse_date(date_to)

            if parsed_date is None:
                return queryset.none()

            queryset = queryset.filter(
                created_at__date__lte=parsed_date
            )

        search = self.request.query_params.get("search")

        if search:
            queryset = queryset.filter(
                Q(actor_email__icontains=search)
                | Q(target_repr__icontains=search)
                | Q(target_id__icontains=search)
            )

        return queryset
