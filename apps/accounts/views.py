from uuid import uuid4

from django.db.models import Count, Q
from django.db.models.deletion import ProtectedError

from rest_framework import status, viewsets
from rest_framework.decorators import (
    action,
    api_view,
    permission_classes,
)
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.generics import CreateAPIView

from apps.audit.models import AuditLog
from apps.audit.serializers import AuditLogSerializer
from apps.audit.services import AuditService
from apps.orders.serializers import OrderSerializer

from .models import Permission, Role, User
from .serializers import (
    AdminUserCreateSerializer,
    AdminUserDetailSerializer,
    AdminUserListSerializer,
    AdminUserUpdateSerializer,
    ChangePasswordSerializer,
    LoginSerializer,
    LogoutSerializer,
    MeSerializer,
    PermissionSerializer,
    ProfileSerializer,
    RegisterSerializer,
    RoleSerializer,
)
        
from .permissions import HasPermission



class RegisterView(CreateAPIView):

    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]


class LoginView(TokenObtainPairView):

    serializer_class = LoginSerializer


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me_view(request):

    serializer = MeSerializer(request.user)

    return Response(serializer.data)



@api_view(["GET", "PUT", "PATCH"])
@permission_classes([IsAuthenticated])
def profile_view(request):

    user = request.user

    if request.method == "GET":
        serializer = ProfileSerializer(user)

        return Response(
            serializer.data,
            status=status.HTTP_200_OK
        )

    serializer = ProfileSerializer(
        user,
        data=request.data,
        partial=request.method == "PATCH"
    )

    if serializer.is_valid():
        serializer.save()

        return Response(
            serializer.data,
            status=status.HTTP_200_OK
        )

    return Response(
        serializer.errors,
        status=status.HTTP_400_BAD_REQUEST
    )



@api_view(["POST"])
@permission_classes([IsAuthenticated])
def change_password_view(request):

    serializer = ChangePasswordSerializer(
        data=request.data,
        context={
            "request": request
        }
    )

    if serializer.is_valid():
        serializer.save()

        return Response({
            "message": "Mot de passe modifié avec succès."
        })

    return Response(
        serializer.errors,
        status=status.HTTP_400_BAD_REQUEST
    )

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout_view(request):

    serializer = LogoutSerializer(
        data=request.data
    )

    if serializer.is_valid():
        serializer.save()

        return Response({
            "message": "Déconnexion réussie."
        })

    return Response(
        serializer.errors,
        status=status.HTTP_400_BAD_REQUEST
    )


@api_view(["GET"])
@permission_classes([
    HasPermission("products.view")
])
def test_products_view(request):

    return Response({
        "message": "Vous avez accès aux produits."
    })


@api_view(["POST"])
@permission_classes([
    HasPermission("products.create")
])
def test_products_create(request):

    return Response(
        {
            "message": "Produit créé avec succès."
        },
        status=status.HTTP_201_CREATED
    )


class AdminUserViewSet(viewsets.ModelViewSet):
    """
    Gestion administrative des comptes clients et administrateurs.
    """

    queryset = (
        User.objects
        .prefetch_related("roles__permissions")
        .annotate(
            orders_count=Count(
                "orders",
                distinct=True,
            )
        )
    )

    def get_serializer_class(self):
        if self.action == "create":
            return AdminUserCreateSerializer

        if self.action in [
            "update",
            "partial_update",
        ]:
            return AdminUserUpdateSerializer

        if self.action == "list":
            return AdminUserListSerializer

        return AdminUserDetailSerializer

    def get_permissions(self):
        if self.action in [
            "list",
            "retrieve",
            "orders",
            "activities",
        ]:
            permission = "users.view"

        elif self.action == "create":
            permission = "users.create"

        elif self.action in [
            "update",
            "partial_update",
            "activate",
            "deactivate",
        ]:
            permission = "users.update"

        elif self.action == "destroy":
            permission = "users.delete"

        else:
            permission = "users.view"

        return [HasPermission(permission)()]

    def get_queryset(self):
        queryset = super().get_queryset()

        search = self.request.query_params.get("search")

        if search:
            queryset = queryset.filter(
                Q(email__icontains=search)
                | Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
                | Q(phone__icontains=search)
            )

        role = self.request.query_params.get("role")

        if role:
            role = role.strip()

            if role.isdigit():
                queryset = queryset.filter(
                    roles__id=int(role)
                )
            else:
                queryset = queryset.filter(
                    roles__name__iexact=role
                )

            queryset = queryset.distinct()

        for field in [
            "is_active",
            "is_staff",
            "is_superuser",
        ]:
            value = self.request.query_params.get(field)

            if value is None:
                continue

            normalized = value.strip().lower()

            if normalized not in {
                "true",
                "false",
                "1",
                "0",
            }:
                return queryset.none()

            queryset = queryset.filter(**{
                field: normalized in {"true", "1"}
            })

        return queryset.order_by("-created_at")

    def get_object(self):
        user = super().get_object()

        if (
            self.action in [
                "update",
                "partial_update",
                "destroy",
                "activate",
                "deactivate",
            ]
            and user.is_superuser
            and not self.request.user.is_superuser
        ):
            raise PermissionDenied(
                "Seul un superadministrateur peut modifier "
                "ce compte."
            )

        return user

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)

        headers = self.get_success_headers(serializer.data)

        detail = AdminUserDetailSerializer(
            serializer.instance,
            context=self.get_serializer_context(),
        )

        return Response(
            detail.data,
            status=status.HTTP_201_CREATED,
            headers=headers,
        )

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()

        serializer = self.get_serializer(
            instance,
            data=request.data,
            partial=partial,
        )
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        detail = AdminUserDetailSerializer(
            serializer.instance,
            context=self.get_serializer_context(),
        )

        return Response(detail.data)

    def perform_create(self, serializer):
        user = serializer.save()

        AuditService.log(
            action=AuditLog.Action.CREATE,
            actor=self.request.user,
            target=user,
            metadata={
                "roles": sorted(
                    user.roles.values_list(
                        "name",
                        flat=True,
                    )
                )
            },
            request=self.request,
        )

    def perform_update(self, serializer):
        user = serializer.instance

        before = {
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email": user.email,
            "phone": user.phone,
            "is_active": user.is_active,
            "roles": sorted(
                user.roles.values_list(
                    "name",
                    flat=True,
                )
            ),
        }

        user = serializer.save()

        after = {
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email": user.email,
            "phone": user.phone,
            "is_active": user.is_active,
            "roles": sorted(
                user.roles.values_list(
                    "name",
                    flat=True,
                )
            ),
        }

        changes = {
            field: {
                "before": before[field],
                "after": after[field],
            }
            for field in before
            if before[field] != after[field]
        }

        if before["is_active"] == after["is_active"]:
            action = AuditLog.Action.UPDATE
        elif after["is_active"]:
            action = AuditLog.Action.ACTIVATE
        else:
            action = AuditLog.Action.DEACTIVATE

        AuditService.log(
            action=action,
            actor=self.request.user,
            target=user,
            changes=changes,
            request=self.request,
        )

    def destroy(self, request, *args, **kwargs):
        user = self.get_object()

        if user.pk == request.user.pk:
            return Response(
                {
                    "detail": (
                        "Vous ne pouvez pas supprimer "
                        "votre propre compte."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if self._is_last_active_superuser(user):
            return Response(
                {
                    "detail": (
                        "Impossible de supprimer le dernier "
                        "superadministrateur actif."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        user_id = user.pk
        user_email = user.email
        mode = "deleted"

        try:
            user.delete()

        except ProtectedError:
            # Les commandes et paiements doivent être conservés.
            # Le compte est donc anonymisé et désactivé.
            user.first_name = "Compte"
            user.last_name = "Supprimé"
            user.email = (
                f"deleted-{user_id}-{uuid4().hex[:8]}"
                "@bombaa.invalid"
            )
            user.phone = None
            user.is_active = False
            user.is_staff = False
            user.is_superuser = False
            user.set_unusable_password()
            user.roles.clear()
            user.save()
            mode = "anonymized"

        AuditService.log(
            action=AuditLog.Action.DELETE,
            actor=request.user,
            target_type="accounts.user",
            target_id=str(user_id),
            target_repr=user_email,
            metadata={"mode": mode},
            request=request,
        )

        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(
        detail=True,
        methods=["post", "patch"],
        url_path="activate",
    )
    def activate(self, request, pk=None):
        user = self.get_object()

        if not user.is_active:
            previous_value = user.is_active
            user.is_active = True
            user.save(
                update_fields=[
                    "is_active",
                    "updated_at",
                ]
            )

            AuditService.log(
                action=AuditLog.Action.ACTIVATE,
                actor=request.user,
                target=user,
                changes={
                    "is_active": {
                        "before": previous_value,
                        "after": user.is_active,
                    }
                },
                request=request,
            )

        serializer = AdminUserDetailSerializer(
            user,
            context=self.get_serializer_context(),
        )

        return Response(serializer.data)

    @action(
        detail=True,
        methods=["post", "patch"],
        url_path="deactivate",
    )
    def deactivate(self, request, pk=None):
        user = self.get_object()

        if user.pk == request.user.pk:
            return Response(
                {
                    "detail": (
                        "Vous ne pouvez pas désactiver "
                        "votre propre compte."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if self._is_last_active_superuser(user):
            return Response(
                {
                    "detail": (
                        "Impossible de désactiver le dernier "
                        "superadministrateur actif."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if user.is_active:
            previous_value = user.is_active
            user.is_active = False
            user.save(
                update_fields=[
                    "is_active",
                    "updated_at",
                ]
            )

            AuditService.log(
                action=AuditLog.Action.DEACTIVATE,
                actor=request.user,
                target=user,
                changes={
                    "is_active": {
                        "before": previous_value,
                        "after": user.is_active,
                    }
                },
                request=request,
            )

        serializer = AdminUserDetailSerializer(
            user,
            context=self.get_serializer_context(),
        )

        return Response(serializer.data)

    @action(
        detail=True,
        methods=["get"],
        url_path="orders",
    )
    def orders(self, request, pk=None):
        user = self.get_object()

        queryset = (
            user.orders
            .select_related(
                "shipping_address",
                "delivery__shipping_method",
            )
            .prefetch_related("items")
            .order_by("-created_at")
        )

        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = OrderSerializer(
                page,
                many=True,
            )
            return self.get_paginated_response(
                serializer.data
            )

        serializer = OrderSerializer(
            queryset,
            many=True,
        )

        return Response(serializer.data)

    @action(
        detail=True,
        methods=["get"],
        url_path="activities",
    )
    def activities(self, request, pk=None):
        user = self.get_object()

        queryset = (
            AuditLog.objects
            .select_related("actor")
            .filter(
                Q(actor=user)
                | Q(
                    target_type="accounts.user",
                    target_id=str(user.pk),
                )
            )
            .order_by("-created_at")
        )

        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = AuditLogSerializer(
                page,
                many=True,
            )
            return self.get_paginated_response(
                serializer.data
            )

        serializer = AuditLogSerializer(
            queryset,
            many=True,
        )

        return Response(serializer.data)

    @staticmethod
    def _is_last_active_superuser(user):
        if not user.is_superuser or not user.is_active:
            return False

        return not (
            User.objects
            .filter(
                is_superuser=True,
                is_active=True,
            )
            .exclude(pk=user.pk)
            .exists()
        )


class RoleViewSet(viewsets.ModelViewSet):
    """
    Gestion des rôles et de leurs permissions.
    """

    serializer_class = RoleSerializer

    def get_queryset(self):
        queryset = (
            Role.objects
            .prefetch_related("permissions")
            .annotate(
                users_count=Count(
                    "users",
                    distinct=True,
                )
            )
        )

        search = self.request.query_params.get("search")

        if search:
            queryset = queryset.filter(
                Q(name__icontains=search)
                | Q(description__icontains=search)
            )

        return queryset.order_by("name")

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            permission = "roles.view"

        elif self.action == "create":
            permission = "roles.create"

        elif self.action in [
            "update",
            "partial_update",
        ]:
            permission = "roles.update"

        elif self.action == "destroy":
            permission = "roles.delete"

        else:
            permission = "roles.view"

        return [HasPermission(permission)()]

    def perform_create(self, serializer):
        role = serializer.save()

        AuditService.log(
            action=AuditLog.Action.CREATE,
            actor=self.request.user,
            target=role,
            metadata={
                "permissions": sorted(
                    role.permissions.values_list(
                        "name",
                        flat=True,
                    )
                )
            },
            request=self.request,
        )

    def perform_update(self, serializer):
        role = serializer.instance

        before = {
            "name": role.name,
            "description": role.description,
            "permissions": sorted(
                role.permissions.values_list(
                    "name",
                    flat=True,
                )
            ),
        }

        role = serializer.save()

        after = {
            "name": role.name,
            "description": role.description,
            "permissions": sorted(
                role.permissions.values_list(
                    "name",
                    flat=True,
                )
            ),
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
            actor=self.request.user,
            target=role,
            changes=changes,
            request=self.request,
        )

    def destroy(self, request, *args, **kwargs):
        role = self.get_object()

        if role.user_roles.exists():
            return Response(
                {
                    "detail": (
                        "Ce rôle est assigné à au moins "
                        "un utilisateur."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        role_id = role.pk
        role_name = role.name

        role.delete()

        AuditService.log(
            action=AuditLog.Action.DELETE,
            actor=request.user,
            target_type="accounts.role",
            target_id=str(role_id),
            target_repr=role_name,
            request=request,
        )

        return Response(status=status.HTTP_204_NO_CONTENT)


class PermissionViewSet(viewsets.ModelViewSet):
    """
    Gestion des permissions disponibles pour les rôles.
    """

    serializer_class = PermissionSerializer

    def get_queryset(self):
        queryset = Permission.objects.annotate(
            roles_count=Count(
                "roles",
                distinct=True,
            )
        )

        search = self.request.query_params.get("search")

        if search:
            queryset = queryset.filter(
                Q(name__icontains=search)
                | Q(description__icontains=search)
            )

        return queryset.order_by("name")

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            permission = "permissions.view"

        elif self.action == "create":
            permission = "permissions.create"

        elif self.action in [
            "update",
            "partial_update",
        ]:
            permission = "permissions.update"

        elif self.action == "destroy":
            permission = "permissions.delete"

        else:
            permission = "permissions.view"

        return [HasPermission(permission)()]

    def perform_create(self, serializer):
        permission = serializer.save()

        AuditService.log(
            action=AuditLog.Action.CREATE,
            actor=self.request.user,
            target=permission,
            request=self.request,
        )

    def perform_update(self, serializer):
        permission = serializer.instance

        before = {
            "name": permission.name,
            "description": permission.description,
        }

        permission = serializer.save()

        after = {
            "name": permission.name,
            "description": permission.description,
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
            actor=self.request.user,
            target=permission,
            changes=changes,
            request=self.request,
        )

    def destroy(self, request, *args, **kwargs):
        permission = self.get_object()

        if permission.role_permissions.exists():
            return Response(
                {
                    "detail": (
                        "Cette permission est assignée à "
                        "au moins un rôle."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        permission_id = permission.pk
        permission_name = permission.name

        permission.delete()

        AuditService.log(
            action=AuditLog.Action.DELETE,
            actor=request.user,
            target_type="accounts.permission",
            target_id=str(permission_id),
            target_repr=permission_name,
            request=request,
        )

        return Response(status=status.HTTP_204_NO_CONTENT)


