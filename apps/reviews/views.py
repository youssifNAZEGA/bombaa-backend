from django.db.models import Q
from django.shortcuts import get_object_or_404

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import (
    AllowAny,
    BasePermission,
    IsAuthenticated,
)
from rest_framework.response import Response

from apps.accounts.permissions import (
    HasPermission,
    user_has_permission,
)
from apps.audit.models import AuditLog
from apps.audit.services import AuditService
from apps.catalog.models import Product

from .models import Review
from .serializers import ReviewSerializer
from .services import ReviewService


class IsReviewModerator(BasePermission):
    message = "Vous n'avez pas la permission de modérer les avis."

    def has_permission(self, request, view):
        return ReviewService.is_moderator(request.user)


class CanUpdateReview(BasePermission):
    message = "Vous n'avez pas la permission de modifier cet avis."

    def has_permission(self, request, view):
        return (
            ReviewService.is_moderator(request.user)
            or user_has_permission(
                request.user,
                "reviews.update",
            )
        )


class CanDeleteReview(BasePermission):
    message = "Vous n'avez pas la permission de supprimer cet avis."

    def has_permission(self, request, view):
        return (
            ReviewService.is_moderator(request.user)
            or user_has_permission(
                request.user,
                "reviews.delete",
            )
        )


class ReviewViewSet(viewsets.ModelViewSet):
    serializer_class = ReviewSerializer

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [AllowAny()]

        if self.action == "create":
            return [HasPermission("reviews.create")()]

        if self.action in ["update", "partial_update"]:
            return [CanUpdateReview()]

        if self.action == "destroy":
            return [CanDeleteReview()]

        if self.action in ["approve", "reject"]:
            return [IsReviewModerator()]

        if self.action in ["mine", "eligibility"]:
            return [IsAuthenticated()]

        return [HasPermission("reviews.view")()]

    def get_queryset(self):
        queryset = (
            Review.objects
            .select_related(
                "product",
                "user",
                "moderated_by",
            )
            .prefetch_related("images")
        )

        user = self.request.user

        if not user or not user.is_authenticated:
            queryset = queryset.filter(
                status=Review.Status.APPROVED
            )
        elif not ReviewService.is_moderator(user):
            queryset = queryset.filter(
                Q(status=Review.Status.APPROVED)
                | Q(user=user)
            )

        product = self.request.query_params.get("product")

        if product:
            if product.isdigit():
                queryset = queryset.filter(
                    product_id=int(product)
                )
            else:
                queryset = queryset.filter(
                    product__slug=product
                )

        rating = self.request.query_params.get("rating")

        if rating:
            if not rating.isdigit():
                return queryset.none()

            queryset = queryset.filter(
                rating=int(rating)
            )

        review_status = self.request.query_params.get("status")

        if review_status:
            valid_statuses = {
                value
                for value, _label in Review.Status.choices
            }
            normalized = review_status.strip().upper()

            if normalized not in valid_statuses:
                return queryset.none()

            queryset = queryset.filter(status=normalized)

        mine = self.request.query_params.get("mine")

        if (
            mine is not None
            and mine.lower() in {"1", "true", "yes", "on"}
        ):
            if not user or not user.is_authenticated:
                return queryset.none()

            queryset = queryset.filter(user=user)

        search = self.request.query_params.get("search")

        if search:
            queryset = queryset.filter(
                Q(comment__icontains=search)
                | Q(product__name__icontains=search)
                | Q(user__first_name__icontains=search)
                | Q(user__last_name__icontains=search)
            )

        return queryset

    def perform_create(self, serializer):
        review = serializer.save()

        AuditService.log(
            action=AuditLog.Action.CREATE,
            actor=self.request.user,
            target=review,
            metadata={
                "product_id": review.product_id,
                "rating": review.rating,
                "verified": review.is_verified_purchase,
            },
            request=self.request,
        )

    def perform_update(self, serializer):
        review = serializer.instance
        user = self.request.user

        if (
            not ReviewService.is_moderator(user)
            and review.user_id != user.id
        ):
            raise PermissionDenied(
                "Cet avis ne vous appartient pas."
            )

        before = {
            "rating": review.rating,
            "comment": review.comment,
            "status": review.status,
        }

        review = serializer.save()
        moderator = ReviewService.is_moderator(user)

        if not moderator:
            review.status = Review.Status.PENDING
            review.moderated_by = None
            review.moderated_at = None
            review.moderation_note = None
            review.save(
                update_fields=[
                    "status",
                    "moderated_by",
                    "moderated_at",
                    "moderation_note",
                    "updated_at",
                ]
            )

        after = {
            "rating": review.rating,
            "comment": review.comment,
            "status": review.status,
        }

        changes = {
            field: {
                "before": before[field],
                "after": after[field],
            }
            for field in before
            if before[field] != after[field]
        }

        AuditService.log(
            action=AuditLog.Action.UPDATE,
            actor=user,
            target=review,
            changes=changes,
            metadata={"moderator": moderator},
            request=self.request,
        )

    def destroy(self, request, *args, **kwargs):
        review = self.get_object()
        user = request.user

        if (
            not ReviewService.is_moderator(user)
            and review.user_id != user.id
        ):
            raise PermissionDenied(
                "Cet avis ne vous appartient pas."
            )

        review_id = review.pk
        review_repr = str(review)
        product_id = review.product_id

        review.delete()

        AuditService.log(
            action=AuditLog.Action.DELETE,
            actor=user,
            target_type="reviews.review",
            target_id=str(review_id),
            target_repr=review_repr,
            metadata={"product_id": product_id},
            request=request,
        )

        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        detail=True,
        methods=["post"],
        url_path="approve",
    )
    def approve(self, request, pk=None):
        review = self.get_object()
        previous_status = review.status
        note = request.data.get("moderation_note")

        review.approve(
            moderator=request.user,
            note=note,
        )

        AuditService.log(
            action=AuditLog.Action.STATUS_CHANGE,
            actor=request.user,
            target=review,
            changes={
                "status": {
                    "before": previous_status,
                    "after": review.status,
                }
            },
            metadata={"moderation_note": note},
            request=request,
        )

        return Response(
            ReviewSerializer(
                review,
                context=self.get_serializer_context(),
            ).data
        )

    @action(
        detail=True,
        methods=["post"],
        url_path="reject",
    )
    def reject(self, request, pk=None):
        review = self.get_object()
        previous_status = review.status
        note = request.data.get("moderation_note")

        review.reject(
            moderator=request.user,
            note=note,
        )

        AuditService.log(
            action=AuditLog.Action.STATUS_CHANGE,
            actor=request.user,
            target=review,
            changes={
                "status": {
                    "before": previous_status,
                    "after": review.status,
                }
            },
            metadata={"moderation_note": note},
            request=request,
        )

        return Response(
            ReviewSerializer(
                review,
                context=self.get_serializer_context(),
            ).data
        )

    @action(
        detail=False,
        methods=["get"],
        url_path="mine",
    )
    def mine(self, request):
        queryset = (
            Review.objects
            .filter(user=request.user)
            .select_related("product", "moderated_by")
            .prefetch_related("images")
        )

        serializer = ReviewSerializer(
            queryset,
            many=True,
            context=self.get_serializer_context(),
        )

        return Response(serializer.data)

    @action(
        detail=False,
        methods=["get"],
        url_path="eligibility",
    )
    def eligibility(self, request):
        value = request.query_params.get("product")

        if not value:
            return Response(
                {
                    "product": (
                        "Le paramètre product est obligatoire."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        products = Product.objects.filter(is_active=True)

        if value.isdigit():
            product = get_object_or_404(
                products,
                pk=int(value),
            )
        else:
            product = get_object_or_404(
                products,
                slug=value,
            )

        existing_review = (
            Review.objects
            .filter(
                user=request.user,
                product=product,
            )
            .first()
        )
        has_purchased = ReviewService.has_purchased(
            request.user,
            product,
        )

        reason = None

        if existing_review is not None:
            reason = "already_reviewed"
        elif not has_purchased:
            reason = "not_purchased"

        return Response(
            {
                "product": product.id,
                "has_purchased": has_purchased,
                "can_review": (
                    has_purchased
                    and existing_review is None
                ),
                "reason": reason,
                "existing_review": (
                    ReviewSerializer(
                        existing_review,
                        context=self.get_serializer_context(),
                    ).data
                    if existing_review is not None
                    else None
                ),
            }
        )
