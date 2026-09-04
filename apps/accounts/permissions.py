from rest_framework.permissions import BasePermission

from .models import User


def user_has_permission(user: User, permission_name: str) -> bool:
    """
    Vérifie si un utilisateur possède une permission
    via l'un de ses rôles.
    """

    if not user.is_active:
        return False

    return user.roles.filter(
        permissions__name=permission_name
    ).exists()


def user_has_any_permission(
    user: User,
    *permission_names: str
) -> bool:
    """
    Vérifie si l'utilisateur possède au moins
    une des permissions fournies.
    """

    if not user.is_active:
        return False

    return user.roles.filter(
        permissions__name__in=permission_names
    ).exists()


def user_has_all_permissions(
    user: User,
    *permission_names: str
) -> bool:
    """
    Vérifie si l'utilisateur possède toutes
    les permissions fournies.
    """

    if not user.is_active:
        return False

    user_permissions = set(
        user.roles.values_list(
            "permissions__name",
            flat=True
        )
    )

    return set(permission_names).issubset(user_permissions)


def HasPermission(permission_name: str):
    """
    Factory permettant de créer une permission DRF
    nécessitant une permission BOMBAA précise.
    """

    class PermissionClass(BasePermission):

        message = (
            f"Vous n'avez pas la permission : "
            f"{permission_name}"
        )

        def has_permission(self, request, view):
            if not request.user or not request.user.is_authenticated:
                return False

            return user_has_permission(
                request.user,
                permission_name
            )

    return PermissionClass