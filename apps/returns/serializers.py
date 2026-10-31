from decimal import Decimal

from rest_framework import serializers

from apps.orders.models import Order, OrderItem
from apps.payments.models import Payment

from .models import Refund, ReturnItem, ReturnRequest
from .services import RefundService, ReturnService


class ReturnItemSerializer(serializers.ModelSerializer):
    order_item = serializers.PrimaryKeyRelatedField(
        queryset=OrderItem.objects.all(),
    )

    class Meta:
        model = ReturnItem
        fields = [
            "id",
            "order_item",
            "product_name",
            "sku",
            "quantity",
            "unit_price",
            "subtotal",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "product_name",
            "sku",
            "unit_price",
            "subtotal",
            "created_at",
        ]

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError(
                "La quantité doit être supérieure à zéro."
            )

        return value


class ReturnRequestListSerializer(serializers.ModelSerializer):
    order_reference = serializers.CharField(
        source="order.reference",
        read_only=True,
    )
    user = serializers.IntegerField(
        source="order.user_id",
        read_only=True,
    )
    items_count = serializers.SerializerMethodField()

    class Meta:
        model = ReturnRequest
        fields = [
            "id",
            "reference",
            "order",
            "order_reference",
            "user",
            "status",
            "reason",
            "total_amount",
            "currency",
            "items_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_items_count(self, obj):
        return obj.items.count()


class ReturnRequestSerializer(serializers.ModelSerializer):
    order = serializers.PrimaryKeyRelatedField(
        queryset=Order.objects.all(),
    )
    order_reference = serializers.CharField(
        source="order.reference",
        read_only=True,
    )
    user = serializers.IntegerField(
        source="order.user_id",
        read_only=True,
    )
    user_name = serializers.SerializerMethodField()
    items = ReturnItemSerializer(many=True)
    processed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = ReturnRequest
        fields = [
            "id",
            "reference",
            "order",
            "order_reference",
            "user",
            "user_name",
            "status",
            "reason",
            "admin_note",
            "total_amount",
            "currency",
            "items",
            "processed_by",
            "processed_by_name",
            "approved_at",
            "received_at",
            "rejected_at",
            "cancelled_at",
            "refunded_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "reference",
            "user",
            "user_name",
            "status",
            "admin_note",
            "total_amount",
            "currency",
            "processed_by",
            "processed_by_name",
            "approved_at",
            "received_at",
            "rejected_at",
            "cancelled_at",
            "refunded_at",
            "created_at",
            "updated_at",
        ]

    def validate_reason(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "Le motif du retour est obligatoire."
            )

        return value

    def validate_items(self, value):
        if not value:
            raise serializers.ValidationError(
                "Sélectionnez au moins un article à retourner."
            )

        identifiers = [
            item["order_item"].id
            for item in value
        ]

        if len(identifiers) != len(set(identifiers)):
            raise serializers.ValidationError(
                "Un article ne peut apparaître qu'une seule fois."
            )

        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)

        request = self.context.get("request")
        user = getattr(request, "user", None)

        if user is None or not user.is_authenticated:
            raise serializers.ValidationError(
                "Vous devez être connecté pour demander un retour."
            )

        order = attrs.get("order")

        if (
            not ReturnService.is_manager(user)
            and order.user_id != user.id
        ):
            raise serializers.ValidationError(
                {
                    "order": (
                        "Cette commande ne vous appartient pas."
                    )
                }
            )

        try:
            ReturnService.validate_order(order)
        except ValueError as exc:
            raise serializers.ValidationError(
                {"order": str(exc)}
            )

        returned = ReturnService.active_quantities(order)
        items = attrs.get("items") or []

        for entry in items:
            order_item = entry["order_item"]
            quantity = entry["quantity"]

            if order_item.order_id != order.id:
                raise serializers.ValidationError(
                    {
                        "items": (
                            f"L'article {order_item.sku} "
                            "n'appartient pas à cette commande."
                        )
                    }
                )

            available = (
                order_item.quantity
                - returned.get(order_item.id, 0)
            )

            if quantity > available:
                raise serializers.ValidationError(
                    {
                        "items": (
                            f"La quantité disponible pour "
                            f"{order_item.sku} est {available}."
                        )
                    }
                )

        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        items = validated_data.pop("items")
        order = validated_data.pop("order")
        reason = validated_data.pop("reason")

        try:
            return ReturnService.create_return(
                order=order,
                items=items,
                reason=reason,
                actor=request.user,
            )
        except ValueError as exc:
            raise serializers.ValidationError(
                {"detail": str(exc)}
            )

    def get_user_name(self, obj):
        user = obj.order.user

        if user is None:
            return None

        name = (
            f"{user.first_name} {user.last_name}"
        ).strip()

        return name or user.email

    def get_processed_by_name(self, obj):
        if obj.processed_by is None:
            return None

        name = (
            f"{obj.processed_by.first_name} "
            f"{obj.processed_by.last_name}"
        ).strip()

        return name or obj.processed_by.email


class RefundSerializer(serializers.ModelSerializer):
    order = serializers.PrimaryKeyRelatedField(
        queryset=Order.objects.all(),
    )
    order_reference = serializers.CharField(
        source="order.reference",
        read_only=True,
    )
    return_request = serializers.PrimaryKeyRelatedField(
        queryset=ReturnRequest.objects.all(),
        required=False,
        allow_null=True,
    )
    return_reference = serializers.CharField(
        source="return_request.reference",
        read_only=True,
    )
    payment = serializers.PrimaryKeyRelatedField(
        queryset=Payment.objects.all(),
        required=False,
        allow_null=True,
    )
    payment_reference = serializers.CharField(
        source="payment.reference",
        read_only=True,
    )
    amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal("0.01"),
        required=False,
        allow_null=True,
    )
    requested_by_name = serializers.SerializerMethodField()
    processed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Refund
        fields = [
            "id",
            "reference",
            "order",
            "order_reference",
            "return_request",
            "return_reference",
            "payment",
            "payment_reference",
            "amount",
            "currency",
            "reason",
            "method",
            "status",
            "external_reference",
            "notes",
            "requested_by",
            "requested_by_name",
            "processed_by",
            "processed_by_name",
            "approved_at",
            "processed_at",
            "rejected_at",
            "requested_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "reference",
            "currency",
            "status",
            "requested_by",
            "requested_by_name",
            "processed_by",
            "processed_by_name",
            "approved_at",
            "processed_at",
            "rejected_at",
            "requested_at",
            "updated_at",
        ]

    def validate_reason(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "Le motif du remboursement est obligatoire."
            )

        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)

        order = attrs.get("order")
        return_request = attrs.get("return_request")
        payment = attrs.get("payment")
        amount = attrs.get("amount")

        if order.status == Order.Status.CANCELLED:
            raise serializers.ValidationError(
                {
                    "order": (
                        "Impossible de rembourser une commande "
                        "annulée."
                    )
                }
            )

        if return_request is not None:
            if return_request.order_id != order.id:
                raise serializers.ValidationError(
                    {
                        "return_request": (
                            "Cette demande de retour ne "
                            "correspond pas à la commande."
                        )
                    }
                )

            if (
                return_request.status
                != ReturnRequest.Status.RECEIVED
            ):
                raise serializers.ValidationError(
                    {
                        "return_request": (
                            "Le retour doit être réceptionné "
                            "avant tout remboursement."
                        )
                    }
                )

            available = RefundService.available_return_amount(
                return_request
            )
        else:
            available = RefundService.available_order_amount(
                order
            )

        if amount is None:
            amount = available

        if amount <= 0:
            raise serializers.ValidationError(
                {
                    "amount": (
                        "Aucun montant remboursable n'est "
                        "disponible."
                    )
                }
            )

        if amount > available:
            raise serializers.ValidationError(
                {
                    "amount": (
                        f"Le montant maximum remboursable est "
                        f"{available}."
                    )
                }
            )

        if payment is not None:
            if payment.order_id != order.id:
                raise serializers.ValidationError(
                    {
                        "payment": (
                            "Ce paiement ne correspond pas à "
                            "la commande."
                        )
                    }
                )

            if payment.status != Payment.Status.SUCCESS:
                raise serializers.ValidationError(
                    {
                        "payment": (
                            "Seul un paiement réussi peut être "
                            "remboursé."
                        )
                    }
                )

        attrs["amount"] = amount

        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        order = validated_data.pop("order")

        try:
            return RefundService.create_refund(
                order=order,
                actor=request.user,
                reason=validated_data.pop("reason"),
                method=validated_data.pop(
                    "method",
                    Refund.Method.ORIGINAL_PAYMENT,
                ),
                amount=validated_data.pop("amount", None),
                payment=validated_data.pop("payment", None),
                return_request=validated_data.pop(
                    "return_request",
                    None,
                ),
                notes=validated_data.pop("notes", None),
                external_reference=validated_data.pop(
                    "external_reference",
                    None,
                ),
            )
        except ValueError as exc:
            raise serializers.ValidationError(
                {"detail": str(exc)}
            )

    def get_requested_by_name(self, obj):
        if obj.requested_by is None:
            return None

        name = (
            f"{obj.requested_by.first_name} "
            f"{obj.requested_by.last_name}"
        ).strip()

        return name or obj.requested_by.email

    def get_processed_by_name(self, obj):
        if obj.processed_by is None:
            return None

        name = (
            f"{obj.processed_by.first_name} "
            f"{obj.processed_by.last_name}"
        ).strip()

        return name or obj.processed_by.email
