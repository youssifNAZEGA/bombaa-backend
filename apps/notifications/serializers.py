from rest_framework import serializers

from apps.accounts.models import User
from apps.catalog.models import Product
from apps.orders.models import Order

from .models import Notification, NotificationPreference


class NotificationSerializer(serializers.ModelSerializer):

    event_label = serializers.CharField(
        source="get_event_display",
        read_only=True,
    )

    channel_label = serializers.CharField(
        source="get_channel_display",
        read_only=True,
    )

    order_reference = serializers.CharField(
        source="order.reference",
        read_only=True,
        allow_null=True,
    )

    product_name = serializers.CharField(
        source="product.name",
        read_only=True,
        allow_null=True,
    )

    class Meta:
        model = Notification

        fields = [
            "id",
            "event",
            "event_label",
            "channel",
            "channel_label",
            "title",
            "message",
            "order",
            "order_reference",
            "product",
            "product_name",
            "data",
            "is_read",
            "read_at",
            "created_at",
        ]

        read_only_fields = fields


class NotificationPreferenceSerializer(serializers.ModelSerializer):

    class Meta:
        model = NotificationPreference

        fields = [
            "in_app_enabled",
            "email_enabled",
            "sms_enabled",
            "push_enabled",
            "updated_at",
        ]

        read_only_fields = [
            "updated_at",
        ]


class NotificationCreateSerializer(serializers.ModelSerializer):

    user = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(is_active=True),
    )

    order = serializers.PrimaryKeyRelatedField(
        queryset=Order.objects.all(),
        required=False,
        allow_null=True,
    )

    product = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.all(),
        required=False,
        allow_null=True,
    )

    class Meta:
        model = Notification

        fields = [
            "user",
            "event",
            "title",
            "message",
            "order",
            "product",
            "data",
        ]

    def validate_title(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "Le titre de la notification est obligatoire."
            )

        return value

    def validate_message(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "Le message de la notification est obligatoire."
            )

        return value


class NotificationBroadcastSerializer(serializers.Serializer):

    event = serializers.ChoiceField(
        choices=Notification.Event.choices,
    )

    title = serializers.CharField(
        max_length=255,
    )

    message = serializers.CharField()

    users = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(
            is_active=True,
            is_staff=False,
            is_superuser=False,
        ),
        many=True,
        required=False,
    )

    product = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.filter(is_active=True),
        required=False,
        allow_null=True,
    )

    data = serializers.JSONField(
        required=False,
        default=dict,
    )

    def validate_title(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "Le titre de la notification est obligatoire."
            )

        return value

    def validate_message(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "Le message de la notification est obligatoire."
            )

        return value
