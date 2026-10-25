from datetime import date

from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import HasPermission

from .services import DashboardService


class DashboardViewBase(APIView):

    permission_classes = [
        HasPermission("dashboard.view")
    ]

    @staticmethod
    def parse_date(value, field_name):
        if value in [None, ""]:
            return None

        try:
            return date.fromisoformat(str(value))

        except (TypeError, ValueError):
            raise ValidationError({
                field_name: (
                    "Format de date invalide. "
                    "Utilisez YYYY-MM-DD."
                )
            })

    @staticmethod
    def parse_limit(value, default=10):
        if value in [None, ""]:
            return default

        try:
            limit = int(value)

        except (TypeError, ValueError):
            raise ValidationError({
                "limit": "La limite doit être un entier."
            })

        if limit < 1 or limit > 50:
            raise ValidationError({
                "limit": (
                    "La limite doit être comprise entre 1 et 50."
                )
            })

        return limit

    def get_service(self, request):
        date_from = self.parse_date(
            request.query_params.get("date_from"),
            "date_from",
        )
        date_to = self.parse_date(
            request.query_params.get("date_to"),
            "date_to",
        )

        if (
            date_from is not None
            and date_to is not None
            and date_from > date_to
        ):
            raise ValidationError({
                "date_to": (
                    "La date de fin doit être postérieure "
                    "ou égale à la date de début."
                )
            })

        group_by = request.query_params.get(
            "group_by",
            "month",
        )

        if group_by not in {"day", "week", "month", "year"}:
            raise ValidationError({
                "group_by": (
                    "Valeur invalide. Utilisez day, week, "
                    "month ou year."
                )
            })

        try:
            country = DashboardService.resolve_country(
                request.query_params.get("country")
            )

        except ValueError as exc:
            raise ValidationError({
                "country": str(exc)
            })

        return DashboardService(
            date_from=date_from,
            date_to=date_to,
            country=country,
            group_by=group_by,
        )


class DashboardOverviewView(DashboardViewBase):

    def get(self, request):
        service = self.get_service(request)
        limit = self.parse_limit(
            request.query_params.get("limit")
        )

        return Response(
            service.overview(limit=limit),
            status=status.HTTP_200_OK,
        )


class DashboardSalesView(DashboardViewBase):

    def get(self, request):
        service = self.get_service(request)
        limit = self.parse_limit(
            request.query_params.get("limit")
        )

        return Response(
            service.sales(limit=limit),
            status=status.HTTP_200_OK,
        )


class DashboardProductsView(DashboardViewBase):

    def get(self, request):
        service = self.get_service(request)
        limit = self.parse_limit(
            request.query_params.get("limit")
        )

        return Response(
            service.products(limit=limit),
            status=status.HTTP_200_OK,
        )


class DashboardCustomersView(DashboardViewBase):

    def get(self, request):
        service = self.get_service(request)
        limit = self.parse_limit(
            request.query_params.get("limit")
        )

        return Response(
            service.customers(limit=limit),
            status=status.HTTP_200_OK,
        )


class DashboardOrdersView(DashboardViewBase):

    def get(self, request):
        service = self.get_service(request)
        limit = self.parse_limit(
            request.query_params.get("limit"),
            default=5,
        )

        return Response(
            service.orders(limit=limit),
            status=status.HTTP_200_OK,
        )
