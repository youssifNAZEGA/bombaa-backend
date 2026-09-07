from rest_framework import serializers

from .models import Category


class CategorySerializer(serializers.ModelSerializer):

    children_count = serializers.SerializerMethodField()

    class Meta:
        model = Category

        fields = [
            "id",
            "name",
            "slug",
            "description",
            "parent",
            "is_active",
            "children_count",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "children_count",
            "created_at",
            "updated_at",
        ]

    def get_children_count(self, obj):
        return obj.children.count()

    def validate_name(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "Le nom de la catégorie est obligatoire."
            )

        return value
    
    def validate_parent(self, value):

        if value is None:
            return value

        if self.instance and value.id == self.instance.id:
            raise serializers.ValidationError(
                "Une catégorie ne peut pas être son propre parent."
            )

        return value