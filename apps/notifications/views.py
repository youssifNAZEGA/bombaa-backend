from django.utils import timezone

from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import HasPermission

from .models import Notification
from .serializers import (
    NotificationBroadcastSerializer,
    NotificationCreateSerializer,
    NotificationPreferenceSerializer,
    NotificationSerializer,
)
from .services import NotificationService


class NotificationViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """
    Liste les notifications de l'utilisateur connecté et permet
    de les marquer comme lues.

    La création d'une notification ciblée et la diffusion d'une
    notification de masse sont réservées aux administrateurs.
    """

    serializer_class = NotificationSerializer

    def get_permissions(self):
        if self.action in ["create", "broadcast"]:
            return [
                HasPermission("notifications.create")()
            ]

        return [IsAuthenticated()]

    def get_queryset(self):
        queryset = (
            Notification.objects
            .filter(user=self.request.user)
            .select_related("order", "product")
        )

        unread = self.request.query_params.get("unread")

        if unread is not None:
            normalized = str(unread).strip().lower()

            if normalized in {"true", "1", "yes"}:
                queryset = queryset.filter(is_read=False)

            elif normalized in {"false", "0", "no"}:
                queryset = queryset.filter(is_read=True)

        is_read = self.request.query_params.get("is_read")

        if is_read is not None:
            normalized = str(is_read).strip().lower()

            if normalized in {"true", "1", "yes"}:
                queryset = queryset.filter(is_read=True)

            elif normalized in {"false", "0", "no"}:
                queryset = queryset.filter(is_read=False)

        event = self.request.query_params.get("event")

        if event:
            queryset = queryset.filter(event=event)

        channel = self.request.query_params.get("channel")

        if channel:
            queryset = queryset.filter(channel=channel)

        return queryset

    def create(self, request):
        serializer = NotificationCreateSerializer(
            data=request.data
        )

        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        notification = NotificationService.notify(
            user=data["user"],
            event=data["event"],
            title=data["title"],
            message=data["message"],
            order=data.get("order"),
            product=data.get("product"),
            data=data.get("data"),
        )

        if notification is None:
            return Response(
                {
                    "detail": (
                        "L'utilisateur a désactivé les "
                        "notifications dans l'application."
                    )
                },
                status=status.HTTP_200_OK,
            )

        return Response(
            NotificationSerializer(notification).data,
            status=status.HTTP_201_CREATED,
        )

    @action(
        detail=True,
        methods=["post"],
        url_path="read",
    )
    def read(self, request, pk=None):
        notification = self.get_object()
        notification.mark_as_read()

        return Response(
            NotificationSerializer(notification).data
        )

    @action(
        detail=False,
        methods=["post"],
        url_path="read-all",
    )
    def read_all(self, request):
        updated = (
            self.get_queryset()
            .filter(is_read=False)
            .update(
                is_read=True,
                read_at=timezone.now(),
            )
        )

        return Response(
            {
                "updated": updated,
            }
        )

    @action(
        detail=False,
        methods=["get"],
        url_path="unread-count",
    )
    def unread_count(self, request):
        count = self.get_queryset().filter(
            is_read=False
        ).count()

        return Response(
            {
                "unread_count": count,
            }
        )

    @action(
        detail=False,
        methods=["get", "patch"],
        url_path="preferences",
    )
    def preferences(self, request):
        preferences = NotificationService.get_preferences(
            request.user
        )

        if request.method == "GET":
            return Response(
                NotificationPreferenceSerializer(
                    preferences
                ).data
            )

        serializer = NotificationPreferenceSerializer(
            preferences,
            data=request.data,
            partial=True,
        )

        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data)

    @action(
        detail=False,
        methods=["post"],
        url_path="broadcast",
    )
    def broadcast(self, request):
        serializer = NotificationBroadcastSerializer(
            data=request.data
        )

        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data

        created_count = NotificationService.broadcast(
            event=data["event"],
            title=data["title"],
            message=data["message"],
            recipients=data.get("users"),
            product=data.get("product"),
            data=data.get("data"),
        )

        return Response(
            {
                "created": created_count,
            },
            status=status.HTTP_201_CREATED,
        )
