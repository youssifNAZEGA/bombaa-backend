import django_filters

from django.db.models import Exists, F, OuterRef, Q

from apps.geography.models import Country
from apps.stocks.models import Stock

from .models import (
    AttributeValue,
    Category,
    Product,
    ProductVariant,
)


def descendant_category_ids(category, visited=None):
    """
    Retourne l'identifiant de la catégorie et de toutes
    ses sous-catégories.
    """

    visited = visited or set()

    if category.id in visited:
        return []

    visited.add(category.id)

    ids = [category.id]

    for child in category.children.all():
        ids.extend(
            descendant_category_ids(child, visited)
        )

    return ids


class ProductFilter(django_filters.FilterSet):
    category = django_filters.NumberFilter(
        method="filter_category"
    )

    brand = django_filters.NumberFilter(
        field_name="brand_id"
    )

    price_min = django_filters.NumberFilter(
        field_name="base_price",
        lookup_expr="gte",
    )

    price_max = django_filters.NumberFilter(
        field_name="base_price",
        lookup_expr="lte",
    )

    in_stock = django_filters.BooleanFilter(
        method="filter_in_stock"
    )

    attributes = django_filters.CharFilter(
        method="filter_attributes"
    )

    country = django_filters.CharFilter(
        method="filter_country"
    )

    is_active = django_filters.BooleanFilter(
        field_name="is_active"
    )

    class Meta:
        model = Product
        fields = [
            "category",
            "brand",
            "price_min",
            "price_max",
            "in_stock",
            "attributes",
            "country",
            "is_active",
        ]

    def filter_category(self, queryset, name, value):
        try:
            category = Category.objects.get(pk=value)
        except Category.DoesNotExist:
            return queryset.none()

        return queryset.filter(
            product_categories__category_id__in=(
                descendant_category_ids(category)
            )
        ).distinct()

    def filter_in_stock(self, queryset, name, value):
        available_stock = Stock.objects.filter(
            variant__product=OuterRef("pk"),
            variant__is_active=True,
            quantity__gt=F("reserved_quantity"),
        )

        if value:
            return queryset.filter(
                Exists(available_stock)
            )

        return queryset.filter(
            ~Exists(available_stock)
        )

    def filter_country(self, queryset, name, value):
        value = str(value).strip()

        if not value:
            return queryset

        countries = Country.objects.filter(is_active=True)

        if value.isdigit():
            country = countries.filter(pk=int(value)).first()
        else:
            country = countries.filter(
                code__iexact=value
            ).first()

        if country is None:
            return queryset.none()

        return queryset.filter(
            Q(available_countries__isnull=True)
            | Q(available_countries=country)
        ).distinct()

    def filter_attributes(self, queryset, name, value):
        """
        Filtre par valeurs d'attributs.

        Deux formats acceptés :
        - identifiants : ?attributes=12,15
        - noms : ?attributes=Couleur:Rouge,Taille:M
        """

        raw_items = [
            item.strip()
            for item in value.split(",")
            if item.strip()
        ]

        value_ids = []

        for item in raw_items:
            if item.isdigit():
                value_ids.append(int(item))
                continue

            if ":" not in item:
                return queryset.none()

            attribute_name, attribute_value = item.split(":", 1)

            try:
                attribute_value_obj = AttributeValue.objects.get(
                    attribute__name__iexact=attribute_name.strip(),
                    value__iexact=attribute_value.strip(),
                )
            except (
                AttributeValue.DoesNotExist,
                AttributeValue.MultipleObjectsReturned,
            ):
                return queryset.none()

            value_ids.append(attribute_value_obj.id)

        if not value_ids:
            return queryset

        matching_variants = ProductVariant.objects.filter(
            product=OuterRef("pk"),
            is_active=True,
        )

        for value_id in value_ids:
            matching_variants = matching_variants.filter(
                variant_attribute_values__attribute_value_id=(
                    value_id
                )
            )

        return queryset.filter(
            Exists(matching_variants)
        )
