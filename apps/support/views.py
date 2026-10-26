from django.conf import settings
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404

from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import (
    AllowAny,
    BasePermission,
    IsAuthenticated,
)
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.audit.models import AuditLog
from apps.audit.services import AuditService

from .models import FaqEntry, SupportTicket
from .serializers import (
    FaqEntrySerializer,
    SupportMessageCreateSerializer,
    SupportMessageSerializer,
    SupportTicketDetailSerializer,
    SupportTicketListSerializer,
)
from .services import SupportService


class IsSupportAgent(BasePermission):
    message = (
        "Vous n'avez pas la permission de gérer le service client."
    )

    def has_permission(self, request, view):
        return SupportService.is_agent(request.user)


class SupportTicketViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = SupportTicketDetailSerializer

    def get_permissions(self):
        if self.action == "create":
            return [AllowAny()]

        if self.action in ["list", "retrieve", "messages", "reopen"]:
            return [IsAuthenticated()]

        if self.action in [
            "update",
            "partial_update",
            "assign",
            "resolve",
            "close",
            "stats",
        ]:
            return [IsSupportAgent()]

        return [IsAuthenticated()]

    def get_serializer_class(self):
        if self.action == "list":
            return SupportTicketListSerializer

        return SupportTicketDetailSerializer

    def get_queryset(self):
        user = self.request.user
        is_agent = SupportService.is_agent(user)

        queryset = (
            SupportTicket.objects
            .select_related(
                "user",
                "order",
                "assigned_to",
            )
        )

        if not user or not user.is_authenticated:
            return queryset.none()

        if not is_agent:
            queryset = queryset.filter(user=user)

        ticket_status = self.request.query_params.get("status")

        if ticket_status:
            queryset = queryset.filter(
                status=ticket_status.strip().upper()
            )

        ticket_type = self.request.query_params.get("type")

        if ticket_type:
            queryset = queryset.filter(
                type=ticket_type.strip().upper()
            )

        priority = self.request.query_params.get("priority")

        if priority:
            queryset = queryset.filter(
                priority=priority.strip().upper()
            )

        assigned_to = self.request.query_params.get(
            "assigned_to"
        )

        if assigned_to:
            normalized = assigned_to.strip().lower()

            if normalized == "me":
                queryset = queryset.filter(
                    assigned_to=user
                )
            elif normalized in {"none", "unassigned"}:
                queryset = queryset.filter(
                    assigned_to__isnull=True
                )
            elif normalized.isdigit():
                queryset = queryset.filter(
                    assigned_to_id=int(normalized)
                )
            else:
                queryset = queryset.none()

        order = self.request.query_params.get("order")

        if order:
            if order.isdigit():
                queryset = queryset.filter(
                    order_id=int(order)
                )
            else:
                queryset = queryset.filter(
                    order__reference=order
                )

        search = self.request.query_params.get("search")

        if search:
            queryset = queryset.filter(
                Q(subject__icontains=search)
                | Q(description__icontains=search)
                | Q(reference__icontains=search)
                | Q(contact_name__icontains=search)
                | Q(contact_email__icontains=search)
                | Q(order__reference__icontains=search)
            )

        if is_agent:
            queryset = queryset.annotate(
                messages_count=Count("messages")
            )
        else:
            queryset = queryset.annotate(
                messages_count=Count(
                    "messages",
                    filter=Q(messages__is_internal=False),
                )
            )

        return queryset.order_by("-created_at")

    def perform_create(self, serializer):
        ticket = serializer.save()

        AuditService.log(
            action=AuditLog.Action.CREATE,
            actor=self.request.user,
            target=ticket,
            metadata={
                "type": ticket.type,
                "priority": ticket.priority,
                "anonymous": ticket.user_id is None,
                "order_id": ticket.order_id,
            },
            request=self.request,
        )

    def perform_update(self, serializer):
        ticket = serializer.instance

        before = {
            "type": ticket.type,
            "priority": ticket.priority,
            "subject": ticket.subject,
            "description": ticket.description,
            "order_id": ticket.order_id,
            "contact_name": ticket.contact_name,
            "contact_email": ticket.contact_email,
            "contact_phone": ticket.contact_phone,
        }

        ticket = serializer.save()

        after = {
            "type": ticket.type,
            "priority": ticket.priority,
            "subject": ticket.subject,
            "description": ticket.description,
            "order_id": ticket.order_id,
            "contact_name": ticket.contact_name,
            "contact_email": ticket.contact_email,
            "contact_phone": ticket.contact_phone,
        }

        changes = {
            field: {
                "before": before[field],
                "after": after[field],
            }
            for field in before
            if before[field] != after[field]
        }

        AuditService.log(
            action=AuditLog.Action.UPDATE,
            actor=self.request.user,
            target=ticket,
            changes=changes,
            request=self.request,
        )

    @action(
        detail=True,
        methods=["get", "post"],
        url_path="messages",
    )
    def messages(self, request, pk=None):
        ticket = self.get_object()
        is_agent = SupportService.is_agent(request.user)

        if request.method.lower() == "get":
            messages = SupportService.visible_messages(
                ticket,
                include_internal=is_agent,
            )

            return Response(
                SupportMessageSerializer(
                    messages,
                    many=True,
                ).data
            )

        serializer = SupportMessageCreateSerializer(
            data=request.data,
            context=self.get_serializer_context(),
        )
        serializer.is_valid(raise_exception=True)

        is_internal = serializer.validated_data.get(
            "is_internal",
            False,
        )

        if is_internal and not is_agent:
            raise ValidationError(
                {
                    "is_internal": (
                        "Seul le service client peut ajouter "
                        "une note interne."
                    )
                }
            )

        message = SupportService.add_message(
            ticket=ticket,
            author=request.user,
            body=serializer.validated_data["body"],
            is_internal=is_internal,
        )

        AuditService.log(
            action=AuditLog.Action.CREATE,
            actor=request.user,
            target=message,
            metadata={
                "ticket_id": ticket.id,
                "ticket_reference": ticket.reference,
                "is_internal": message.is_internal,
            },
            request=request,
        )

        return Response(
            SupportMessageSerializer(message).data,
            status=status.HTTP_201_CREATED,
        )

    @action(
        detail=True,
        methods=["post"],
        url_path="assign",
    )
    def assign(self, request, pk=None):
        ticket = self.get_object()
        previous_assignee_id = ticket.assigned_to_id

        assignee_id = request.data.get("assigned_to")

        if assignee_id in [None, "", 0, "0"]:
            assignee = None
        else:
            assignee = get_object_or_404(
                User,
                pk=assignee_id,
                is_active=True,
            )

            if not SupportService.is_agent(assignee):
                raise ValidationError(
                    {
                        "assigned_to": (
                            "L'utilisateur choisi n'est pas "
                            "agent du service client."
                        )
                    }
                )

        SupportService.assign(
            ticket=ticket,
            assignee=assignee,
            actor=request.user,
        )

        AuditService.log(
            action=AuditLog.Action.ASSIGN,
            actor=request.user,
            target=ticket,
            changes={
                "assigned_to_id": {
                    "before": previous_assignee_id,
                    "after": ticket.assigned_to_id,
                }
            },
            request=request,
        )

        return Response(
            SupportTicketDetailSerializer(
                ticket,
                context=self.get_serializer_context(),
            ).data
        )

    @action(
        detail=True,
        methods=["post"],
        url_path="resolve",
    )
    def resolve(self, request, pk=None):
        ticket = self.get_object()
        resolution = (
            request.data.get("resolution") or ""
        ).strip()

        if not resolution:
            raise ValidationError(
                {
                    "resolution": (
                        "La résolution est obligatoire."
                    )
                }
            )

        previous_status = ticket.status

        SupportService.resolve(
            ticket=ticket,
            actor=request.user,
            resolution=resolution,
        )

        AuditService.log(
            action=AuditLog.Action.STATUS_CHANGE,
            actor=request.user,
            target=ticket,
            changes={
                "status": {
                    "before": previous_status,
                    "after": ticket.status,
                }
            },
            metadata={"resolution": resolution},
            request=request,
        )

        return Response(
            SupportTicketDetailSerializer(
                ticket,
                context=self.get_serializer_context(),
            ).data
        )

    @action(
        detail=True,
        methods=["post"],
        url_path="close",
    )
    def close(self, request, pk=None):
        ticket = self.get_object()

        if ticket.status == SupportTicket.Status.CLOSED:
            return Response(
                SupportTicketDetailSerializer(
                    ticket,
                    context=self.get_serializer_context(),
                ).data
            )

        previous_status = ticket.status
        note = request.data.get("note")

        SupportService.close(
            ticket=ticket,
            actor=request.user,
            note=note,
        )

        AuditService.log(
            action=AuditLog.Action.STATUS_CHANGE,
            actor=request.user,
            target=ticket,
            changes={
                "status": {
                    "before": previous_status,
                    "after": ticket.status,
                }
            },
            metadata={"note": note},
            request=request,
        )

        return Response(
            SupportTicketDetailSerializer(
                ticket,
                context=self.get_serializer_context(),
            ).data
        )

    @action(
        detail=True,
        methods=["post"],
        url_path="reopen",
    )
    def reopen(self, request, pk=None):
        ticket = self.get_object()

        if ticket.status == SupportTicket.Status.OPEN:
            return Response(
                SupportTicketDetailSerializer(
                    ticket,
                    context=self.get_serializer_context(),
                ).data
            )

        previous_status = ticket.status
        note = request.data.get("note")

        SupportService.reopen(
            ticket=ticket,
            actor=request.user,
            note=note,
        )

        AuditService.log(
            action=AuditLog.Action.STATUS_CHANGE,
            actor=request.user,
            target=ticket,
            changes={
                "status": {
                    "before": previous_status,
                    "after": ticket.status,
                }
            },
            metadata={"note": note},
            request=request,
        )

        return Response(
            SupportTicketDetailSerializer(
                ticket,
                context=self.get_serializer_context(),
            ).data
        )

    @action(
        detail=False,
        methods=["get"],
        url_path="stats",
    )
    def stats(self, request):
        return Response(SupportService.stats())


class FaqEntryViewSet(viewsets.ModelViewSet):
    serializer_class = FaqEntrySerializer
    pagination_class = None

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [AllowAny()]

        return [IsSupportAgent()]

    def get_queryset(self):
        queryset = FaqEntry.objects.all()

        if not SupportService.is_agent(self.request.user):
            queryset = queryset.filter(is_active=True)

        category = self.request.query_params.get("category")

        if category:
            queryset = queryset.filter(
                category__iexact=category.strip()
            )

        search = self.request.query_params.get("search")

        if search:
            queryset = queryset.filter(
                Q(question__icontains=search)
                | Q(answer__icontains=search)
                | Q(category__icontains=search)
            )

        return queryset

    def perform_create(self, serializer):
        entry = serializer.save()

        AuditService.log(
            action=AuditLog.Action.CREATE,
            actor=self.request.user,
            target=entry,
            request=self.request,
        )

    def perform_update(self, serializer):
        entry = serializer.instance

        before = {
            "question": entry.question,
            "answer": entry.answer,
            "category": entry.category,
            "display_order": entry.display_order,
            "is_active": entry.is_active,
        }

        entry = serializer.save()

        after = {
            "question": entry.question,
            "answer": entry.answer,
            "category": entry.category,
            "display_order": entry.display_order,
            "is_active": entry.is_active,
        }

        changes = {
            field: {
                "before": before[field],
                "after": after[field],
            }
            for field in before
            if before[field] != after[field]
        }

        AuditService.log(
            action=AuditLog.Action.UPDATE,
            actor=self.request.user,
            target=entry,
            changes=changes,
            request=self.request,
        )

    def perform_destroy(self, instance):
        entry_id = instance.pk
        entry_repr = str(instance)

        instance.delete()

        AuditService.log(
            action=AuditLog.Action.DELETE,
            actor=self.request.user,
            target_type="support.faqentry",
            target_id=str(entry_id),
            target_repr=entry_repr,
            request=self.request,
        )


class SupportContactView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response(
            {
                "email": settings.SUPPORT_EMAIL,
                "phone": settings.SUPPORT_PHONE,
                "hours": settings.SUPPORT_HOURS,
                "faq_endpoint": "/api/support/faq/",
                "contact_endpoint": "/api/support/tickets/",
            }
        )
