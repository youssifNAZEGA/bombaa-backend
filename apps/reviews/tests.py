from decimal import Decimal
from uuid import uuid4

from rest_framework.test import APITestCase

from apps.accounts.models import Permission, Role, User
from apps.audit.models import AuditLog
from apps.catalog.models import (
    Brand,
    Category,
    Product,
    ProductCategory,
    ProductVariant,
)
from apps.orders.models import Order, OrderItem

from .models import Review, ReviewImage
from .services import ReviewService


PERMISSION_NAMES = [
    "reviews.view",
    "reviews.create",
    "reviews.update",
    "reviews.delete",
    "reviews.moderate",
    "products.view",
]


class ReviewTestBase(APITestCase):
    def setUp(self):
        self.permissions = {
            name: Permission.objects.create(name=name)
            for name in PERMISSION_NAMES
        }

        self.client_role = Role.objects.create(
            name="REVIEW_CLIENT",
            description="Client de test",
        )
        self.client_role.permissions.set([
            self.permissions["reviews.view"],
            self.permissions["reviews.create"],
            self.permissions["reviews.update"],
            self.permissions["reviews.delete"],
            self.permissions["products.view"],
        ])

        self.moderator_role = Role.objects.create(
            name="REVIEW_MODERATOR",
            description="Modérateur de test",
        )
        self.moderator_role.permissions.set([
            self.permissions["reviews.view"],
            self.permissions["reviews.moderate"],
        ])

        self.author = self.create_user(
            "review-author@example.com",
            self.client_role,
        )
        self.other_client = self.create_user(
            "review-other@example.com",
            self.client_role,
        )
        self.moderator = self.create_user(
            "review-moderator@example.com",
            self.moderator_role,
        )
        self.staff_user = self.create_user(
            "review-staff@example.com",
            self.moderator_role,
            is_staff=True,
        )

        self.brand = Brand.objects.create(
            name="Marque avis",
        )
        self.category = Category.objects.create(
            name="Catégorie avis",
            slug="categorie-avis",
        )
        self.product = Product.objects.create(
            brand=self.brand,
            name="Produit évalué",
            slug="produit-evalue",
            description="Un produit de test.",
            base_price=Decimal("10000.00"),
            weight_grams=100,
        )
        ProductCategory.objects.create(
            product=self.product,
            category=self.category,
        )
        self.variant = ProductVariant.objects.create(
            product=self.product,
            sku="REVIEW-001",
            price=Decimal("10000.00"),
        )
        self.second_variant = ProductVariant.objects.create(
            product=self.product,
            sku="REVIEW-002",
            price=Decimal("12000.00"),
        )

        self.other_product = Product.objects.create(
            brand=self.brand,
            name="Autre produit évalué",
            slug="autre-produit-evalue",
            base_price=Decimal("5000.00"),
            weight_grams=100,
        )
        self.other_variant = ProductVariant.objects.create(
            product=self.other_product,
            sku="REVIEW-003",
            price=Decimal("5000.00"),
        )

    def create_user(self, email, role, is_staff=False):
        user = User.objects.create_user(
            email=email,
            password="TestPassword123!",
            first_name="Test",
            last_name="Avis",
            phone=f"+228{abs(hash(email)) % 100000000:08d}",
            is_staff=is_staff,
        )
        user.roles.add(role)
        return user

    def create_order(
        self,
        *,
        user=None,
        product=None,
        status=Order.Status.COMPLETED,
    ):
        product = product or self.product
        variant = product.variants.first()

        order = Order.objects.create(
            user=user or self.author,
            reference=f"REV-{uuid4().hex[:10].upper()}",
            status=status,
            subtotal=Decimal("10000.00"),
            total_amount=Decimal("10000.00"),
        )

        item = OrderItem.objects.create(
            order=order,
            variant=variant,
            product_name=product.name,
            sku=variant.sku,
            quantity=1,
            unit_price=Decimal("10000.00"),
            subtotal=Decimal("10000.00"),
        )

        return order, item

    def create_review(
        self,
        *,
        user=None,
        product=None,
        rating=5,
        comment="Très bon produit",
        status=Review.Status.PENDING,
    ):
        return Review.objects.create(
            user=user or self.author,
            product=product or self.product,
            rating=rating,
            comment=comment,
            status=status,
        )


class ReviewCreationTests(ReviewTestBase):
    def test_anonymous_cannot_create_review(self):
        response = self.client.post(
            "/api/reviews/",
            {
                "product": self.product.id,
                "rating": 5,
                "comment": "Anonyme",
            },
            format="json",
        )

        self.assertIn(response.status_code, (401, 403))
        self.assertEqual(Review.objects.count(), 0)

    def test_client_without_purchase_cannot_review(self):
        self.client.force_authenticate(self.author)

        response = self.client.post(
            "/api/reviews/",
            {
                "product": self.product.id,
                "rating": 5,
                "comment": "Achat inexistant",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("product", response.data)
        self.assertEqual(Review.objects.count(), 0)

    def test_cancelled_order_does_not_allow_review(self):
        self.create_order(status=Order.Status.CANCELLED)
        self.client.force_authenticate(self.author)

        response = self.client.post(
            "/api/reviews/",
            {
                "product": self.product.id,
                "rating": 4,
                "comment": "Commande annulée",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Review.objects.count(), 0)

    def test_purchase_allows_verified_review(self):
        order, item = self.create_order(
            status=Order.Status.CONFIRMED
        )
        self.client.force_authenticate(self.author)

        response = self.client.post(
            "/api/reviews/",
            {
                "product": self.product.id,
                "rating": 5,
                "comment": "  Excellent produit  ",
                "images": [
                    {
                        "image_url": "https://cdn.example.com/1.jpg",
                        "alt_text": "Face avant",
                    },
                    {
                        "image_url": "https://cdn.example.com/2.jpg",
                    },
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], Review.Status.PENDING)
        self.assertTrue(response.data["is_verified_purchase"])
        self.assertEqual(response.data["comment"], "Excellent produit")
        self.assertEqual(len(response.data["images"]), 2)

        review = Review.objects.get(pk=response.data["id"])
        self.assertEqual(review.user, self.author)
        self.assertEqual(review.order_item_id, item.id)
        self.assertEqual(review.product, self.product)
        self.assertEqual(review.images.count(), 2)
        self.assertEqual(review.status, Review.Status.PENDING)

        self.assertTrue(
            AuditLog.objects.filter(
                action=AuditLog.Action.CREATE,
                actor=self.author,
                target_type="reviews.review",
                target_id=str(review.id),
            ).exists()
        )

    def test_duplicate_review_is_rejected(self):
        self.create_order()
        self.create_review()
        self.client.force_authenticate(self.author)

        response = self.client.post(
            "/api/reviews/",
            {
                "product": self.product.id,
                "rating": 3,
                "comment": "Deuxième avis",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("product", response.data)
        self.assertEqual(Review.objects.count(), 1)

    def test_rating_must_be_between_one_and_five(self):
        self.create_order()
        self.client.force_authenticate(self.author)

        for rating in (0, 6):
            response = self.client.post(
                "/api/reviews/",
                {
                    "product": self.product.id,
                    "rating": rating,
                    "comment": "Note invalide",
                },
                format="json",
            )

            self.assertEqual(response.status_code, 400)
            self.assertIn("rating", response.data)

        self.assertEqual(Review.objects.count(), 0)

    def test_review_cannot_exceed_ten_images(self):
        self.create_order()
        self.client.force_authenticate(self.author)

        response = self.client.post(
            "/api/reviews/",
            {
                "product": self.product.id,
                "rating": 5,
                "images": [
                    {
                        "image_url": (
                            f"https://cdn.example.com/{index}.jpg"
                        )
                    }
                    for index in range(11)
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("images", response.data)

    def test_product_can_only_be_reviewed_after_buying_it(self):
        self.create_order(product=self.other_product)
        self.client.force_authenticate(self.author)

        response = self.client.post(
            "/api/reviews/",
            {
                "product": self.product.id,
                "rating": 5,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Review.objects.count(), 0)


class ReviewVisibilityTests(ReviewTestBase):
    def setUp(self):
        super().setUp()
        self.approved = self.create_review(
            user=self.author,
            rating=5,
            status=Review.Status.APPROVED,
        )
        self.pending = self.create_review(
            user=self.other_client,
            rating=1,
            comment="En attente",
            status=Review.Status.PENDING,
        )
        self.rejected = self.create_review(
            user=self.moderator,
            rating=2,
            comment="Rejeté",
            status=Review.Status.REJECTED,
        )

    def test_public_list_only_returns_approved_reviews(self):
        response = self.client.get("/api/reviews/")

        self.assertEqual(response.status_code, 200)
        identifiers = [
            item["id"] for item in response.data["results"]
        ]

        self.assertIn(self.approved.id, identifiers)
        self.assertNotIn(self.pending.id, identifiers)
        self.assertNotIn(self.rejected.id, identifiers)

    def test_author_sees_own_pending_review(self):
        self.client.force_authenticate(self.other_client)

        response = self.client.get("/api/reviews/")

        self.assertEqual(response.status_code, 200)
        identifiers = [
            item["id"] for item in response.data["results"]
        ]

        self.assertIn(self.pending.id, identifiers)
        self.assertIn(self.approved.id, identifiers)
        self.assertNotIn(self.rejected.id, identifiers)

    def test_author_cannot_retrieve_another_pending_review(self):
        self.client.force_authenticate(self.author)

        response = self.client.get(
            f"/api/reviews/{self.pending.id}/"
        )

        self.assertEqual(response.status_code, 404)

    def test_moderator_sees_all_reviews(self):
        self.client.force_authenticate(self.moderator)

        response = self.client.get("/api/reviews/")

        self.assertEqual(response.status_code, 200)
        identifiers = {
            item["id"] for item in response.data["results"]
        }

        self.assertEqual(
            identifiers,
            {self.approved.id, self.pending.id, self.rejected.id},
        )

    def test_mine_returns_only_own_reviews(self):
        self.client.force_authenticate(self.other_client)

        response = self.client.get("/api/reviews/mine/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], self.pending.id)

    def test_rating_filter_and_search(self):
        self.create_review(
            user=self.staff_user,
            rating=5,
            comment="Cherche moi",
            status=Review.Status.APPROVED,
        )

        response = self.client.get("/api/reviews/?rating=5")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            all(
                item["rating"] == 5
                for item in response.data["results"]
            )
        )

        response = self.client.get("/api/reviews/?search=Cherche")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(
            response.data["results"][0]["comment"],
            "Cherche moi",
        )

    def test_product_reviews_endpoint_returns_approved_only(self):
        self.create_review(
            user=self.staff_user,
            rating=4,
            status=Review.Status.APPROVED,
        )

        response = self.client.get(
            f"/api/products/{self.product.id}/reviews/"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)
        self.assertTrue(
            all(
                item["status"] == Review.Status.APPROVED
                for item in response.data
            )
        )
        self.assertNotIn(
            self.pending.id,
            [item["id"] for item in response.data],
        )


class ReviewModerationTests(ReviewTestBase):
    def test_author_can_update_own_review_and_resets_to_pending(self):
        self.create_order()
        review = self.create_review(
            status=Review.Status.APPROVED,
        )
        review.approve(moderator=self.moderator, note="Validé")
        self.client.force_authenticate(self.author)

        response = self.client.patch(
            f"/api/reviews/{review.id}/",
            {
                "rating": 4,
                "comment": "Commentaire modifié",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        review.refresh_from_db()
        self.assertEqual(review.rating, 4)
        self.assertEqual(review.comment, "Commentaire modifié")
        self.assertEqual(review.status, Review.Status.PENDING)
        self.assertIsNone(review.moderated_by)
        self.assertIsNone(review.moderated_at)
        self.assertIsNone(review.moderation_note)

        self.assertTrue(
            AuditLog.objects.filter(
                action=AuditLog.Action.UPDATE,
                actor=self.author,
                target_type="reviews.review",
                target_id=str(review.id),
            ).exists()
        )

    def test_author_cannot_change_review_product(self):
        review = self.create_review()
        self.client.force_authenticate(self.author)

        response = self.client.patch(
            f"/api/reviews/{review.id}/",
            {"product": self.other_product.id},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        review.refresh_from_db()
        self.assertEqual(review.product, self.product)

    def test_other_client_cannot_update_or_delete_review(self):
        review = self.create_review(
            status=Review.Status.APPROVED,
        )
        self.client.force_authenticate(self.other_client)

        response = self.client.patch(
            f"/api/reviews/{review.id}/",
            {"comment": "Piratage"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

        response = self.client.delete(
            f"/api/reviews/{review.id}/"
        )
        self.assertEqual(response.status_code, 403)
        self.assertTrue(
            Review.objects.filter(pk=review.id).exists()
        )

    def test_author_can_delete_own_review(self):
        review = self.create_review()
        review_id = review.id
        self.client.force_authenticate(self.author)

        response = self.client.delete(
            f"/api/reviews/{review_id}/"
        )

        self.assertEqual(response.status_code, 204)
        self.assertFalse(
            Review.objects.filter(pk=review_id).exists()
        )
        self.assertTrue(
            AuditLog.objects.filter(
                action=AuditLog.Action.DELETE,
                actor=self.author,
                target_type="reviews.review",
                target_id=str(review_id),
            ).exists()
        )

    def test_client_cannot_moderate_review(self):
        review = self.create_review()
        self.client.force_authenticate(self.author)

        for action_name in ("approve", "reject"):
            response = self.client.post(
                f"/api/reviews/{review.id}/{action_name}/"
            )
            self.assertEqual(response.status_code, 403)

        review.refresh_from_db()
        self.assertEqual(review.status, Review.Status.PENDING)

    def test_moderator_can_approve_review(self):
        review = self.create_review()
        self.client.force_authenticate(self.moderator)

        response = self.client.post(
            f"/api/reviews/{review.id}/approve/",
            {"moderation_note": "Conforme"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], Review.Status.APPROVED)

        review.refresh_from_db()
        self.assertEqual(review.status, Review.Status.APPROVED)
        self.assertEqual(review.moderated_by, self.moderator)
        self.assertIsNotNone(review.moderated_at)
        self.assertEqual(review.moderation_note, "Conforme")

        self.assertTrue(
            AuditLog.objects.filter(
                action=AuditLog.Action.STATUS_CHANGE,
                actor=self.moderator,
                target_type="reviews.review",
                target_id=str(review.id),
            ).exists()
        )

    def test_staff_can_reject_review(self):
        review = self.create_review()
        self.client.force_authenticate(self.staff_user)

        response = self.client.post(
            f"/api/reviews/{review.id}/reject/",
            {"moderation_note": "Contenu inapproprié"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], Review.Status.REJECTED)

        review.refresh_from_db()
        self.assertEqual(review.status, Review.Status.REJECTED)
        self.assertEqual(review.moderation_note, "Contenu inapproprié")

    def test_moderator_update_keeps_approved_status(self):
        review = self.create_review(
            status=Review.Status.APPROVED,
        )
        self.client.force_authenticate(self.moderator)

        response = self.client.patch(
            f"/api/reviews/{review.id}/",
            {"comment": "Corrigé par la modération"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        review.refresh_from_db()
        self.assertEqual(review.status, Review.Status.APPROVED)
        self.assertEqual(
            review.comment,
            "Corrigé par la modération",
        )

    def test_moderator_can_delete_any_review(self):
        review = self.create_review()
        review_id = review.id
        self.client.force_authenticate(self.moderator)

        response = self.client.delete(
            f"/api/reviews/{review_id}/"
        )

        self.assertEqual(response.status_code, 204)
        self.assertFalse(
            Review.objects.filter(pk=review_id).exists()
        )


class ReviewStatsTests(ReviewTestBase):
    def test_service_only_counts_approved_reviews(self):
        self.create_review(
            user=self.author,
            rating=5,
            status=Review.Status.APPROVED,
        )
        self.create_review(
            user=self.other_client,
            rating=3,
            status=Review.Status.APPROVED,
        )
        self.create_review(
            user=self.moderator,
            rating=1,
            status=Review.Status.PENDING,
        )
        self.create_review(
            user=self.staff_user,
            rating=1,
            status=Review.Status.REJECTED,
        )

        stats = ReviewService.stats_for_product(self.product)

        self.assertEqual(stats["review_count"], 2)
        self.assertEqual(
            Decimal(stats["average_rating"]).quantize(
                Decimal("0.01")
            ),
            Decimal("4.00"),
        )

    def test_product_detail_exposes_average_and_count(self):
        self.create_review(
            user=self.author,
            rating=5,
            status=Review.Status.APPROVED,
        )
        self.create_review(
            user=self.other_client,
            rating=3,
            status=Review.Status.APPROVED,
        )
        self.create_review(
            user=self.moderator,
            rating=1,
            status=Review.Status.PENDING,
        )

        response = self.client.get(
            f"/api/products/{self.product.id}/"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["average_rating"], "4.00")
        self.assertEqual(response.data["review_count"], 2)

    def test_product_list_exposes_stats_with_variants(self):
        self.create_review(
            user=self.author,
            rating=5,
            status=Review.Status.APPROVED,
        )
        self.create_review(
            user=self.other_client,
            rating=3,
            status=Review.Status.APPROVED,
        )

        response = self.client.get("/api/products/")

        self.assertEqual(response.status_code, 200)
        products = {
            item["id"]: item
            for item in response.data["results"]
        }

        self.assertIn(self.product.id, products)
        self.assertEqual(
            products[self.product.id]["average_rating"],
            "4.00",
        )
        self.assertEqual(
            products[self.product.id]["review_count"],
            2,
        )

    def test_product_without_review_has_zero_stats(self):
        response = self.client.get(
            f"/api/products/{self.product.id}/"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["average_rating"], "0.00")
        self.assertEqual(response.data["review_count"], 0)

    def test_rejected_review_does_not_affect_product_stats(self):
        self.create_review(
            rating=1,
            status=Review.Status.REJECTED,
        )

        response = self.client.get(
            f"/api/products/{self.product.id}/"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["average_rating"], "0.00")
        self.assertEqual(response.data["review_count"], 0)


class ReviewEligibilityTests(ReviewTestBase):
    def test_requires_product_parameter(self):
        self.client.force_authenticate(self.author)

        response = self.client.get("/api/reviews/eligibility/")

        self.assertEqual(response.status_code, 400)

    def test_not_purchased(self):
        self.client.force_authenticate(self.author)

        response = self.client.get(
            f"/api/reviews/eligibility/?product={self.product.id}"
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["has_purchased"])
        self.assertFalse(response.data["can_review"])
        self.assertEqual(response.data["reason"], "not_purchased")

    def test_purchased_without_review(self):
        self.create_order()
        self.client.force_authenticate(self.author)

        response = self.client.get(
            f"/api/reviews/eligibility/?product={self.product.slug}"
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["has_purchased"])
        self.assertTrue(response.data["can_review"])
        self.assertIsNone(response.data["reason"])
        self.assertIsNone(response.data["existing_review"])

    def test_purchased_with_existing_review(self):
        self.create_order()
        review = self.create_review()
        self.client.force_authenticate(self.author)

        response = self.client.get(
            f"/api/reviews/eligibility/?product={self.product.id}"
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["can_review"])
        self.assertEqual(
            response.data["reason"],
            "already_reviewed",
        )
        self.assertEqual(
            response.data["existing_review"]["id"],
            review.id,
        )


class ReviewModelTests(ReviewTestBase):
    def test_review_string_representation(self):
        review = self.create_review()

        self.assertIn(self.product.name, str(review))
        self.assertIn(self.author.email, str(review))

    def test_review_image_ordering_and_representation(self):
        review = self.create_review()
        first = ReviewImage.objects.create(
            review=review,
            image_url="https://cdn.example.com/a.jpg",
        )
        ReviewImage.objects.create(
            review=review,
            image_url="https://cdn.example.com/b.jpg",
        )

        self.assertEqual(review.images.count(), 2)
        self.assertEqual(review.images.first(), first)
        self.assertIn(
            first.image_url,
            str(first),
        )
