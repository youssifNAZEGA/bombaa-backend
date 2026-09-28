from django.urls import path

from .views import OrderViewSet


order_list_view = OrderViewSet.as_view({
    "get": "list",
    "post": "create",
})

order_detail_view = OrderViewSet.as_view({
    "get": "retrieve",
})


urlpatterns = [
    path(
        "orders/",
        order_list_view,
        name="order-list",
    ),
    path(
        "orders/<int:pk>/",
        order_detail_view,
        name="order-detail",
    ),
]