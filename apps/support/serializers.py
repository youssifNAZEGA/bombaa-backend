from rest_framework import serializers

from apps.orders.models import Order

from .models import (
    FaqEntry,
    SupportEvent,
    SupportMessage,
    SupportTicket,
)
from .services import SupportService


class FaqEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = FaqEntry
        fields = [
            "id",
            "question",
            "answer",
            "category",
            "display_order",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
        ]

    def validate_question(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "La question est obligatoire."
            )

        return value

    def validate_answer(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "La réponse est obligatoire."
            )

        return value


class SupportMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupportMessage
        fields = [
            "id",
            "author",
            "author_name",
            "body",
            "is_internal",
            "created_at",
        ]
        read_only_fields = fields


class SupportMessageCreateSerializer(serializers.Serializer):
    body = serializers.CharField()
    is_internal = serializers.BooleanField(
        required=False,
        default=False,
    )

    def validate_body(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "Le message ne peut pas être vide."
            )

        return value


class SupportEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupportEvent
        fields = [
            "id",
            "action",
            "actor_name",
            "previous_status",
            "new_status",
            "note",
            "created_at",
        ]
        read_only_fields = fields


class SupportTicketListSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()
    order_reference = serializers.CharField(
        source="order.reference",
        read_only=True,
    )
    assigned_to_name = serializers.SerializerMethodField()
    messages_count = serializers.IntegerField(
        read_only=True,
    )

    class Meta:
        model = SupportTicket
        fields = [
            "id",
            "reference",
            "type",
            "status",
            "priority",
            "subject",
            "user",
            "user_name",
            "order",
            "order_reference",
            "assigned_to",
            "assigned_to_name",
            "messages_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_user_name(self, obj):
        if obj.user is None:
            return obj.contact_name

        name = (
            f"{obj.user.first_name} {obj.user.last_name}"
        ).strip()

        return name or obj.user.email

    def get_assigned_to_name(self, obj):
        if obj.assigned_to is None:
            return None

        name = (
            f"{obj.assigned_to.first_name} "
            f"{obj.assigned_to.last_name}"
        ).strip()

        return name or obj.assigned_to.email


class SupportTicketDetailSerializer(serializers.ModelSerializer):
    user = serializers.PrimaryKeyRelatedField(
        read_only=True,
    )
    user_name = serializers.SerializerMethodField()
    contact_name = serializers.CharField(
        required=False,
        allow_blank=True,
    )
    contact_email = serializers.EmailField(
        required=False,
        allow_blank=True,
    )
    contact_phone = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    order = serializers.PrimaryKeyRelatedField(
        queryset=Order.objects.all(),
        required=False,
        allow_null=True,
    )
    order_reference = serializers.CharField(
        source="order.reference",
        read_only=True,
    )
    assigned_to = serializers.PrimaryKeyRelatedField(
        read_only=True,
    )
    assigned_to_name = serializers.SerializerMethodField()
    messages = serializers.SerializerMethodField()
    events = serializers.SerializerMethodField()

    class Meta:
        model = SupportTicket
        fields = [
            "id",
            "reference",
            "type",
            "status",
            "priority",
            "subject",
            "description",
            "user",
            "user_name",
            "order",
            "order_reference",
            "contact_name",
            "contact_email",
            "contact_phone",
            "assigned_to",
            "assigned_to_name",
            "resolution",
            "resolved_at",
            "closed_at",
            "messages",
            "events",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "reference",
            "status",
            "user",
            "user_name",
            "order_reference",
            "assigned_to",
            "assigned_to_name",
            "resolution",
            "resolved_at",
            "closed_at",
            "messages",
            "events",
            "created_at",
            "updated_at",
        ]

    def validate_subject(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "Le sujet est obligatoire."
            )

        return value

    def validate_description(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "La description est obligatoire."
            )

        return value

    def validate_contact_name(self, value):
        return (value or "").strip()

    def validate_contact_email(self, value):
        return (value or "").strip()

    def validate_contact_phone(self, value):
        return (value or "").strip()

    def validate(self, attrs):
        attrs = super().validate(attrs)

        request = self.context.get("request")
        user = getattr(request, "user", None)
        is_authenticated = bool(
            user is not None and user.is_authenticated
        )
        is_agent = (
            SupportService.is_agent(user)
            if is_authenticated
            else False
        )

        if self.instance is not None:
            if not is_agent:
                raise serializers.ValidationError(
                    "Seul le service client peut modifier "
                    "ce ticket."
                )

            if (
                "contact_name" in attrs
                and not attrs["contact_name"]
            ):
                raise serializers.ValidationError(
                    {
                        "contact_name": (
                            "Le nom de contact est obligatoire."
                        )
                    }
                )

            if (
                "contact_email" in attrs
                and not attrs["contact_email"]
            ):
                raise serializers.ValidationError(
                    {
                        "contact_email": (
                            "L'adresse email de contact est "
                            "obligatoire."
                        )
                    }
                )

            return attrs

        order = attrs.get("order")
        ticket_type = attrs.get(
            "type",
            SupportTicket.Type.QUESTION,
        )

        if not is_authenticated:
            if ticket_type in [
                SupportTicket.Type.RETURN,
                SupportTicket.Type.REFUND,
            ]:
                raise serializers.ValidationError(
                    {
                        "type": (
                            "Connectez-vous pour créer une "
                            "demande de retour ou de "
                            "remboursement."
                        )
                    }
                )

            if order is not None:
                raise serializers.ValidationError(
                    {
                        "order": (
                            "Connectez-vous pour rattacher "
                            "une commande à votre demande."
                        )
                    }
                )

            missing = {}

            if not attrs.get("contact_name"):
                missing["contact_name"] = (
                    "Le nom est obligatoire."
                )

            if not attrs.get("contact_email"):
                missing["contact_email"] = (
                    "L'adresse email est obligatoire."
                )

            if missing:
                raise serializers.ValidationError(missing)

            attrs["priority"] = (
                SupportTicket.Priority.NORMAL
            )

            return attrs

        if (
            order is not None
            and not is_agent
            and order.user_id != user.id
        ):
            raise serializers.ValidationError(
                {
                    "order": (
                        "Cette commande ne vous appartient pas."
                    )
                }
            )

        name, email = SupportService.contact_snapshot(user)
        attrs["contact_name"] = (
            attrs.get("contact_name") or name
        )
        attrs["contact_email"] = (
            attrs.get("contact_email") or email
        )
        attrs["contact_phone"] = (
            attrs.get("contact_phone") or user.phone
        )

        if not is_agent:
            attrs["priority"] = (
                SupportTicket.Priority.NORMAL
            )

        return attrs

    def create(self, validated_data):
        request = self.context["request"]
        user = getattr(request, "user", None)

        if user is None or not user.is_authenticated:
            user = None

        ticket = SupportTicket.objects.create(
            user=user,
            **validated_data,
        )

        SupportEvent.objects.create(
            ticket=ticket,
            action=SupportEvent.Action.CREATED,
            actor=user,
            actor_name=ticket.contact_name,
            new_status=ticket.status,
            note="Ticket créé",
        )

        return ticket

    def get_user_name(self, obj):
        if obj.user is None:
            return obj.contact_name

        name = (
            f"{obj.user.first_name} {obj.user.last_name}"
        ).strip()

        return name or obj.user.email

    def get_assigned_to_name(self, obj):
        if obj.assigned_to is None:
            return None

        name = (
            f"{obj.assigned_to.first_name} "
            f"{obj.assigned_to.last_name}"
        ).strip()

        return name or obj.assigned_to.email

    def get_messages(self, obj):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        include_internal = SupportService.is_agent(user)

        messages = SupportService.visible_messages(
            obj,
            include_internal=include_internal,
        )

        return SupportMessageSerializer(
            messages,
            many=True,
        ).data

    def get_events(self, obj):
        events = obj.events.select_related("actor")

        return SupportEventSerializer(
            events,
            many=True,
        ).data
