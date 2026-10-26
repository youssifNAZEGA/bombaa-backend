from rest_framework import serializers

from apps.catalog.models import Product

from .models import Review, ReviewImage
from .services import ReviewService


class ReviewImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReviewImage
        fields = [
            "id",
            "image_url",
            "alt_text",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
        ]


class ReviewSerializer(serializers.ModelSerializer):
    product = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.filter(is_active=True),
    )

    product_name = serializers.CharField(
        source="product.name",
        read_only=True,
    )

    product_slug = serializers.CharField(
        source="product.slug",
        read_only=True,
    )

    user = serializers.PrimaryKeyRelatedField(
        read_only=True,
    )

    user_name = serializers.SerializerMethodField()

    rating = serializers.IntegerField(
        min_value=1,
        max_value=5,
    )

    comment = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
    )

    images = ReviewImageSerializer(
        many=True,
        required=False,
    )

    moderated_by_name = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields = [
            "id",
            "product",
            "product_name",
            "product_slug",
            "user",
            "user_name",
            "rating",
            "comment",
            "images",
            "status",
            "is_verified_purchase",
            "moderated_by",
            "moderated_by_name",
            "moderated_at",
            "moderation_note",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "user",
            "status",
            "is_verified_purchase",
            "moderated_by",
            "moderated_by_name",
            "moderated_at",
            "moderation_note",
            "created_at",
            "updated_at",
        ]

    def validate_product(self, value):
        if (
            self.instance is not None
            and value != self.instance.product
        ):
            raise serializers.ValidationError(
                "Le produit d'un avis ne peut pas être modifié."
            )

        return value

    def validate_comment(self, value):
        if value is None:
            return value

        return value.strip()

    def validate_images(self, value):
        if len(value) > 10:
            raise serializers.ValidationError(
                "Un avis ne peut pas contenir plus de 10 photos."
            )

        return value

    def validate(self, attrs):
        attrs = super().validate(attrs)

        if self.instance is not None:
            return attrs

        request = self.context.get("request")
        user = getattr(request, "user", None)
        product = attrs.get("product")

        if user is None or not user.is_authenticated:
            raise serializers.ValidationError(
                "Vous devez être connecté pour laisser un avis."
            )

        if not ReviewService.has_purchased(user, product):
            raise serializers.ValidationError(
                {
                    "product": (
                        "Vous pouvez laisser un avis uniquement "
                        "après avoir acheté ce produit."
                    )
                }
            )

        if Review.objects.filter(
            user=user,
            product=product,
        ).exists():
            raise serializers.ValidationError(
                {
                    "product": (
                        "Vous avez déjà laissé un avis "
                        "pour ce produit."
                    )
                }
            )

        return attrs

    def create(self, validated_data):
        images = validated_data.pop("images", [])
        request = self.context["request"]
        user = request.user
        product = validated_data["product"]
        order_item = ReviewService.purchase_order_item(
            user,
            product,
        )

        review = Review.objects.create(
            user=user,
            order_item=order_item,
            is_verified_purchase=order_item is not None,
            **validated_data,
        )

        self._create_images(review, images)

        return review

    def update(self, instance, validated_data):
        images = validated_data.pop("images", None)

        review = super().update(
            instance,
            validated_data,
        )

        if images is not None:
            review.images.all().delete()
            self._create_images(review, images)

        return review

    @staticmethod
    def _create_images(review, images):
        ReviewImage.objects.bulk_create([
            ReviewImage(
                review=review,
                image_url=image["image_url"],
                alt_text=image.get("alt_text"),
            )
            for image in images
        ])

    def get_user_name(self, obj):
        name = (
            f"{obj.user.first_name} {obj.user.last_name}"
        ).strip()

        return name or obj.user.email

    def get_moderated_by_name(self, obj):
        if obj.moderated_by is None:
            return None

        name = (
            f"{obj.moderated_by.first_name} "
            f"{obj.moderated_by.last_name}"
        ).strip()

        return name or obj.moderated_by.email
