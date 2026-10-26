from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    FaqEntryViewSet,
    SupportContactView,
    SupportTicketViewSet,
)


router = DefaultRouter()

router.register(
    "tickets",
    SupportTicketViewSet,
    basename="support-ticket",
)

router.register(
    "faq",
    FaqEntryViewSet,
    basename="support-faq",
)

urlpatterns = [
    path(
        "contact/",
        SupportContactView.as_view(),
        name="support-contact",
    ),
] + router.urls
