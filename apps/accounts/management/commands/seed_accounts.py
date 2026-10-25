from django.core.management.base import BaseCommand

from apps.accounts.models import Role, Permission


class Command(BaseCommand):

    help = "Initialise les rôles et permissions de BOMBAA"

    def handle(self, *args, **options):

        permissions = [
            # Utilisateurs
            ("users.view", "Consulter les utilisateurs"),
            ("users.create", "Créer un utilisateur"),
            ("users.update", "Modifier un utilisateur"),
            ("users.delete", "Supprimer un utilisateur"),

            # Rôles
            ("roles.view", "Consulter les rôles"),
            ("roles.create", "Créer un rôle"),
            ("roles.update", "Modifier un rôle"),
            ("roles.delete", "Supprimer un rôle"),

            # Permissions
            ("permissions.view", "Consulter les permissions"),
            ("permissions.create", "Créer une permission"),
            ("permissions.update", "Modifier une permission"),
            ("permissions.delete", "Supprimer une permission"),

            # Catégories
            ("categories.view", "Consulter les catégories"),
            ("categories.create", "Créer une catégorie"),
            ("categories.update", "Modifier une catégorie"),
            ("categories.delete", "Supprimer une catégorie"),

            #Brands
            ("brands.view", "Consulter les marques"),
            ("brands.create","Créer une marque"),
            ("brands.update","Modifier une marque"),
            ("brands.delete", "Supprimer une marque"),

            # Produits
            ("products.view", "Consulter les produits"),
            ("products.create", "Créer un produit"),
            ("products.update", "Modifier un produit"),
            ("products.delete", "Supprimer un produit"),

            # Commandes
            ("orders.view", "Consulter les commandes"),
            ("orders.create", "Créer une commande"),
            ("orders.update", "Modifier une commande"),
            ("orders.delete", "Supprimer une commande"),

            # Paiements
            ("payments.view", "Consulter les paiements"),
            ("payments.create", "Créer un paiement"),
            ("payments.update", "Modifier un paiement"),

            # Pays
            ("countries.view", "Consulter les pays"),
            ("countries.create", "Créer un pays"),
            ("countries.update", "Modifier un pays"),
            ("countries.delete", "Supprimer un pays"),

            # Devises
            ("currencies.view", "Consulter les devises"),
            ("currencies.create", "Créer une devise"),
            ("currencies.update", "Modifier une devise"),
            ("currencies.delete", "Supprimer une devise"),

            # Livraison
            ("shipping.view", "Consulter la livraison"),
            ("shipping.create", "Créer un paramètre de livraison"),
            ("shipping.update", "Modifier la livraison"),
            ("shipping.delete", "Supprimer un paramètre de livraison"),

            # Avis
            ("reviews.view", "Consulter les avis"),
            ("reviews.create", "Créer un avis"),
            ("reviews.update", "Modifier un avis"),
            ("reviews.delete", "Supprimer un avis"),

            # Retours
            ("returns.view", "Consulter les retours"),
            ("returns.create", "Créer un retour"),
            ("returns.update", "Modifier un retour"),

            # Remboursements
            ("refunds.view", "Consulter les remboursements"),
            ("refunds.create", "Créer un remboursement"),
            ("refunds.update", "Modifier un remboursement"),

            # Promotions
            ("promotions.view", "Consulter les promotions"),
            ("promotions.create", "Créer une promotion"),
            ("promotions.update", "Modifier une promotion"),
            ("promotions.delete", "Supprimer une promotion"),

            # Coupons
            ("coupons.view", "Consulter les coupons"),
            ("coupons.create", "Créer un coupon"),
            ("coupons.update", "Modifier un coupon"),
            ("coupons.delete", "Supprimer un coupon"),

            # Notifications
            ("notifications.view", "Consulter les notifications"),
            ("notifications.create", "Créer une notification"),

            # Tableau de bord
            ("dashboard.view", "Consulter le tableau de bord"),

            # Journal d'activité
            ("audit.view", "Consulter le journal d'activité"),

            # Support
            ("support.view", "Consulter le support"),
            ("support.create", "Créer un ticket support"),
            ("support.update", "Modifier un ticket support"),
        ]

        permission_objects = {}

        for name, description in permissions:
            permission, created = Permission.objects.get_or_create(
                name=name,
                defaults={
                    "description": description
                }
            )

            permission_objects[name] = permission

            if created:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Permission créée : {name}"
                    )
                )

        # ==========================
        # RÔLE ADMIN
        # ==========================

        admin_role, created = Role.objects.get_or_create(
            name="ADMIN",
            defaults={
                "description": "Administrateur de la plateforme BOMBAA"
            }
        )

        if created:
            self.stdout.write(
                self.style.SUCCESS("Rôle ADMIN créé")
            )

        admin_role.permissions.set(
            permission_objects.values()
        )

        # ==========================
        # RÔLE CLIENT
        # ==========================

        client_role, created = Role.objects.get_or_create(
            name="CLIENT",
            defaults={
                "description": "Client de la plateforme BOMBAA"
            }
        )

        if created:
            self.stdout.write(
                self.style.SUCCESS("Rôle CLIENT créé")
            )

        client_permission_names = [
            "products.view",
            "categories.view",

            "countries.view",
            "currencies.view",
            "shipping.view",

            "orders.view",
            "orders.create",

            "payments.view",
            "payments.create",

            "reviews.view",
            "reviews.create",
            "reviews.update",
            "reviews.delete",

            "returns.view",
            "returns.create",

            "refunds.view",

            "notifications.view",

            "support.view",
            "support.create",
            "support.update",
        ]

        client_role.permissions.set(
            permission_objects[name]
            for name in client_permission_names
        )

        # ==========================
        # RÔLES ADMINISTRATEURS SPÉCIALISÉS
        # ==========================

        specialized_roles = {
            "PRODUCT_MANAGER": {
                "description": (
                    "Gestion du catalogue et des produits"
                ),
                "permissions": [
                    "categories.view",
                    "categories.create",
                    "categories.update",
                    "categories.delete",
                    "brands.view",
                    "brands.create",
                    "brands.update",
                    "brands.delete",
                    "products.view",
                    "products.create",
                    "products.update",
                    "products.delete",
                    "dashboard.view",
                ],
            },
            "ORDER_MANAGER": {
                "description": (
                    "Gestion et suivi des commandes"
                ),
                "permissions": [
                    "orders.view",
                    "orders.update",
                    "payments.view",
                    "users.view",
                    "shipping.view",
                    "notifications.view",
                    "dashboard.view",
                ],
            },
            "STOCK_MANAGER": {
                "description": (
                    "Gestion des stocks et des disponibilités"
                ),
                "permissions": [
                    "products.view",
                    "products.update",
                    "dashboard.view",
                ],
            },
            "DELIVERY_MANAGER": {
                "description": (
                    "Gestion des livraisons et des zones"
                ),
                "permissions": [
                    "shipping.view",
                    "shipping.create",
                    "shipping.update",
                    "shipping.delete",
                    "orders.view",
                    "countries.view",
                    "currencies.view",
                    "dashboard.view",
                ],
            },
            "FINANCE_MANAGER": {
                "description": (
                    "Gestion des paiements et remboursements"
                ),
                "permissions": [
                    "orders.view",
                    "payments.view",
                    "payments.update",
                    "refunds.view",
                    "refunds.create",
                    "refunds.update",
                    "dashboard.view",
                ],
            },
            "SUPPORT_MANAGER": {
                "description": (
                    "Gestion du service client et du support"
                ),
                "permissions": [
                    "users.view",
                    "orders.view",
                    "notifications.view",
                    "support.view",
                    "support.create",
                    "support.update",
                    "dashboard.view",
                ],
            },
            "MARKETING_MANAGER": {
                "description": (
                    "Gestion des promotions, coupons et "
                    "communications marketing"
                ),
                "permissions": [
                    "products.view",
                    "categories.view",
                    "brands.view",
                    "promotions.view",
                    "promotions.create",
                    "promotions.update",
                    "promotions.delete",
                    "coupons.view",
                    "coupons.create",
                    "coupons.update",
                    "coupons.delete",
                    "notifications.view",
                    "notifications.create",
                    "dashboard.view",
                ],
            },
        }

        for role_name, role_data in specialized_roles.items():
            role, created = Role.objects.get_or_create(
                name=role_name,
                defaults={
                    "description": role_data["description"],
                },
            )

            if created:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Rôle {role_name} créé"
                    )
                )

            role.permissions.set(
                permission_objects[name]
                for name in role_data["permissions"]
            )

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                " Rôles et permissions BOMBAA initialisés avec succès."
            )
        )