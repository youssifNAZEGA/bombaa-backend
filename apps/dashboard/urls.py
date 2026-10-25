from django.urls import path

from .views import (
    DashboardCustomersView,
    DashboardOrdersView,
    DashboardOverviewView,
    DashboardProductsView,
    DashboardSalesView,
)


urlpatterns = [
    path(
        "dashboard/overview/",
        DashboardOverviewView.as_view(),
        name="dashboard-overview",
    ),
    path(
        "dashboard/sales/",
        DashboardSalesView.as_view(),
        name="dashboard-sales",
    ),
    path(
        "dashboard/products/",
        DashboardProductsView.as_view(),
        name="dashboard-products",
    ),
    path(
        "dashboard/customers/",
        DashboardCustomersView.as_view(),
        name="dashboard-customers",
    ),
    path(
        "dashboard/orders/",
        DashboardOrdersView.as_view(),
        name="dashboard-orders",
    ),
]
