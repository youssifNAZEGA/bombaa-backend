from collections import defaultdict
from decimal import Decimal

from django.db.models import Count, F, Max, Q, Sum
from django.db.models.functions import (
    Coalesce,
    TruncDate,
    TruncMonth,
    TruncWeek,
    TruncYear,
)

from apps.accounts.models import User
from apps.catalog.models import Category, Product
from apps.geography.models import Country
from apps.orders.models import Order, OrderItem
from apps.payments.models import Payment
from apps.stocks.models import Stock


ZERO = Decimal("0.00")

SALE_ORDER_STATUSES = [
    Order.Status.CONFIRMED,
    Order.Status.PROCESSING,
    Order.Status.SHIPPED,
    Order.Status.DELIVERED,
    Order.Status.COMPLETED,
]

PERIOD_GROUPING = {
    "day": TruncDate,
    "week": TruncWeek,
    "month": TruncMonth,
    "year": TruncYear,
}


class DashboardService:
    """
    Calcule les indicateurs du tableau de bord administrateur.

    Les revenus proviennent uniquement des paiements réussis.
    Les indicateurs multi-devises sont toujours regroupés par devise
    afin de ne jamais additionner des montants de devises différentes.
    """

    def __init__(
        self,
        *,
        date_from=None,
        date_to=None,
        country=None,
        group_by="month",
    ):
        self.date_from = date_from
        self.date_to = date_to
        self.country = country
        self.group_by = group_by

    @staticmethod
    def resolve_country(value):
        if value is None:
            return None

        value = str(value).strip()

        if not value:
            return None

        queryset = Country.objects.all()

        if value.isdigit():
            country = queryset.filter(pk=int(value)).first()
        else:
            country = queryset.filter(
                Q(code__iexact=value)
                | Q(name__iexact=value)
            ).first()

        if country is None:
            raise ValueError("Pays introuvable.")

        return country

    @staticmethod
    def _money(value):
        if value is None:
            value = ZERO

        return str(
            Decimal(value).quantize(Decimal("0.01"))
        )

    @staticmethod
    def _period_value(value):
        if value is None:
            return None

        if hasattr(value, "date"):
            value = value.date()

        return value.isoformat()

    def _apply_country_filter(self, queryset, prefix):
        if self.country is None:
            return queryset

        return queryset.filter(
            Q(**{
                f"{prefix}__country_code__iexact": (
                    self.country.code
                )
            })
            | Q(**{
                f"{prefix}__country_name__iexact": (
                    self.country.name
                )
            })
        )

    def _apply_order_dates(self, queryset):
        if self.date_from is not None:
            queryset = queryset.filter(
                created_at__date__gte=self.date_from
            )

        if self.date_to is not None:
            queryset = queryset.filter(
                created_at__date__lte=self.date_to
            )

        return queryset

    def _apply_sale_dates(self, queryset):
        if self.date_from is not None:
            queryset = queryset.filter(
                sale_date__date__gte=self.date_from
            )

        if self.date_to is not None:
            queryset = queryset.filter(
                sale_date__date__lte=self.date_to
            )

        return queryset

    def _apply_created_dates(self, queryset):
        if self.date_from is not None:
            queryset = queryset.filter(
                created_at__date__gte=self.date_from
            )

        if self.date_to is not None:
            queryset = queryset.filter(
                created_at__date__lte=self.date_to
            )

        return queryset

    def orders_queryset(self):
        queryset = Order.objects.all()
        queryset = self._apply_order_dates(queryset)
        queryset = self._apply_country_filter(
            queryset,
            "shipping_address",
        )

        return queryset

    def successful_payments(self):
        queryset = (
            Payment.objects
            .filter(status=Payment.Status.SUCCESS)
            .annotate(
                sale_date=Coalesce(
                    "paid_at",
                    "created_at",
                )
            )
        )

        queryset = self._apply_sale_dates(queryset)
        queryset = self._apply_country_filter(
            queryset,
            "order__shipping_address",
        )

        return queryset

    def payments_queryset(self):
        queryset = Payment.objects.all()
        queryset = self._apply_created_dates(queryset)
        queryset = self._apply_country_filter(
            queryset,
            "order__shipping_address",
        )

        return queryset

    def _sold_items(self):
        queryset = OrderItem.objects.filter(
            order__status__in=SALE_ORDER_STATUSES,
        )

        if self.date_from is not None:
            queryset = queryset.filter(
                order__created_at__date__gte=self.date_from
            )

        if self.date_to is not None:
            queryset = queryset.filter(
                order__created_at__date__lte=self.date_to
            )

        queryset = self._apply_country_filter(
            queryset,
            "order__shipping_address",
        )

        return queryset

    def _revenue_by_currency(self, payments):
        rows = (
            payments
            .values("currency")
            .annotate(amount=Sum("amount"))
            .order_by("currency")
        )

        return [
            {
                "currency": row["currency"],
                "amount": self._money(row["amount"]),
            }
            for row in rows
        ]

    def orders_stats(self):
        orders = self.orders_queryset()

        status_rows = (
            orders
            .values("status")
            .annotate(count=Count("id"))
            .order_by("status")
        )

        by_status = {
            status_value: 0
            for status_value, _label in Order.Status.choices
        }

        for row in status_rows:
            by_status[row["status"]] = row["count"]

        average_rows = (
            orders
            .exclude(status=Order.Status.CANCELLED)
            .values("currency")
            .annotate(
                total=Sum("total_amount"),
                order_count=Count("id"),
            )
            .order_by("currency")
        )

        average_order_value = []

        for row in average_rows:
            order_count = row["order_count"] or 0

            average = (
                (row["total"] or ZERO) / order_count
                if order_count
                else ZERO
            )

            average_order_value.append({
                "currency": row["currency"],
                "amount": self._money(average),
                "order_count": order_count,
            })

        return {
            "total_orders": orders.count(),
            "by_status": by_status,
            "pending_orders": by_status.get(
                Order.Status.PENDING,
                0,
            ),
            "cancelled_orders": by_status.get(
                Order.Status.CANCELLED,
                0,
            ),
            "average_order_value": average_order_value,
        }

    def customers_stats(self, limit=10):
        all_customers = User.objects.filter(
            is_staff=False,
            is_superuser=False,
        )

        new_customers = self._apply_created_dates(
            all_customers
        ).count()

        orders = (
            self.orders_queryset()
            .exclude(status=Order.Status.CANCELLED)
        )

        active_customers = (
            orders
            .values("user_id")
            .distinct()
            .count()
        )

        returning_customers = (
            orders
            .values("user_id")
            .annotate(order_count=Count("id"))
            .filter(order_count__gte=2)
            .count()
        )

        top_rows = list(
            orders
            .values(
                "user_id",
                "user__email",
                "user__first_name",
                "user__last_name",
            )
            .annotate(order_count=Count("id"))
            .order_by("-order_count", "user__email")[:limit]
        )

        spending_rows = (
            orders
            .values("user_id", "currency")
            .annotate(amount=Sum("total_amount"))
        )

        spending = defaultdict(list)

        for row in spending_rows:
            spending[row["user_id"]].append({
                "currency": row["currency"],
                "amount": self._money(row["amount"]),
            })

        for row in top_rows:
            row["total_spent_by_currency"] = spending[
                row["user_id"]
            ]

        return {
            "total_customers": all_customers.count(),
            "new_customers": new_customers,
            "active_customers": active_customers,
            "returning_customers": returning_customers,
            "top_customers": [
                {
                    "user_id": row["user_id"],
                    "email": row["user__email"],
                    "first_name": row["user__first_name"],
                    "last_name": row["user__last_name"],
                    "order_count": row["order_count"],
                    "total_spent_by_currency": (
                        row["total_spent_by_currency"]
                    ),
                }
                for row in top_rows
            ],
        }

    def products_stats(self):
        active_products = Product.objects.filter(
            is_active=True
        )

        available_product_ids = (
            Stock.objects
            .filter(
                variant__is_active=True,
                variant__product__is_active=True,
                quantity__gt=F("reserved_quantity"),
            )
            .values_list(
                "variant__product_id",
                flat=True,
            )
            .distinct()
        )

        available_products = active_products.filter(
            pk__in=available_product_ids
        ).count()

        return {
            "total_products": Product.objects.count(),
            "active_products": active_products.count(),
            "available_products": available_products,
            "out_of_stock_products": (
                active_products.count()
                - available_products
            ),
        }

    def _product_sales(self):
        items = self._sold_items()

        quantity_rows = (
            items
            .values("variant__product_id")
            .annotate(
                quantity_sold=Sum("quantity"),
                order_count=Count("order", distinct=True),
                product_name=Max("product_name"),
            )
            .order_by("-quantity_sold", "product_name")
        )

        revenue_rows = (
            items
            .values(
                "variant__product_id",
                "order__currency",
            )
            .annotate(amount=Sum("subtotal"))
        )

        revenue = defaultdict(list)

        for row in revenue_rows:
            revenue[row["variant__product_id"]].append({
                "currency": row["order__currency"],
                "amount": self._money(row["amount"]),
            })

        stats = {}

        for row in quantity_rows:
            product_id = row["variant__product_id"]

            stats[product_id] = {
                "product_id": product_id,
                "product_name": row["product_name"],
                "quantity_sold": row["quantity_sold"],
                "order_count": row["order_count"],
                "revenue_by_currency": revenue.get(
                    product_id,
                    [],
                ),
            }

        return stats

    def best_sellers(self, limit=10):
        return list(self._product_sales().values())[:limit]

    def worst_sellers(self, limit=10):
        sold_products = self._product_sales()

        records = []

        for product in Product.objects.filter(
            is_active=True
        ).values("id", "name"):
            stat = sold_products.get(
                product["id"],
                {
                    "product_id": product["id"],
                    "product_name": product["name"],
                    "quantity_sold": 0,
                    "order_count": 0,
                    "revenue_by_currency": [],
                },
            )

            records.append(stat)

        records.sort(
            key=lambda item: (
                item["quantity_sold"],
                item["product_name"].lower(),
            )
        )

        return records[:limit]

    def sales_by_period(self):
        trunc_function = PERIOD_GROUPING.get(
            self.group_by,
            TruncMonth,
        )

        rows = (
            self.successful_payments()
            .annotate(period=trunc_function("sale_date"))
            .values("period", "currency")
            .annotate(
                amount=Sum("amount"),
                payment_count=Count("id"),
            )
            .order_by("period", "currency")
        )

        periods = {}

        for row in rows:
            period_key = self._period_value(row["period"])

            item = periods.setdefault(
                period_key,
                {
                    "period": period_key,
                    "payment_count": 0,
                    "revenue_by_currency": [],
                },
            )

            item["payment_count"] += row["payment_count"]
            item["revenue_by_currency"].append({
                "currency": row["currency"],
                "amount": self._money(row["amount"]),
            })

        return [
            periods[key]
            for key in sorted(periods.keys())
        ]

    def sales_by_country(self):
        rows = (
            self.successful_payments()
            .values(
                "order__shipping_address__country_code",
                "order__shipping_address__country_name",
                "currency",
            )
            .annotate(
                amount=Sum("amount"),
                payment_count=Count("id"),
            )
            .order_by(
                "order__shipping_address__country_name",
                "currency",
            )
        )

        countries = {}

        for row in rows:
            country_code = (
                row["order__shipping_address__country_code"]
                or ""
            )
            country_name = (
                row["order__shipping_address__country_name"]
                or "Inconnu"
            )
            key = (country_code, country_name)

            item = countries.setdefault(
                key,
                {
                    "country_code": country_code,
                    "country_name": country_name,
                    "payment_count": 0,
                    "revenue_by_currency": [],
                },
            )

            item["payment_count"] += row["payment_count"]
            item["revenue_by_currency"].append({
                "currency": row["currency"],
                "amount": self._money(row["amount"]),
            })

        return sorted(
            countries.values(),
            key=lambda item: (
                item["country_name"].lower(),
                item["country_code"],
            ),
        )

    def sales_by_category(self):
        items = (
            self._sold_items()
            .filter(
                variant__product__product_categories__isnull=False
            )
        )

        quantity_rows = (
            items
            .values(
                "variant__product__product_categories"
                "__category_id",
                "variant__product__product_categories"
                "__category__name",
            )
            .annotate(quantity_sold=Sum("quantity"))
            .order_by("-quantity_sold")
        )

        revenue_rows = (
            items
            .values(
                "variant__product__product_categories"
                "__category_id",
                "order__currency",
            )
            .annotate(amount=Sum("subtotal"))
        )

        revenue = defaultdict(list)

        for row in revenue_rows:
            category_id = row[
                "variant__product__product_categories__category_id"
            ]

            revenue[category_id].append({
                "currency": row["order__currency"],
                "amount": self._money(row["amount"]),
            })

        categories = {}

        for row in quantity_rows:
            category_id = row[
                "variant__product__product_categories__category_id"
            ]

            categories[category_id] = {
                "category_id": category_id,
                "category_name": row[
                    "variant__product__product_categories"
                    "__category__name"
                ],
                "quantity_sold": row["quantity_sold"],
                "revenue_by_currency": revenue.get(
                    category_id,
                    [],
                ),
            }

        for category in Category.objects.filter(
            is_active=True
        ).values("id", "name"):
            categories.setdefault(
                category["id"],
                {
                    "category_id": category["id"],
                    "category_name": category["name"],
                    "quantity_sold": 0,
                    "revenue_by_currency": [],
                },
            )

        return sorted(
            categories.values(),
            key=lambda item: (
                -item["quantity_sold"],
                item["category_name"].lower(),
            ),
        )

    def recent_orders(self, limit=5):
        orders = (
            self.orders_queryset()
            .select_related(
                "user",
                "shipping_address",
            )
            .order_by("-created_at")[:limit]
        )

        return [
            {
                "id": order.id,
                "reference": order.reference,
                "status": order.status,
                "total_amount": self._money(
                    order.total_amount
                ),
                "currency": order.currency,
                "created_at": order.created_at,
                "customer": {
                    "id": order.user_id,
                    "email": order.user.email,
                    "first_name": order.user.first_name,
                    "last_name": order.user.last_name,
                },
            }
            for order in orders
        ]

    def recent_payments(self, limit=5):
        payments = (
            self.payments_queryset()
            .select_related(
                "order",
                "order__user",
                "payment_method",
            )
            .order_by("-created_at")[:limit]
        )

        return [
            {
                "id": payment.id,
                "reference": payment.reference,
                "status": payment.status,
                "amount": self._money(payment.amount),
                "currency": payment.currency,
                "payment_method": payment.payment_method.name,
                "order_reference": payment.order.reference,
                "customer_email": payment.order.user.email,
                "created_at": payment.created_at,
            }
            for payment in payments
        ]

    def filters(self):
        return {
            "date_from": (
                self.date_from.isoformat()
                if self.date_from is not None
                else None
            ),
            "date_to": (
                self.date_to.isoformat()
                if self.date_to is not None
                else None
            ),
            "country": (
                {
                    "id": self.country.id,
                    "code": self.country.code,
                    "name": self.country.name,
                }
                if self.country is not None
                else None
            ),
            "group_by": self.group_by,
        }

    def overview(self, limit=10):
        payments = self.successful_payments()

        return {
            "filters": self.filters(),
            "revenue": {
                "by_currency": self._revenue_by_currency(
                    payments
                ),
            },
            "orders": self.orders_stats(),
            "customers": self.customers_stats(limit=limit),
            "products": self.products_stats(),
            "recent_orders": self.recent_orders(),
            "recent_payments": self.recent_payments(),
            "best_sellers": self.best_sellers(limit=limit),
            "worst_sellers": self.worst_sellers(limit=limit),
            "sales_by_period": self.sales_by_period(),
            "sales_by_country": self.sales_by_country(),
            "sales_by_category": self.sales_by_category(),
        }

    def sales(self, limit=10):
        return {
            "filters": self.filters(),
            "revenue_by_currency": self._revenue_by_currency(
                self.successful_payments()
            ),
            "by_period": self.sales_by_period(),
            "by_country": self.sales_by_country(),
            "by_category": self.sales_by_category(),
            "best_sellers": self.best_sellers(limit=limit),
            "worst_sellers": self.worst_sellers(limit=limit),
        }

    def products(self, limit=10):
        return {
            "filters": self.filters(),
            "summary": self.products_stats(),
            "best_sellers": self.best_sellers(limit=limit),
            "worst_sellers": self.worst_sellers(limit=limit),
        }

    def customers(self, limit=10):
        return {
            "filters": self.filters(),
            "summary": self.customers_stats(limit=limit),
        }

    def orders(self, limit=5):
        return {
            "filters": self.filters(),
            "summary": self.orders_stats(),
            "recent_orders": self.recent_orders(limit=limit),
        }
