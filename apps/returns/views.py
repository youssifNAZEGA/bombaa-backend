from django.db.models import Q
from django.shortcuts import get_object_or_404

from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.accounts.permissions import HasPermission
from apps.audit.models import AuditLog
from apps.audit.services import AuditService
from apps.orders.models import Order

from .models import Refund, ReturnRequest
from .serializers import (
    RefundSerializer,
    ReturnRequestListSerializer,
    ReturnRequestSerializer,
)
from .services import RefundService, ReturnService


class ReturnRequestViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = ReturnRequestSerializer

    def get_permissions(self):
        if self.action == "create":
            return [HasPermission("returns.create")()]

        if self.action in [
            "list",
            "retrieve",
            "cancel",
            "eligibility",
        ]:
            return [HasPermission("returns.view")()]

        if self.action in ["approve", "reject", "receive"]:
            return [HasPermission("returns.update")()]

        return [HasPermission("returns.view")()]

    def get_serializer_class(self):
        if self.action == "list":
            return ReturnRequestListSerializer

        return ReturnRequestSerializer

    def get_queryset(self):
        user = self.request.user

        queryset = (
            ReturnRequest.objects
            .select_related(
                "order",
                "order__user",
                "processed_by",
            )
            .prefetch_related("items")
        )

        if not user or not user.is_authenticated:
            return queryset.none()

        if not ReturnService.is_manager(user):
            queryset = queryset.filter(order__user=user)

        return_status = self.request.query_params.get("status")

        if return_status:
            queryset = queryset.filter(
                status=return_status.strip().upper()
            )

        order = self.request.query_params.get("order")

        if order:
            if order.isdigit():
                queryset = queryset.filter(order_id=int(order))
            else:
                queryset = queryset.filter(
                    order__reference=order
                )

        search = self.request.query_params.get("search")

        if search:
            queryset = queryset.filter(
                Q(reference__icontains=search)
                | models.Q(reason__icontains=search)
                | models.Q(order__reference__icontains=search)
            )

        return queryset.order_by("-created_at")

    def perform_create(self, serializer):
        return_request = serializer.save()

        AuditService.log(
            action=AuditLog.Action.CREATE,
            actor=self.request.user,
            target=return_request,
            metadata={
                "order_id": return_request.order_id,
                "order_reference": (
                    return_request.order.reference
                ),
                "items_count": return_request.items.count(),
                "total_amount": str(
                    return_request.total_amount
                ),
            },
            request=self.request,
        )

    @action(
        detail=True,
        methods=["post"],
        url_path="cancel",
    )
    def cancel(self, request, pk=None):
        return_request = self.get_object()
        previous_status = return_request.status

        try:
            ReturnService.cancel(
                return_request=return_request,
                actor=request.user,
            )
        except ValueError as exc:
            raise ValidationError({"detail": str(exc)})

        AuditService.log(
            action=AuditLog.Action.CANCEL,
            actor=request.user,
            target=return_request,
            changes={
                "status": {
                    "before": previous_status,
                    "after": return_request.status,
                }
            },
            request=request,
        )

        return Response(
            ReturnRequestSerializer(
                return_request,
                context=self.get_serializer_context(),
            ).data
        )

    @action(
        detail=True,
        methods=["post"],
        url_path="approve",
    )
    def approve(self, request, pk=None):
        return_request = self.get_object()

        if (
            return_request.status
            == ReturnRequest.Status.APPROVED
        ):
            return Response(
                ReturnRequestSerializer(
                    return_request,
                    context=self.get_serializer_context(),
                ).data
            )

        previous_status = return_request.status

        try:
            ReturnService.approve(
                return_request=return_request,
                actor=request.user,
            )
        except ValueError as exc:
            raise ValidationError({"detail": str(exc)})

        AuditService.log(
            action=AuditLog.Action.STATUS_CHANGE,
            actor=request.user,
            target=return_request,
            changes={
                "status": {
                    "before": previous_status,
                    "after": return_request.status,
                }
            },
            request=request,
        )

        return Response(
            ReturnRequestSerializer(
                return_request,
                context=self.get_serializer_context(),
            ).data
        )

    @action(
        detail=True,
        methods=["post"],
        url_path="reject",
    )
    def reject(self, request, pk=None):
        return_request = self.get_object()
        previous_status = return_request.status
        note = request.data.get("admin_note")

        try:
            ReturnService.reject(
                return_request=return_request,
                actor=request.user,
                note=note,
            )
        except ValueError as exc:
            raise ValidationError({"detail": str(exc)})

        AuditService.log(
            action=AuditLog.Action.STATUS_CHANGE,
            actor=request.user,
            target=return_request,
            changes={
                "status": {
                    "before": previous_status,
                    "after": return_request.status,
                }
            },
            metadata={"admin_note": note},
            request=request,
        )

        return Response(
            ReturnRequestSerializer(
                return_request,
                context=self.get_serializer_context(),
            ).data
        )

    @action(
        detail=True,
        methods=["post"],
        url_path="receive",
    )
    def receive(self, request, pk=None):
        return_request = self.get_object()
        previous_status = return_request.status

        try:
            ReturnService.receive(
                return_request=return_request,
                actor=request.user,
            )
        except ValueError as exc:
            raise ValidationError({"detail": str(exc)})

        AuditService.log(
            action=AuditLog.Action.STATUS_CHANGE,
            actor=request.user,
            target=return_request,
            changes={
                "status": {
                    "before": previous_status,
                    "after": return_request.status,
                }
            },
            metadata={
                "order_id": return_request.order_id,
                "restocked": True,
            },
            request=request,
        )

        return Response(
            ReturnRequestSerializer(
                return_request,
                context=self.get_serializer_context(),
            ).data
        )

    @action(
        detail=False,
        methods=["get"],
        url_path="eligibility",
    )
    def eligibility(self, request):
        value = request.query_params.get("order")

        if not value:
            return Response(
                {
                    "order": (
                        "Le paramètre order est obligatoire."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        orders = Order.objects.select_related("user")

        if not ReturnService.is_manager(request.user):
            orders = orders.filter(user=request.user)

        if value.isdigit():
            order = get_object_or_404(orders, pk=int(value))
        else:
            order = get_object_or_404(
                orders,
                reference=value,
            )

        try:
            ReturnService.validate_order(order)
        except ValueError as exc:
            return Response(
                {
                    "order": order.id,
                    "order_reference": order.reference,
                    "order_status": order.status,
                    "can_return": False,
                    "reason": str(exc),
                    "items": [],
                }
            )

        items = ReturnService.available_items(order)

        return Response(
            {
                "order": order.id,
                "order_reference": order.reference,
                "order_status": order.status,
                "can_return": bool(items),
                "reason": (
                    None
                    if items
                    else "Aucun article retournable."
                ),
                "items": items,
            }
        )


class RefundViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = RefundSerializer

    def get_permissions(self):
        if self.action == "create":
            return [HasPermission("refunds.create")()]

        if self.action in ["list", "retrieve"]:
            return [HasPermission("refunds.view")()]

        if self.action in ["approve", "process", "reject"]:
            return [HasPermission("refunds.update")()]

        return [HasPermission("refunds.view")()]

    def get_queryset(self):
        user = self.request.user

        queryset = (
            Refund.objects
            .select_related(
                "order",
                "return_request",
                "payment",
                "requested_by",
                "processed_by",
            )
        )

        if not user or not user.is_authenticated:
            return queryset.none()

        if not RefundService.is_manager(user):
            queryset = queryset.filter(order__user=user)

        refund_status = self.request.query_params.get("status")

        if refund_status:
            queryset = queryset.filter(
                status=refund_status.strip().upper()
            )

        order = self.request.query_params.get("order")

        if order:
            if order.isdigit():
                queryset = queryset.filter(order_id=int(order))
            else:
                queryset = queryset.filter(
                    order__reference=order
                )

        return_request = self.request.query_params.get(
            "return_request"
        )

        if return_request:
            if return_request.isdigit():
                queryset = queryset.filter(
                    return_request_id=int(return_request)
                )
            else:
                queryset = queryset.filter(
                    return_request__reference=return_request
                )

        search = self.request.query_params.get("search")

        if search:
            queryset = queryset.filter(
                Q(reference__icontains=search)
                | models.Q(reason__icontains=search)
                | models.Q(order__reference__icontains=search)
            )

        return queryset.order_by("-requested_at")

    def perform_create(self, serializer):
        refund = serializer.save()

        AuditService.log(
            action=AuditLog.Action.CREATE,
            actor=self.request.user,
            target=refund,
            metadata={
                "order_id": refund.order_id,
                "amount": str(refund.amount),
                "method": refund.method,
                "return_request_id": (
                    refund.return_request_id
                ),
            },
            request=self.request,
        )

    @action(
        detail=True,
        methods=["post"],
        url_path="approve",
    )
    def approve(self, request, pk=None):
        refund = self.get_object()

        if refund.status == Refund.Status.APPROVED:
            return Response(
                RefundSerializer(
                    refund,
                    context=self.get_serializer_context(),
                ).data
            )

        previous_status = refund.status

        try:
            RefundService.approve(
                refund=refund,
                actor=request.user,
            )
        except ValueError as exc:
            raise ValidationError({"detail": str(exc)})

        AuditService.log(
            action=AuditLog.Action.STATUS_CHANGE,
            actor=request.user,
            target=refund,
            changes={
                "status": {
                    "before": previous_status,
                    "after": refund.status,
                }
            },
            request=request,
        )

        return Response(
            RefundSerializer(
                refund,
                context=self.get_serializer_context(),
            ).data
        )

    @action(
        detail=True,
        methods=["post"],
        url_path="process",
    )
    def process(self, request, pk=None):
        refund = self.get_object()
        previous_status = refund.status

        try:
            RefundService.process(
                refund=refund,
                actor=request.user,
                external_reference=request.data.get(
                    "external_reference"
                ),
                notes=request.data.get("notes"),
            )
        except ValueError as exc:
            raise ValidationError({"detail": str(exc)})

        AuditService.log(
            action=AuditLog.Action.STATUS_CHANGE,
            actor=request.user,
            target=refund,
            changes={
                "status": {
                    "before": previous_status,
                    "after": refund.status,
                }
            },
            metadata={
                "external_reference": (
                    refund.external_reference
                ),
                "amount": str(refund.amount),
            },
            request=request,
        )

        return Response(
            RefundSerializer(
                refund,
                context=self.get_serializer_context(),
            ).data
        )

    @action(
        detail=True,
        methods=["post"],
        url_path="reject",
    )
    def reject(self, request, pk=None):
        refund = self.get_object()
        previous_status = refund.status
        note = request.data.get("notes")

        try:
            RefundService.reject(
                refund=refund,
                actor=request.user,
                note=note,
            )
        except ValueError as exc:
            raise ValidationError({"detail": str(exc)})

        AuditService.log(
            action=AuditLog.Action.STATUS_CHANGE,
            actor=request.user,
            target=refund,
            changes={
                "status": {
                    "before": previous_status,
                    "after": refund.status,
                }
            },
            metadata={"notes": note},
            request=request,
        )

        return Response(
            RefundSerializer(
                refund,
                context=self.get_serializer_context(),
            ).data
        )
