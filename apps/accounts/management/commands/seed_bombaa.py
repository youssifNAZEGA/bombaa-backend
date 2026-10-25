
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from apps.stocks.models import Stock, StockMovement
from apps.accounts.models import User, Role
from apps.addresses.models import Address
from apps.catalog.models import (
    Category,
    Brand,
    Product,
    ProductCategory,
    ProductImage,
    Attribute,
    AttributeValue,
    ProductVariant,
    VariantAttributeValue,
    
)
from apps.payments.models import PaymentMethod, Payment,Transaction
from apps.geography.models import Country, Currency
from apps.shipping.models import (
    Delivery,
    ShippingMethod,
    ShippingRate,
    ShippingZone,
)
from apps.cart.models import Cart, CartItem
from apps.wishlist.models import Wishlist, WishlistItem
from apps.orders.models import Order, OrderAddress, OrderItem
from apps.notifications.models import (
    Notification,
    NotificationPreference,
)
from apps.promotions.models import Coupon, Promotion
from decimal import Decimal

class Command(BaseCommand):
    help = "Peuple la base de données BOMBAA avec les données de développement."

    @transaction.atomic
    def handle(self, *args, **options):

        self.stdout.write(
            self.style.MIGRATE_HEADING(
                "=== SEED BOMBAA ==="
            )
        )

        self.seed_users()
        self.seed_catalog()
        self.seed_payment_methods()
        self.seed_geography()
        self.seed_shipping()
        self.seed_products()
        self.seed_stocks()
        self.seed_promotions()
        self.seed_addresses()
        self.seed_carts()
        self.seed_wishlists()
        self.seed_orders()
        self.seed_deliveries()
        self.seed_payments()
        self.seed_notifications()


        self.stdout.write(
            self.style.SUCCESS(
                "\n✓ Peuplement BOMBAA terminé avec succès."
            )
        )

    # ==========================================================
    # USERS
    # ==========================================================

    def seed_users(self):

        admin_role = Role.objects.get(
            name="ADMIN"
        )

        client_role = Role.objects.get(
            name="CLIENT"
        )

        admin, created = User.objects.get_or_create(
            email="admin@bombaa.com",
            defaults={
                "first_name": "Admin",
                "last_name": "BOMBAA",
                "phone": "+22890000001",
                "is_active": True,
                "is_staff": True,
                "is_superuser": True,
            },
        )

        if created:
            admin.set_password("Admin12345!")
            admin.save()

        admin.roles.add(admin_role)

        self.stdout.write(
            self.style.SUCCESS(
                "✓ Administrateur : admin@bombaa.com"
            )
        )

        clients = [
            {
                "email": "client1@bombaa.com",
                "first_name": "Koffi",
                "last_name": "Mensah",
                "phone": "+22890000002",
            },
            {
                "email": "client2@bombaa.com",
                "first_name": "Ama",
                "last_name": "Kossi",
                "phone": "+22890000003",
            },
            {
                "email": "client3@bombaa.com",
                "first_name": "Yao",
                "last_name": "Adjei",
                "phone": "+22890000004",
            },
        ]

        for data in clients:

            user, created = User.objects.get_or_create(
                email=data["email"],
                defaults={
                    "first_name": data["first_name"],
                    "last_name": data["last_name"],
                    "phone": data["phone"],
                    "is_active": True,
                },
            )

            if created:
                user.set_password(
                    "Client12345!"
                )
                user.save()

            user.roles.add(client_role)

            self.stdout.write(
                f"  → {user.email}"
            )



    def seed_addresses(self):
        addresses = [
            {
                "email": "client1@bombaa.com",
                "label": "Maison",
                "first_name": "Koffi",
                "last_name": "Mensah",
                "phone": "+22890000002",
                "address_line_1": "12 Rue des Cocotiers",
                "address_line_2": "",
                "city": "Lomé",
                "state": "Golfe",
                "postal_code": "01 BP 1234",
                "country": "Togo",
                "is_default": True,
            },
            {
                "email": "client1@bombaa.com",
                "label": "Bureau",
                "first_name": "Koffi",
                "last_name": "Mensah",
                "phone": "+22890000002",
                "address_line_1": "45 Boulevard du 30 Août",
                "address_line_2": "",
                "city": "Lomé",
                "state": "Golfe",
                "postal_code": "01 BP 5678",
                "country": "Togo",
                "is_default": False,
            },

            {
                "email": "client2@bombaa.com",
                "label": "Maison",
                "first_name": "Ama",
                "last_name": "Kossi",
                "phone": "+22890000003",
                "address_line_1": "18 Rue de la Paix",
                "address_line_2": "",
                "city": "Lomé",
                "state": "Golfe",
                "postal_code": "01 BP 2345",
                "country": "Togo",
                "is_default": True,
            },
            {
                "email": "client2@bombaa.com",
                "label": "Travail",
                "first_name": "Ama",
                "last_name": "Kossi",
                "phone": "+22890000003",
                "address_line_1": "10 Avenue de la Libération",
                "address_line_2": "",
                "city": "Lomé",
                "state": "Golfe",
                "postal_code": "01 BP 6789",
                "country": "Togo",
                "is_default": False,
            },

            {
                "email": "client3@bombaa.com",
                "label": "Maison",
                "first_name": "Yao",
                "last_name": "Adjei",
                "phone": "+22890000004",
                "address_line_1": "7 Rue de la Marina",
                "address_line_2": "",
                "city": "Lomé",
                "state": "Golfe",
                "postal_code": "01 BP 3456",
                "country": "Togo",
                "is_default": True,
            },
            {
                "email": "client3@bombaa.com",
                "label": "Famille",
                "first_name": "Yao",
                "last_name": "Adjei",
                "phone": "+22890000004",
                "address_line_1": "25 Route de Baguida",
                "address_line_2": "",
                "city": "Lomé",
                "state": "Golfe",
                "postal_code": "01 BP 7890",
                "country": "Togo",
                "is_default": False,
            },
        ]

        countries = {
            country.name.lower(): country
            for country in Country.objects.all()
        }

        for data in addresses:
            user = User.objects.get(email=data["email"])
            country_ref = countries.get(
                data["country"].strip().lower()
            )

            # On cherche une adresse existante avec le même label
            address = Address.objects.filter(
                user=user,
                label=data["label"],
            ).first()

            if address:
                for field, value in data.items():
                    if field != "email":
                        setattr(address, field, value)

                address.country_ref = country_ref
                address.save()
            else:
                Address.objects.create(
                    user=user,
                    label=data["label"],
                    first_name=data["first_name"],
                    last_name=data["last_name"],
                    phone=data["phone"],
                    address_line_1=data["address_line_1"],
                    address_line_2=data["address_line_2"],
                    city=data["city"],
                    state=data["state"],
                    postal_code=data["postal_code"],
                    country=data["country"],
                    country_ref=country_ref,
                    is_default=data["is_default"],
                )

        # Sécurité : une seule adresse par client est définie comme principale
        for email in [
            "client1@bombaa.com",
            "client2@bombaa.com",
            "client3@bombaa.com",
        ]:
            user = User.objects.get(email=email)

            default_addresses = Address.objects.filter(
                user=user,
                is_default=True,
            ).order_by("created_at")

            if default_addresses.exists():
                first_default = default_addresses.first()

                Address.objects.filter(
                    user=user,
                    is_default=True,
                ).exclude(
                    id=first_default.id
                ).update(is_default=False)

        self.stdout.write(
            self.style.SUCCESS("Adresses de test créées/mises à jour.")
        )

    # ==========================================================
    # CATALOG
    # ==========================================================

    def seed_catalog(self):

        categories = [
            {
                "name": "Vêtements",
                "slug": "vetements",
                "description": "Vêtements pour hommes et femmes.",
            },
            {
                "name": "Chaussures",
                "slug": "chaussures",
                "description": "Chaussures et baskets.",
            },
            {
                "name": "Accessoires",
                "slug": "accessoires",
                "description": "Accessoires de mode.",
            },
            {
                "name": "Électronique",
                "slug": "electronique",
                "description": "Produits électroniques.",
            },
            {
                "name": "Beauté",
                "slug": "beaute",
                "description": "Produits de beauté.",
            },
            {
                "name": "Maison",
                "slug": "maison",
                "description": "Produits pour la maison.",
            },
        ]

        for data in categories:

            category, _ = Category.objects.update_or_create(
                slug=data["slug"],
                defaults={
                    "name": data["name"],
                    "description": data["description"],
                    "is_active": True,
                },
            )

            self.stdout.write(
                f"  → Catégorie : {category.name}"
            )

        brands = [
            {
                "name": "BOMBAA",
                "description": "Marque officielle BOMBAA.",
            },
            {
                "name": "Nike",
                "description": "Articles de sport et de mode.",
            },
            {
                "name": "Adidas",
                "description": "Articles de sport et de mode.",
            },
            {
                "name": "Samsung",
                "description": "Produits électroniques.",
            },
        ]

        for data in brands:

            brand, _ = Brand.objects.update_or_create(
                name=data["name"],
                defaults={
                    "description": data["description"],
                    "is_active": True,
                },
            )

            self.stdout.write(
                f"  → Marque : {brand.name}"
            )

        attributes = {
            "Couleur": [
                "Noir",
                "Blanc",
                "Rouge",
                "Bleu",
                "Vert",
            ],
            "Taille": [
                "XS",
                "S",
                "M",
                "L",
                "XL",
                "XXL",
            ],
            "Pointure": [
                "38",
                "39",
                "40",
                "41",
                "42",
                "43",
                "44",
            ],
            "Matière": [
                "Coton",
                "Polyester",
                "Cuir",
                "Denim",
            ],
            "Capacité": [
                "64 Go",
                "128 Go",
                "256 Go",
                "512 Go",
            ],
        }

        for attribute_name, values in attributes.items():

            attribute, _ = Attribute.objects.update_or_create(
                name=attribute_name
            )

            for value in values:

                AttributeValue.objects.update_or_create(
                    attribute=attribute,
                    value=value,
                )

            self.stdout.write(
                f"  → Attribut : {attribute_name}"
            )

    # ==========================================================
    # PAYMENT METHODS
    # ==========================================================

    def seed_payment_methods(self):

        methods = [
            {
                "name": "Mobile Money",
                "code": "MOBILE_MONEY",
                "description": (
                    "Paiement par services Mobile Money."
                ),
            },
            {
                "name": "Carte bancaire",
                "code": "CARD",
                "description": (
                    "Paiement par carte bancaire."
                ),
            },
            {
                "name": "Virement bancaire",
                "code": "BANK_TRANSFER",
                "description": (
                    "Paiement par virement bancaire."
                ),
            },
            {
                "name": "Paiement à la livraison",
                "code": "CASH_ON_DELIVERY",
                "description": (
                    "Paiement à la livraison."
                ),
            },
        ]

        for data in methods:

            method, _ = PaymentMethod.objects.update_or_create(
                code=data["code"],
                defaults={
                    "name": data["name"],
                    "description": data["description"],
                    "is_active": True,
                },
            )

            self.stdout.write(
                f"  → Paiement : {method.name}"
            )

    # ==========================================================
    # PAYS / DEVISES
    # ==========================================================

    def seed_geography(self):

        currencies = [
            {
                "code": "XOF",
                "name": "Franc CFA",
                "symbol": "FCFA",
                "exchange_rate": Decimal("1.000000"),
                "is_base": True,
            },
            {
                "code": "EUR",
                "name": "Euro",
                "symbol": "€",
                "exchange_rate": Decimal("655.957000"),
                "is_base": False,
            },
            {
                "code": "USD",
                "name": "Dollar américain",
                "symbol": "$",
                "exchange_rate": Decimal("600.000000"),
                "is_base": False,
            },
            {
                "code": "GBP",
                "name": "Livre sterling",
                "symbol": "£",
                "exchange_rate": Decimal("770.000000"),
                "is_base": False,
            },
        ]

        currency_by_code = {}

        for data in currencies:
            currency, _ = Currency.objects.update_or_create(
                code=data["code"],
                defaults={
                    "name": data["name"],
                    "symbol": data["symbol"],
                    "exchange_rate": data["exchange_rate"],
                    "is_base": data["is_base"],
                    "is_active": True,
                },
            )
            currency_by_code[currency.code] = currency

        countries = [
            {
                "name": "Togo",
                "code": "TG",
                "phone_code": "+228",
                "currency": "XOF",
            },
            {
                "name": "Bénin",
                "code": "BJ",
                "phone_code": "+229",
                "currency": "XOF",
            },
            {
                "name": "Côte d'Ivoire",
                "code": "CI",
                "phone_code": "+225",
                "currency": "XOF",
            },
            {
                "name": "Sénégal",
                "code": "SN",
                "phone_code": "+221",
                "currency": "XOF",
            },
            {
                "name": "France",
                "code": "FR",
                "phone_code": "+33",
                "currency": "EUR",
            },
        ]

        country_by_code = {}

        for data in countries:
            country, _ = Country.objects.update_or_create(
                code=data["code"],
                defaults={
                    "name": data["name"],
                    "phone_code": data["phone_code"],
                    "currency": currency_by_code[data["currency"]],
                    "is_active": True,
                },
            )
            country_by_code[country.code] = country

        methods = {
            method.code: method
            for method in PaymentMethod.objects.all()
        }

        country_payment_methods = {
            "TG": ["MOBILE_MONEY", "CASH_ON_DELIVERY"],
            "BJ": ["MOBILE_MONEY", "CASH_ON_DELIVERY"],
            "CI": ["MOBILE_MONEY", "CASH_ON_DELIVERY"],
            "SN": ["MOBILE_MONEY", "CASH_ON_DELIVERY"],
            "FR": ["CARD", "BANK_TRANSFER"],
        }

        for country_code, method_codes in country_payment_methods.items():
            country = country_by_code[country_code]

            country.payment_methods.set([
                methods[code]
                for code in method_codes
                if code in methods
            ])

        self.stdout.write(
            self.style.SUCCESS(
                "Devises et pays de test créés/mis à jour."
            )
        )

    # ==========================================================
    # LIVRAISON
    # ==========================================================

    def seed_shipping(self):

        xof = Currency.objects.get(code="XOF")

        methods = {}

        for data in [
            {
                "name": "Livraison standard",
                "code": "STANDARD",
                "description": "Livraison économique.",
                "carrier": "BOMBAA Logistics",
                "estimated_days": 3,
            },
            {
                "name": "Livraison express",
                "code": "EXPRESS",
                "description": "Livraison rapide.",
                "carrier": "BOMBAA Logistics",
                "estimated_days": 1,
            },
        ]:
            method, _ = ShippingMethod.objects.update_or_create(
                code=data["code"],
                defaults={
                    "name": data["name"],
                    "description": data["description"],
                    "carrier": data["carrier"],
                    "estimated_days": data["estimated_days"],
                    "is_active": True,
                },
            )
            methods[method.code] = method

        zones = {}

        for data in [
            {
                "name": "Togo",
                "country_codes": ["TG"],
            },
            {
                "name": "Afrique de l'Ouest",
                "country_codes": ["BJ", "CI", "SN"],
            },
            {
                "name": "Europe",
                "country_codes": ["FR"],
            },
            {
                "name": "International",
                "country_codes": [],
            },
        ]:
            zone, _ = ShippingZone.objects.update_or_create(
                name=data["name"],
                defaults={"is_active": True},
            )
            zone.countries.set(
                Country.objects.filter(
                    code__in=data["country_codes"]
                )
            )
            zones[zone.name] = zone

        rates = [
            # Togo
            ("Togo", "STANDARD", 0, 1000, "1500.00"),
            ("Togo", "STANDARD", 1001, 5000, "2500.00"),
            ("Togo", "STANDARD", 5001, None, "4000.00"),
            ("Togo", "EXPRESS", 0, 5000, "4000.00"),
            ("Togo", "EXPRESS", 5001, None, "6000.00"),
            # Afrique de l'Ouest
            ("Afrique de l'Ouest", "STANDARD", 0, 5000, "5000.00"),
            ("Afrique de l'Ouest", "STANDARD", 5001, None, "7500.00"),
            ("Afrique de l'Ouest", "EXPRESS", 0, 5000, "8000.00"),
            # Europe
            ("Europe", "STANDARD", 0, 5000, "10000.00"),
            ("Europe", "STANDARD", 5001, None, "15000.00"),
            ("Europe", "EXPRESS", 0, 5000, "20000.00"),
            # International
            ("International", "STANDARD", 0, 5000, "25000.00"),
            ("International", "STANDARD", 5001, None, "35000.00"),
            ("International", "EXPRESS", 0, 5000, "40000.00"),
        ]

        for (
            zone_name,
            method_code,
            min_weight,
            max_weight,
            price,
        ) in rates:
            ShippingRate.objects.update_or_create(
                zone=zones[zone_name],
                method=methods[method_code],
                min_weight_grams=min_weight,
                max_weight_grams=max_weight,
                defaults={
                    "price": Decimal(price),
                    "currency": xof,
                    "is_active": True,
                },
            )

        self.stdout.write(
            self.style.SUCCESS(
                "Zones, modes et tarifs de livraison créés/mis à jour."
            )
        )

    # ==========================================================
    # PRODUCTS / VARIANTS
    # ==========================================================

    def seed_products(self):

        categories = {
            category.slug: category
            for category in Category.objects.all()
        }

        brands = {
            brand.name: brand
            for brand in Brand.objects.all()
        }

        attributes = {
            attribute.name: attribute
            for attribute in Attribute.objects.prefetch_related("values")
        }

        def get_attribute_value(attribute_name, value):
            attribute = attributes[attribute_name]

            return AttributeValue.objects.get(
                attribute=attribute,
                value=value,
            )

        products = [
            {
                "name": "T-shirt BOMBAA Classic",
                "slug": "t-shirt-bombaa-classic",
                "description": (
                    "T-shirt BOMBAA confortable et polyvalent "
                    "pour un usage quotidien."
                ),
                "base_price": "8500.00",
                "brand": "BOMBAA",
                "categories": ["vetements"],
                "images": [
                    (
                        "https://example.com/products/"
                        "tshirt-bombaa-classic-noir.jpg",
                        "T-shirt BOMBAA Classic noir",
                        True,
                    ),
                    (
                        "https://example.com/products/"
                        "tshirt-bombaa-classic-blanc.jpg",
                        "T-shirt BOMBAA Classic blanc",
                        False,
                    ),
                ],
                "variants": [
                    {
                        "sku": "BOMBAA-TSH-NOIR-M",
                        "price": "8500.00",
                        "attributes": {
                            "Couleur": "Noir",
                            "Taille": "M",
                        },
                    },
                    {
                        "sku": "BOMBAA-TSH-NOIR-L",
                        "price": "8500.00",
                        "attributes": {
                            "Couleur": "Noir",
                            "Taille": "L",
                        },
                    },
                    {
                        "sku": "BOMBAA-TSH-BLANC-M",
                        "price": "8500.00",
                        "attributes": {
                            "Couleur": "Blanc",
                            "Taille": "M",
                        },
                    },
                ],
            },
            {
                "name": "Jean BOMBAA Premium",
                "slug": "jean-bombaa-premium",
                "description": (
                    "Jean BOMBAA premium avec une coupe moderne "
                    "et confortable."
                ),
                "base_price": "18000.00",
                "brand": "BOMBAA",
                "categories": ["vetements"],
                "images": [
                    (
                        "https://example.com/products/"
                        "jean-bombaa-premium.jpg",
                        "Jean BOMBAA Premium",
                        True,
                    ),
                ],
                "variants": [
                    {
                        "sku": "BOMBAA-JEAN-BLEU-40",
                        "price": "18000.00",
                        "attributes": {
                            "Couleur": "Bleu",
                            "Taille": "M",
                        },
                    },
                    {
                        "sku": "BOMBAA-JEAN-BLEU-42",
                        "price": "18000.00",
                        "attributes": {
                            "Couleur": "Bleu",
                            "Taille": "L",
                        },
                    },
                ],
            },
            {
                "name": "Nike Air Max",
                "slug": "nike-air-max",
                "description": (
                    "Chaussures Nike Air Max pour un style "
                    "sportif et moderne."
                ),
                "base_price": "65000.00",
                "brand": "Nike",
                "categories": ["chaussures"],
                "images": [
                    (
                        "https://example.com/products/"
                        "nike-air-max-noir.jpg",
                        "Nike Air Max noir",
                        True,
                    ),
                    (
                        "https://example.com/products/"
                        "nike-air-max-blanc.jpg",
                        "Nike Air Max blanc",
                        False,
                    ),
                ],
                "variants": [
                    {
                        "sku": "NIKE-AIRMAX-NOIR-42",
                        "price": "65000.00",
                        "attributes": {
                            "Couleur": "Noir",
                            "Pointure": "42",
                        },
                    },
                    {
                        "sku": "NIKE-AIRMAX-BLANC-43",
                        "price": "65000.00",
                        "attributes": {
                            "Couleur": "Blanc",
                            "Pointure": "43",
                        },
                    },
                ],
            },
            {
                "name": "Adidas Superstar",
                "slug": "adidas-superstar",
                "description": (
                    "Adidas Superstar classique adaptée "
                    "à un usage quotidien."
                ),
                "base_price": "55000.00",
                "brand": "Adidas",
                "categories": ["chaussures"],
                "images": [
                    (
                        "https://example.com/products/"
                        "adidas-superstar.jpg",
                        "Adidas Superstar",
                        True,
                    ),
                ],
                "variants": [
                    {
                        "sku": "ADIDAS-SUPERSTAR-BLANC-41",
                        "price": "55000.00",
                        "attributes": {
                            "Couleur": "Blanc",
                            "Pointure": "41",
                        },
                    },
                    {
                        "sku": "ADIDAS-SUPERSTAR-NOIR-42",
                        "price": "55000.00",
                        "attributes": {
                            "Couleur": "Noir",
                            "Pointure": "42",
                        },
                    },
                ],
            },
            {
                "name": "Sac BOMBAA Urban",
                "slug": "sac-bombaa-urban",
                "description": (
                    "Sac BOMBAA Urban pratique pour "
                    "les déplacements quotidiens."
                ),
                "base_price": "22000.00",
                "brand": "BOMBAA",
                "categories": ["accessoires"],
                "images": [
                    (
                        "https://example.com/products/"
                        "sac-bombaa-urban.jpg",
                        "Sac BOMBAA Urban",
                        True,
                    ),
                ],
                "variants": [
                    {
                        "sku": "BOMBAA-SAC-NOIR",
                        "price": "22000.00",
                        "attributes": {
                            "Couleur": "Noir",
                            "Matière": "Cuir",
                        },
                    },
                    {
                        "sku": "BOMBAA-SAC-BLEU",
                        "price": "22000.00",
                        "attributes": {
                            "Couleur": "Bleu",
                            "Matière": "Cuir",
                        },
                    },
                ],
            },
            {
                "name": "Samsung Galaxy 128 Go",
                "slug": "samsung-galaxy-128-go",
                "description": (
                    "Smartphone Samsung Galaxy avec "
                    "128 Go de stockage."
                ),
                "base_price": "175000.00",
                "brand": "Samsung",
                "categories": ["electronique"],
                "images": [
                    (
                        "https://example.com/products/"
                        "samsung-galaxy-128.jpg",
                        "Samsung Galaxy 128 Go",
                        True,
                    ),
                ],
                "variants": [
                    {
                        "sku": "SAMSUNG-GALAXY-128-NOIR",
                        "price": "175000.00",
                        "attributes": {
                            "Couleur": "Noir",
                            "Capacité": "128 Go",
                        },
                    },
                    {
                        "sku": "SAMSUNG-GALAXY-128-BLANC",
                        "price": "175000.00",
                        "attributes": {
                            "Couleur": "Blanc",
                            "Capacité": "128 Go",
                        },
                    },
                ],
            },
            {
                "name": "Samsung Galaxy 256 Go",
                "slug": "samsung-galaxy-256-go",
                "description": (
                    "Smartphone Samsung Galaxy avec "
                    "256 Go de stockage."
                ),
                "base_price": "210000.00",
                "brand": "Samsung",
                "categories": ["electronique"],
                "images": [
                    (
                        "https://example.com/products/"
                        "samsung-galaxy-256.jpg",
                        "Samsung Galaxy 256 Go",
                        True,
                    ),
                ],
                "variants": [
                    {
                        "sku": "SAMSUNG-GALAXY-256-NOIR",
                        "price": "210000.00",
                        "attributes": {
                            "Couleur": "Noir",
                            "Capacité": "256 Go",
                        },
                    },
                    {
                        "sku": "SAMSUNG-GALAXY-256-BLEU",
                        "price": "210000.00",
                        "attributes": {
                            "Couleur": "Bleu",
                            "Capacité": "256 Go",
                        },
                    },
                ],
            },
        ]

        for data in products:

            product, _ = Product.objects.update_or_create(
                slug=data["slug"],
                defaults={
                    "name": data["name"],
                    "description": data["description"],
                    "base_price": data["base_price"],
                    "brand": brands[data["brand"]],
                    "is_active": True,
                },
            )

            # --------------------------------------------------
            # CATEGORIES
            # --------------------------------------------------

            ProductCategory.objects.filter(
                product=product
            ).delete()

            for category_slug in data["categories"]:

                ProductCategory.objects.create(
                    product=product,
                    category=categories[category_slug],
                )

            # --------------------------------------------------
            # IMAGES
            # --------------------------------------------------

            ProductImage.objects.filter(
                product=product
            ).delete()

            for image_url, alt_text, is_primary in data["images"]:

                ProductImage.objects.create(
                    product=product,
                    image_url=image_url,
                    alt_text=alt_text,
                    is_primary=is_primary,
                )

            # --------------------------------------------------
            # VARIANTS
            # --------------------------------------------------

            for variant_data in data["variants"]:

                variant, _ = ProductVariant.objects.update_or_create(
                    sku=variant_data["sku"],
                    defaults={
                        "product": product,
                        "price": variant_data["price"],
                        "is_active": True,
                    },
                )

                # Supprimer les anciennes associations
                VariantAttributeValue.objects.filter(
                    variant=variant
                ).delete()

                # Ajouter les nouveaux attributs
                for (
                    attribute_name,
                    value,
                ) in variant_data["attributes"].items():

                    attribute_value = get_attribute_value(
                        attribute_name,
                        value,
                    )

                    VariantAttributeValue.objects.create(
                        variant=variant,
                        attribute_value=attribute_value,
                    )

            self.stdout.write(
                self.style.SUCCESS(
                    f"  → Produit : {product.name}"
                )
            )

    # ==========================================================
    # STOCKS
    # ==========================================================

    def seed_stocks(self):

        variants = ProductVariant.objects.select_related(
            "product"
        ).order_by("id")

        # Quantités de stock initiales
        stock_quantities = {
            "BOMBAA-TSH-NOIR-M": 50,
            "BOMBAA-TSH-NOIR-L": 40,
            "BOMBAA-TSH-BLANC-M": 35,

            "BOMBAA-JEAN-BLEU-40": 25,
            "BOMBAA-JEAN-BLEU-42": 20,

            "NIKE-AIRMAX-NOIR-42": 15,
            "NIKE-AIRMAX-BLANC-43": 12,

            "ADIDAS-SUPERSTAR-BLANC-41": 18,
            "ADIDAS-SUPERSTAR-NOIR-42": 14,

            "BOMBAA-SAC-NOIR": 30,
            "BOMBAA-SAC-BLEU": 25,

            "SAMSUNG-GALAXY-128-NOIR": 10,
            "SAMSUNG-GALAXY-128-BLANC": 8,

            "SAMSUNG-GALAXY-256-NOIR": 7,
            "SAMSUNG-GALAXY-256-BLEU": 6,
        }

        for variant in variants:

            quantity = stock_quantities.get(
                variant.sku,
                10,
            )

            stock, created = Stock.objects.update_or_create(
                variant=variant,
                defaults={
                    "quantity": quantity,
                    "reserved_quantity": 0,
                    "minimum_quantity": 5,
                },
            )

            # --------------------------------------------------
            # STOCK INITIAL
            # --------------------------------------------------

            if created:

                StockMovement.objects.create(
                    stock=stock,
                    movement_type=StockMovement.MOVEMENT_IN,
                    quantity=quantity,
                    reason="Stock initial",
                )

            self.stdout.write(
                self.style.SUCCESS(
                    f"  → Stock : "
                    f"{variant.sku} = {stock.quantity}"
                )
            )

        self.stdout.write(
            self.style.SUCCESS(
                "✓ Stocks et mouvements initiaux créés."
            )
        )

    def seed_promotions(self):

        now = timezone.now()

        clothing_category = Category.objects.filter(
            slug="vetements"
        ).first()

        classic_tshirt = Product.objects.filter(
            slug="t-shirt-bombaa-classic"
        ).first()

        togo = Country.objects.filter(code="TG").first()

        promotion, created = Promotion.objects.update_or_create(
            name="Promotion BOMBAA -10 %",
            defaults={
                "description": (
                    "Profitez de 10 % de réduction sur "
                    "la collection BOMBAA."
                ),
                "discount_type": "PERCENTAGE",
                "value": Decimal("10.00"),
                "starts_at": now - timedelta(days=1),
                "ends_at": now + timedelta(days=30),
                "is_active": True,
            },
        )

        promotion.products.clear()
        promotion.categories.clear()
        promotion.brands.clear()
        promotion.countries.clear()

        if clothing_category is not None:
            promotion.categories.add(clothing_category)

        if classic_tshirt is not None:
            promotion.products.add(classic_tshirt)

        if togo is not None:
            promotion.countries.add(togo)

        coupon, created = Coupon.objects.update_or_create(
            code="BOMBAA10",
            defaults={
                "description": (
                    "Coupon de bienvenue BOMBAA : -10 % "
                    "dès 10 000 XOF d'achat."
                ),
                "discount_type": "PERCENTAGE",
                "value": Decimal("10.00"),
                "minimum_amount": Decimal("10000.00"),
                "max_uses": 500,
                "starts_at": now - timedelta(days=1),
                "ends_at": now + timedelta(days=90),
                "is_active": True,
            },
        )

        coupon.products.clear()
        coupon.categories.clear()
        coupon.countries.clear()

        if clothing_category is not None:
            coupon.categories.add(clothing_category)

        if togo is not None:
            coupon.countries.add(togo)

        self.stdout.write(
            self.style.SUCCESS(
                f"  → Promotion : {promotion.name}"
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"  → Coupon : {coupon.code}"
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                "✓ Promotions et coupons de démonstration créés."
            )
        )

    def seed_carts(self):
        cart_data = {
            "client1@bombaa.com": [
                ("BOMBAA-TSH-NOIR-M", 2),
                ("NIKE-AIRMAX-NOIR-42", 1),
            ],
            "client2@bombaa.com": [
                ("BOMBAA-JEAN-BLEU-40", 1),
                ("BOMBAA-SAC-NOIR", 1),
            ],
            "client3@bombaa.com": [
                ("SAMSUNG-GALAXY-128-NOIR", 1),
                ("ADIDAS-SUPERSTAR-BLANC-41", 2),
            ],
        }

        for email, items in cart_data.items():
            user = User.objects.get(email=email)

            cart, created = Cart.objects.get_or_create(
                user=user
            )

            for sku, quantity in items:
                variant = ProductVariant.objects.get(sku=sku)

                CartItem.objects.update_or_create(
                    cart=cart,
                    variant=variant,
                    defaults={
                        "quantity": quantity,
                    },
                )

        self.stdout.write(
            self.style.SUCCESS("Paniers de test créés/mis à jour.")
        )

    def seed_wishlists(self):
        wishlist_data = {
            "client1@bombaa.com": [
                "ADIDAS-SUPERSTAR-BLANC-41",
                "SAMSUNG-GALAXY-256-NOIR",
            ],
            "client2@bombaa.com": [
                "BOMBAA-TSH-BLANC-M",
                "NIKE-AIRMAX-BLANC-43",
            ],
            "client3@bombaa.com": [
                "BOMBAA-JEAN-BLEU-42",
                "BOMBAA-SAC-BLEU",
            ],
        }

        for email, skus in wishlist_data.items():
            user = User.objects.get(email=email)

            wishlist, created = Wishlist.objects.get_or_create(
                user=user
            )

            for sku in skus:
                variant = ProductVariant.objects.get(sku=sku)

                WishlistItem.objects.get_or_create(
                    wishlist=wishlist,
                    variant=variant,
                )

        self.stdout.write(
            self.style.SUCCESS("Wishlists de test créées/mises à jour.")
        )

    def seed_orders(self):
        orders_data = [
            {
                "reference": "CMD-SEED-000001",
                "email": "client1@bombaa.com",
                "address_label": "Maison",
                "status": Order.Status.PENDING,
                "items": [
                    ("BOMBAA-TSH-NOIR-M", 2),
                ],
                "shipping_cost": Decimal("1500.00"),
                "discount_amount": Decimal("0.00"),
            },
            {
                "reference": "CMD-SEED-000002",
                "email": "client2@bombaa.com",
                "address_label": "Maison",
                "status": Order.Status.CONFIRMED,
                "items": [
                    ("BOMBAA-JEAN-BLEU-40", 1),
                    ("BOMBAA-SAC-NOIR", 1),
                ],
                "shipping_cost": Decimal("2000.00"),
                "discount_amount": Decimal("1000.00"),
            },
            {
                "reference": "CMD-SEED-000003",
                "email": "client3@bombaa.com",
                "address_label": "Maison",
                "status": Order.Status.PROCESSING,
                "items": [
                    ("SAMSUNG-GALAXY-128-NOIR", 1),
                ],
                "shipping_cost": Decimal("2500.00"),
                "discount_amount": Decimal("0.00"),
            },
        ]

        for data in orders_data:
            user = User.objects.get(email=data["email"])

            address = Address.objects.get(
                user=user,
                label=data["address_label"],
            )

            # Vérifier si la commande existe déjà
            existing_order = Order.objects.filter(
                reference=data["reference"]
            ).first()

            if existing_order:
                self.stdout.write(
                    f"Commande existante conservée : {existing_order.reference}"
                )
                continue

            # ---------------------------------------------------------
            # 1. Calcul du subtotal AVANT création de la commande
            # ---------------------------------------------------------
            prepared_items = []
            subtotal = Decimal("0.00")

            for sku, quantity in data["items"]:
                variant = ProductVariant.objects.select_related(
                    "product"
                ).get(sku=sku)

                unit_price = variant.price
                item_subtotal = unit_price * quantity

                subtotal += item_subtotal

                prepared_items.append({
                    "variant": variant,
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "subtotal": item_subtotal,
                })

            # ---------------------------------------------------------
            # 2. Calcul du total
            # ---------------------------------------------------------
            shipping_cost = data["shipping_cost"]
            discount_amount = data["discount_amount"]

            total_amount = (
                subtotal
                + shipping_cost
                - discount_amount
            )

            # Sécurité
            if total_amount < Decimal("0.00"):
                raise ValueError(
                    f"Le total de la commande {data['reference']} "
                    f"ne peut pas être négatif."
                )

            # ---------------------------------------------------------
            # 3. Création de la commande
            # ---------------------------------------------------------
            order = Order.objects.create(
                user=user,
                reference=data["reference"],
                status=data["status"],
                subtotal=subtotal,
                shipping_cost=shipping_cost,
                discount_amount=discount_amount,
                total_amount=total_amount,
                currency="XOF",
                notes="Commande de test générée par seed_bombaa.",
            )

            # ---------------------------------------------------------
            # 4. Création des lignes de commande
            # ---------------------------------------------------------
            for item in prepared_items:
                variant = item["variant"]

                OrderItem.objects.create(
                    order=order,
                    variant=variant,
                    product_name=variant.product.name,
                    variant_description=f"SKU: {variant.sku}",
                    sku=variant.sku,
                    quantity=item["quantity"],
                    unit_price=item["unit_price"],
                    subtotal=item["subtotal"],
                )

            # ---------------------------------------------------------
            # 5. Création de l'adresse snapshot
            # ---------------------------------------------------------
            OrderAddress.objects.create(
                order=order,
                recipient_name=(
                    f"{address.first_name} {address.last_name}"
                ),
                phone=address.phone,
                address_line1=address.address_line_1,
                address_line2=address.address_line_2,
                city=address.city,
                state=address.state,
                postal_code=address.postal_code,
                country_name=address.country,
                country_code="TG",
            )

            self.stdout.write(
                self.style.SUCCESS(
                    f"Commande créée : {order.reference} "
                    f"| Total : {order.total_amount} XOF"
                )
            )

        self.stdout.write(
            self.style.SUCCESS(
                "Commandes de test créées/mises à jour."
            )
        )
        
    def seed_deliveries(self):
        method = ShippingMethod.objects.filter(
            code="STANDARD"
        ).first()

        if method is None:
            self.stdout.write(
                self.style.WARNING(
                    "Aucun mode de livraison standard : "
                    "livraisons de test ignorées."
                )
            )
            return

        delivery_statuses = {
            Order.Status.PENDING: Delivery.Status.PENDING,
            Order.Status.CONFIRMED: Delivery.Status.PREPARING,
            Order.Status.PROCESSING: Delivery.Status.PREPARING,
        }

        for reference in [
            "CMD-SEED-000001",
            "CMD-SEED-000002",
            "CMD-SEED-000003",
        ]:
            order = Order.objects.filter(
                reference=reference
            ).first()

            if order is None:
                continue

            delivery, created = Delivery.objects.get_or_create(
                order=order,
                defaults={
                    "shipping_method": method,
                    "status": delivery_statuses.get(
                        order.status,
                        Delivery.Status.PENDING,
                    ),
                    "estimated_delivery_date": (
                        timezone.localdate()
                        + timedelta(days=method.estimated_days)
                    ),
                    "tracking_number": (
                        f"BOMBAA-{order.reference}"
                        if order.status in [
                            Order.Status.CONFIRMED,
                            Order.Status.PROCESSING,
                        ]
                        else None
                    ),
                },
            )

            if (
                not created
                and delivery.shipping_method_id is None
            ):
                delivery.shipping_method = method
                delivery.estimated_delivery_date = (
                    timezone.localdate()
                    + timedelta(days=method.estimated_days)
                )
                delivery.save(
                    update_fields=[
                        "shipping_method",
                        "estimated_delivery_date",
                        "updated_at",
                    ]
                )

            self.stdout.write(
                f"  → Livraison : {order.reference} "
                f"({delivery.status})"
            )

        self.stdout.write(
            self.style.SUCCESS(
                "Livraisons de test créées/mises à jour."
            )
        )

    def seed_payments(self):
        payments_data = [
            {
                "order_reference": "CMD-SEED-000001",
                "method_code": "MOBILE_MONEY",
                "status": Payment.Status.PENDING,
            },
            {
                "order_reference": "CMD-SEED-000002",
                "method_code": "CARD",
                "status": Payment.Status.SUCCESS,
            },
            {
                "order_reference": "CMD-SEED-000003",
                "method_code": "MOBILE_MONEY",
                "status": Payment.Status.PROCESSING,
            },
        ]

        for data in payments_data:
            order = Order.objects.get(
                reference=data["order_reference"]
            )

            payment_method = PaymentMethod.objects.get(
                code=data["method_code"]
            )

            payment, created = Payment.objects.get_or_create(
                reference=f"PAY-SEED-{order.id:06d}",
                defaults={
                    "order": order,
                    "payment_method": payment_method,
                    "amount": order.total_amount,
                    "currency": order.currency,
                    "status": data["status"],
                },
            )

            if not created:
                payment.status = data["status"]

                if data["status"] == Payment.Status.SUCCESS:
                    payment.paid_at = timezone.now()

                payment.save(
                    update_fields=[
                        "status",
                        "paid_at",
                        "updated_at",
                    ]
                )

            transaction, transaction_created = Transaction.objects.get_or_create(
                payment=payment,
                defaults={
                    "reference": f"TXN-SEED-{payment.id:06d}",
                    "external_reference": (
                        f"SEED-EXT-{payment.id:06d}"
                        if data["status"] == Payment.Status.SUCCESS
                        else None
                    ),
                    "amount": payment.amount,
                    "currency": payment.currency,
                    "status": (
                        Transaction.Status.SUCCESS
                        if data["status"] == Payment.Status.SUCCESS
                        else Transaction.Status.PENDING
                    ),
                    "response_message": "Transaction générée par seed_bombaa.",
                },
            )

        self.stdout.write(
            self.style.SUCCESS("Paiements et transactions de test créés/mis à jour.")
        )

    def seed_notifications(self):
        for user in User.objects.all():
            NotificationPreference.objects.get_or_create(
                user=user,
            )

        status_events = {
            Order.Status.CONFIRMED: [
                Notification.Event.PAYMENT_CONFIRMED,
                Notification.Event.ORDER_CONFIRMED,
            ],
            Order.Status.PROCESSING: [
                Notification.Event.PAYMENT_CONFIRMED,
                Notification.Event.ORDER_CONFIRMED,
                Notification.Event.ORDER_PROCESSING,
            ],
        }

        for order in Order.objects.filter(
            reference__startswith="CMD-SEED-"
        ).select_related("user"):
            self.create_seed_notification(
                user=order.user,
                event=Notification.Event.ORDER_CREATED,
                title="Commande créée",
                message=(
                    f"Votre commande {order.reference} "
                    "a bien été créée."
                ),
                order=order,
            )

            for event in status_events.get(order.status, []):
                self.create_seed_notification(
                    user=order.user,
                    event=event,
                    title=event.label,
                    message=(
                        f"Le statut de votre commande "
                        f"{order.reference} a été mis à jour."
                    ),
                    order=order,
                )

        self.stdout.write(
            self.style.SUCCESS(
                "Notifications de démonstration créées/mises à jour."
            )
        )

    @staticmethod
    def create_seed_notification(
        *,
        user,
        event,
        title,
        message,
        order=None,
    ):
        notification = Notification.objects.filter(
            user=user,
            event=event,
            order=order,
        ).first()

        if notification is not None:
            return notification

        return Notification.objects.create(
            user=user,
            event=event,
            title=title,
            message=message,
            order=order,
            data=(
                {
                    "order_id": order.id,
                    "reference": order.reference,
                }
                if order is not None
                else {}
            ),
        )