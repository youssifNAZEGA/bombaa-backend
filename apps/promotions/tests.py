from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from rest_framework.test import APITestCase

from apps.accounts.models import Permission, Role, User
from apps.addresses.models import Address
from apps.audit.models import AuditLog
from apps.cart.models import Cart, CartItem
from apps.catalog.models import (
    Brand,
    Category,
    Product,
    ProductCategory,
    ProductVariant,
)
from apps.geography.models import Country, Currency
from apps.notifications.models import Notification
from apps.orders.models import Order
from apps.promotions.models import (
    Coupon,
    CouponRedemption,
    DiscountType,
    Promotion,
)
from apps.shipping.models import (
    ShippingMethod,
    ShippingRate,
    ShippingZone,
)
from apps.stocks.models import Stock


PERMISSION_NAMES = [
    "promotions.view",
    "promotions.create",
    "promotions.update",
    "promotions.delete",
    "coupons.view",
    "coupons.create",
    "coupons.update",
    "coupons.delete",
    "orders.view",
    "orders.create",
    "orders.update",
    "payments.view",
    "payments.create",
    "products.view",
    "categories.view",
    "brands.view",
    "shipping.view",
    "notifications.view",
]


class PromotionTestBase(APITestCase):
    def setUp(self):
        self.permissions = {
            name: Permission.objects.create(name=name)
            for name in PERMISSION_NAMES
        }

        self.client_role = Role.objects.create(
            name="TEST_CLIENT",
            description="Client de test",
        )
        self.client_role.permissions.set([
            self.permissions["orders.view"],
            self.permissions["orders.create"],
            self.permissions["payments.view"],
            self.permissions["payments.create"],
            self.permissions["products.view"],
            self.permissions["notifications.view"],
        ])

        self.admin_role = Role.objects.create(
            name="TEST_ADMIN",
            description="Administrateur de test",
        )
        self.admin_role.permissions.set(
            self.permissions.values()
        )

        self.client_user = self.create_user(
            "promo-client@example.com",
            self.client_role,
        )
        self.other_client = self.create_user(
            "promo-other@example.com",
            self.client_role,
        )
        self.admin_user = self.create_user(
            "promo-admin@example.com",
            self.admin_role,
            is_staff=True,
        )

        self.currency = Currency.objects.create(
            code="XOF",
            name="Franc CFA",
            symbol="F",
            exchange_rate=Decimal("1.000000"),
            is_base=True,
        )
        self.togo = Country.objects.create(
            name="Togo",
            code="TG",
            currency=self.currency,
        )
        self.france = Country.objects.create(
            name="France",
            code="FR",
            currency=self.currency,
        )

        self.category = Category.objects.create(
            name="Catégorie promotion",
            slug="categorie-promotion",
        )
        self.brand = Brand.objects.create(
            name="Marque promotion",
        )
        self.product = Product.objects.create(
            brand=self.brand,
            name="Produit promotion",
            slug="produit-promotion",
            base_price=Decimal("10000.00"),
            weight_grams=100,
        )
        ProductCategory.objects.create(
            product=self.product,
            category=self.category,
        )
        self.variant = ProductVariant.objects.create(
            product=self.product,
            sku="PROMO-001",
            price=Decimal("10000.00"),
        )
        self.stock = Stock.objects.create(
            variant=self.variant,
            quantity=50,
            reserved_quantity=0,
            minimum_quantity=1,
        )

        self.other_product = Product.objects.create(
            brand=self.brand,
            name="Autre produit",
            slug="autre-produit",
            base_price=Decimal("5000.00"),
            weight_grams=100,
        )
        ProductCategory.objects.create(
            product=self.other_product,
            category=Category.objects.create(
                name="Catégorie secondaire",
                slug="categorie-secondaire",
            ),
        )
        self.other_variant = ProductVariant.objects.create(
            product=self.other_product,
            sku="PROMO-002",
            price=Decimal("5000.00"),
        )
        self.other_stock = Stock.objects.create(
            variant=self.other_variant,
            quantity=50,
            reserved_quantity=0,
            minimum_quantity=1,
        )

        self.shipping_method = ShippingMethod.objects.create(
            name="Standard",
            code="STD",
            estimated_days=3,
        )
        self.shipping_zone = ShippingZone.objects.create(
            name="Zone Togo",
        )
        self.shipping_zone.countries.add(self.togo)
        ShippingRate.objects.create(
            zone=self.shipping_zone,
            method=self.shipping_method,
            min_weight_grams=0,
            max_weight_grams=None,
            price=Decimal("500.00"),
            currency=self.currency,
        )

        self.address = Address.objects.create(
            user=self.client_user,
            first_name="Client",
            last_name="Promotion",
            phone="+22890000001",
            address_line_1="1 rue des Promotions",
            city="Lomé",
            country="Togo",
            country_ref=self.togo,
            is_default=True,
        )

    def create_user(self, email, role, is_staff=False):
        user = User.objects.create_user(
            email=email,
            password="TestPassword123!",
            first_name="Test",
            last_name="Promotion",
            phone=f"+228{abs(hash(email)) % 100000000:08d}",
            is_staff=is_staff,
        )
        user.roles.add(role)
        return user

    def create_cart(self, quantity=2, variant=None):
        cart, _created = Cart.objects.get_or_create(
            user=self.client_user
        )
        CartItem.objects.create(
            cart=cart,
            variant=variant or self.variant,
            quantity=quantity,
        )
        return cart

    def create_promotion(
        self,
        *,
        name="Promotion test",
        discount_type=DiscountType.PERCENTAGE,
        value=Decimal("10.00"),
        products=None,
        categories=None,
        brands=None,
        countries=None,
        is_active=True,
        starts_at=None,
        ends_at=None,
    ):
        promotion = Promotion.objects.create(
            name=name,
            discount_type=discount_type,
            value=value,
            is_active=is_active,
            starts_at=starts_at,
            ends_at=ends_at,
        )

        if products:
            promotion.products.set(products)
        if categories:
            promotion.categories.set(categories)
        if brands:
            promotion.brands.set(brands)
        if countries:
            promotion.countries.set(countries)

        return promotion

    def create_coupon(
        self,
        *,
        code="SAVE10",
        discount_type=DiscountType.PERCENTAGE,
        value=Decimal("10.00"),
        minimum_amount=Decimal("0.00"),
        max_uses=None,
        products=None,
        categories=None,
        countries=None,
        is_active=True,
        starts_at=None,
        ends_at=None,
    ):
        coupon = Coupon.objects.create(
            code=code,
            discount_type=discount_type,
            value=value,
            minimum_amount=minimum_amount,
            max_uses=max_uses,
            is_active=is_active,
            starts_at=starts_at,
            ends_at=ends_at,
        )

        if products:
            coupon.products.set(products)
        if categories:
            coupon.categories.set(categories)
        if countries:
            coupon.countries.set(countries)

        return coupon


class PromotionManagementTests(PromotionTestBase):
    def test_client_cannot_manage_promotions(self):
        self.client.force_authenticate(self.client_user)

        response = self.client.post(
            "/api/promotions/",
            {
                "name": "Promotion pirate",
                "discount_type": DiscountType.PERCENTAGE,
                "value": "20.00",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            Promotion.objects.filter(
                name="Promotion pirate"
            ).exists()
        )

    def test_admin_can_create_update_activate_and_deactivate(self):
        self.client.force_authenticate(self.admin_user)

        response = self.client.post(
            "/api/promotions/",
            {
                "name": "Black Friday",
                "description": "Une belle remise",
                "discount_type": DiscountType.PERCENTAGE,
                "value": "20.00",
                "products": [self.product.id],
                "countries": [self.togo.id],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["is_running"])

        promotion = Promotion.objects.get(
            name="Black Friday"
        )
        self.assertEqual(
            promotion.products.first(),
            self.product,
        )
        self.assertEqual(
            promotion.countries.first(),
            self.togo,
        )

        response = self.client.patch(
            f"/api/promotions/{promotion.id}/",
            {"value": "25.00"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        promotion.refresh_from_db()
        self.assertEqual(promotion.value, Decimal("25.00"))

        response = self.client.post(
            f"/api/promotions/{promotion.id}/deactivate/"
        )
        self.assertEqual(response.status_code, 200)
        promotion.refresh_from_db()
        self.assertFalse(promotion.is_active)

        response = self.client.post(
            f"/api/promotions/{promotion.id}/activate/"
        )
        self.assertEqual(response.status_code, 200)
        promotion.refresh_from_db()
        self.assertTrue(promotion.is_active)

        self.assertTrue(
            AuditLog.objects.filter(
                target_type="promotions.promotion",
                target_id=str(promotion.id),
            ).exists()
        )

    def test_public_promotion_list_hides_inactive_and_expired(self):
        now = timezone.now()

        self.create_promotion(
            name="Promotion active",
            ends_at=now + timedelta(days=1),
        )
        self.create_promotion(
            name="Promotion inactive",
            is_active=False,
        )
        self.create_promotion(
            name="Promotion expirée",
            ends_at=now - timedelta(days=1),
        )

        response = self.client.get("/api/promotions/")

        self.assertEqual(response.status_code, 200)

        names = [
            promotion["name"]
            for promotion in response.data["results"]
        ]

        self.assertIn("Promotion active", names)
        self.assertNotIn("Promotion inactive", names)
        self.assertNotIn("Promotion expirée", names)

    def test_promotion_requires_percentage_not_above_100(self):
        self.client.force_authenticate(self.admin_user)

        response = self.client.post(
            "/api/promotions/",
            {
                "name": "Promotion invalide",
                "discount_type": DiscountType.PERCENTAGE,
                "value": "120.00",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("value", response.data)


class CouponManagementTests(PromotionTestBase):
    def test_admin_can_create_coupon_with_generated_code(self):
        self.client.force_authenticate(self.admin_user)

        response = self.client.post(
            "/api/coupons/",
            {
                "description": "Coupon de bienvenue",
                "discount_type": DiscountType.PERCENTAGE,
                "value": "10.00",
                "minimum_amount": "5000.00",
                "max_uses": 100,
                "countries": [self.togo.id],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["code"].startswith("BOMBAA-"))
        self.assertEqual(response.data["current_uses"], 0)
        self.assertEqual(response.data["remaining_uses"], 100)

    def test_duplicate_coupon_code_is_rejected(self):
        self.create_coupon(code="UNIQUE10")

        self.client.force_authenticate(self.admin_user)

        response = self.client.post(
            "/api/coupons/",
            {
                "code": "unique10",
                "discount_type": DiscountType.FIXED,
                "value": "1000.00",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("code", response.data)

    def test_client_cannot_list_coupons(self):
        self.client.force_authenticate(self.client_user)

        response = self.client.get("/api/coupons/")

        self.assertEqual(response.status_code, 403)

    def test_used_coupon_cannot_be_deleted(self):
        coupon = self.create_coupon(max_uses=1)
        cart = self.create_cart()

        self.client.force_authenticate(self.client_user)
        response = self.client.post(
            "/api/orders/",
            {
                "address_id": self.address.id,
                "coupon_code": coupon.code,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)

        cart.delete()

        self.client.force_authenticate(self.admin_user)
        response = self.client.delete(
            f"/api/coupons/{coupon.id}/"
        )

        self.assertEqual(response.status_code, 400)
        self.assertTrue(
            Coupon.objects.filter(pk=coupon.pk).exists()
        )


class CartPricingTests(PromotionTestBase):
    def test_percentage_promotion_is_applied_to_cart(self):
        self.create_promotion(
            products=[self.product],
            value=Decimal("10.00"),
        )
        self.create_cart(quantity=2)

        self.client.force_authenticate(self.client_user)

        response = self.client.get("/api/cart/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["subtotal"], "20000.00")
        self.assertEqual(
            response.data["promotion_discount"],
            "2000.00",
        )
        self.assertEqual(response.data["total_amount"], "18000.00")
        self.assertEqual(
            response.data["items"][0]["discount_amount"],
            "2000.00",
        )
        self.assertEqual(
            response.data["items"][0]["discounted_subtotal"],
            "18000.00",
        )

    def test_fixed_promotion_is_applied_to_cart(self):
        self.create_promotion(
            products=[self.product],
            discount_type=DiscountType.FIXED,
            value=Decimal("1500.00"),
        )
        self.create_cart(quantity=2)

        self.client.force_authenticate(self.client_user)

        response = self.client.get("/api/cart/")

        self.assertEqual(
            response.data["promotion_discount"],
            "1500.00",
        )
        self.assertEqual(response.data["total_amount"], "18500.00")

    def test_only_best_promotion_is_applied(self):
        self.create_promotion(
            name="Promotion 10",
            products=[self.product],
            value=Decimal("10.00"),
        )
        self.create_promotion(
            name="Promotion 20",
            products=[self.product],
            value=Decimal("20.00"),
        )
        self.create_cart(quantity=2)

        self.client.force_authenticate(self.client_user)

        response = self.client.get("/api/cart/")

        self.assertEqual(
            response.data["promotion_discount"],
            "4000.00",
        )
        self.assertEqual(response.data["total_amount"], "16000.00")

    def test_category_and_country_targeting(self):
        self.create_promotion(
            categories=[self.category],
            countries=[self.togo],
            value=Decimal("20.00"),
        )
        self.create_cart(quantity=2)

        self.client.force_authenticate(self.client_user)

        response = self.client.get("/api/cart/?country=TG")
        self.assertEqual(
            response.data["promotion_discount"],
            "4000.00",
        )

        response = self.client.get("/api/cart/?country=FR")
        self.assertEqual(
            response.data["promotion_discount"],
            "0.00",
        )

    def test_apply_and_remove_coupon_from_cart(self):
        coupon = self.create_coupon(code="SAVE10")
        self.create_cart(quantity=2)

        self.client.force_authenticate(self.client_user)

        response = self.client.post(
            "/api/cart/coupon/",
            {"code": "save10"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["coupon"]["code"], coupon.code)
        self.assertEqual(
            response.data["coupon_discount"],
            "2000.00",
        )
        self.assertEqual(response.data["total_amount"], "18000.00")

        response = self.client.delete("/api/cart/coupon/")

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.data["coupon"])
        self.assertEqual(response.data["coupon_discount"], "0.00")

    def test_coupon_minimum_and_expiration_are_enforced(self):
        expired = self.create_coupon(
            code="EXPIRED",
            ends_at=timezone.now() - timedelta(days=1),
        )
        minimum = self.create_coupon(
            code="MINIMUM",
            minimum_amount=Decimal("50000.00"),
        )
        self.create_cart(quantity=2)

        self.client.force_authenticate(self.client_user)

        response = self.client.post(
            "/api/cart/coupon/",
            {"code": expired.code},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

        response = self.client.post(
            "/api/cart/coupon/",
            {"code": minimum.code},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_coupon_targets_only_eligible_items(self):
        coupon = self.create_coupon(
            code="PRODUCT10",
            products=[self.product],
            value=Decimal("10.00"),
        )
        cart = self.create_cart(quantity=2)
        CartItem.objects.create(
            cart=cart,
            variant=self.other_variant,
            quantity=1,
        )

        self.client.force_authenticate(self.client_user)

        response = self.client.post(
            "/api/cart/coupon/",
            {"code": coupon.code},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["subtotal"],
            "25000.00",
        )
        self.assertEqual(
            response.data["coupon_discount"],
            "2000.00",
        )
        self.assertEqual(response.data["total_amount"], "23000.00")

    def test_coupon_applies_after_promotion(self):
        self.create_promotion(
            products=[self.product],
            value=Decimal("10.00"),
        )
        self.create_coupon(code="AFTER10")
        self.create_cart(quantity=2)

        self.client.force_authenticate(self.client_user)

        response = self.client.post(
            "/api/cart/coupon/",
            {"code": "AFTER10"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data["promotion_discount"],
            "2000.00",
        )
        self.assertEqual(
            response.data["coupon_discount"],
            "1800.00",
        )
        self.assertEqual(response.data["total_amount"], "16200.00")


class OrderDiscountTests(PromotionTestBase):
    def test_order_applies_promotion_and_coupon_server_side(self):
        self.create_promotion(
            products=[self.product],
            value=Decimal("10.00"),
        )
        coupon = self.create_coupon(code="ORDER10")
        cart = self.create_cart(quantity=2)

        self.client.force_authenticate(self.client_user)

        response = self.client.post(
            "/api/orders/",
            {
                "address_id": self.address.id,
                "coupon_code": "order10",
                "discount_amount": "99999.00",
                "total_amount": "1.00",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)

        order = Order.objects.get(user=self.client_user)
        self.assertEqual(order.subtotal, Decimal("20000.00"))
        self.assertEqual(
            order.promotion_discount,
            Decimal("2000.00"),
        )
        self.assertEqual(
            order.coupon_discount,
            Decimal("1800.00"),
        )
        self.assertEqual(
            order.discount_amount,
            Decimal("3800.00"),
        )
        self.assertEqual(order.shipping_cost, Decimal("500.00"))
        self.assertEqual(order.total_amount, Decimal("16700.00"))
        self.assertEqual(order.coupon_code, coupon.code)
        self.assertEqual(
            order.discount_details["coupon"]["code"],
            coupon.code,
        )
        self.assertEqual(
            order.items.first().discount_amount,
            Decimal("2000.00"),
        )

        redemption = CouponRedemption.objects.get(order=order)
        self.assertEqual(
            redemption.discount_amount,
            Decimal("1800.00"),
        )

        cart.refresh_from_db()
        self.assertIsNone(cart.coupon)
        self.assertEqual(cart.items.count(), 0)

        self.stock.refresh_from_db()
        self.assertEqual(self.stock.reserved_quantity, 2)

    def test_coupon_max_uses_is_enforced(self):
        coupon = self.create_coupon(
            code="ONCE",
            max_uses=1,
        )
        self.create_cart(quantity=1)

        self.client.force_authenticate(self.client_user)

        response = self.client.post(
            "/api/orders/",
            {
                "address_id": self.address.id,
                "coupon_code": coupon.code,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)

        cart = Cart.objects.get(user=self.client_user)
        CartItem.objects.create(
            cart=cart,
            variant=self.other_variant,
            quantity=1,
        )

        response = self.client.post(
            "/api/orders/",
            {
                "address_id": self.address.id,
                "coupon_code": coupon.code,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            Order.objects.filter(
                user=self.client_user
            ).count(),
            1,
        )

    def test_cancelling_order_releases_coupon_use(self):
        coupon = self.create_coupon(
            code="RELEASED",
            max_uses=1,
        )
        self.create_cart(quantity=1)

        self.client.force_authenticate(self.client_user)

        response = self.client.post(
            "/api/orders/",
            {
                "address_id": self.address.id,
                "coupon_code": coupon.code,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)

        order = Order.objects.get(user=self.client_user)

        response = self.client.post(
            f"/api/orders/{order.id}/cancel/"
        )
        self.assertEqual(response.status_code, 200)

        redemption = CouponRedemption.objects.get(order=order)
        self.assertIsNotNone(redemption.released_at)

        cart = Cart.objects.get(user=self.client_user)
        CartItem.objects.create(
            cart=cart,
            variant=self.variant,
            quantity=1,
        )

        response = self.client.post(
            "/api/orders/",
            {
                "address_id": self.address.id,
                "coupon_code": coupon.code,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            Order.objects.filter(
                user=self.client_user
            ).count(),
            2,
        )

    def test_invalid_checkout_coupon_does_not_create_order(self):
        self.create_cart(quantity=1)
        self.client.force_authenticate(self.client_user)

        response = self.client.post(
            "/api/orders/",
            {
                "address_id": self.address.id,
                "coupon_code": "DOES-NOT-EXIST",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(
            Order.objects.filter(
                user=self.client_user
            ).exists()
        )


class PromotionDisplayTests(PromotionTestBase):
    def test_product_list_displays_discounted_price(self):
        self.create_promotion(
            products=[self.product],
            value=Decimal("20.00"),
        )

        response = self.client.get("/api/products/?country=TG")

        self.assertEqual(response.status_code, 200)

        item = next(
            product
            for product in response.data["results"]
            if product["id"] == self.product.id
        )

        self.assertTrue(item["has_promotion"])
        self.assertEqual(
            item["price_min_after_discount"],
            "8000.00",
        )
        self.assertEqual(
            item["price_max_after_discount"],
            "8000.00",
        )
        self.assertEqual(item["discount_percentage"], "20.00")
        self.assertEqual(
            item["promotion"]["id"],
            Promotion.objects.get().id,
        )

    def test_country_limited_promotion_is_hidden_for_other_country(self):
        self.create_promotion(
            products=[self.product],
            countries=[self.togo],
            value=Decimal("20.00"),
        )

        response = self.client.get("/api/products/?country=FR")

        item = next(
            product
            for product in response.data["results"]
            if product["id"] == self.product.id
        )

        self.assertFalse(item["has_promotion"])
        self.assertEqual(
            item["price_min_after_discount"],
            "10000.00",
        )

    def test_product_detail_displays_variant_discounts(self):
        self.create_promotion(
            products=[self.product],
            value=Decimal("10.00"),
        )

        response = self.client.get(
            f"/api/products/{self.product.id}/?country=TG"
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["has_promotion"])
        self.assertEqual(
            response.data["variants"][0]["price_after_discount"],
            "9000.00",
        )
        self.assertEqual(
            response.data["variants"][0]["discount_amount"],
            "1000.00",
        )


class PromotionNotificationTests(PromotionTestBase):
    def test_creating_active_coupon_notifies_clients(self):
        self.client.force_authenticate(self.admin_user)

        response = self.client.post(
            "/api/coupons/",
            {
                "code": "NOTIFY10",
                "discount_type": DiscountType.PERCENTAGE,
                "value": "10.00",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            Notification.objects.filter(
                user=self.client_user,
                event=Notification.Event.NEW_COUPON,
            ).exists()
        )
        self.assertFalse(
            Notification.objects.filter(
                user=self.admin_user,
                event=Notification.Event.NEW_COUPON,
            ).exists()
        )

    def test_creating_active_promotion_notifies_clients(self):
        self.client.force_authenticate(self.admin_user)

        response = self.client.post(
            "/api/promotions/",
            {
                "name": "Promotion notifiée",
                "discount_type": DiscountType.PERCENTAGE,
                "value": "15.00",
                "products": [self.product.id],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            Notification.objects.filter(
                user=self.client_user,
                event=Notification.Event.PROMOTION,
            ).exists()
        )
