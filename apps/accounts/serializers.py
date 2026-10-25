from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User, Role, Permission


class LoginSerializer(TokenObtainPairSerializer):

    username_field = "email"

    def validate(self, attrs):
        data = super().validate(attrs)

        user = self.user

        roles = list(
            user.roles.values_list(
                "name",
                flat=True
            )
        )

        permissions = list(
            user.roles.values_list(
                "permissions__name",
                flat=True
            ).distinct()
        )

        data["user"] = {
            "id": user.id,
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "phone": user.phone,
            "roles": roles,
            "permissions": permissions,
        }

        return data


class RegisterSerializer(serializers.ModelSerializer):


    password = serializers.CharField(
        write_only=True,
        min_length=8
    )

    password_confirmation = serializers.CharField(
        write_only=True
    )

    class Meta:
        model = User

        fields = [
            "first_name",
            "last_name",
            "email",
            "phone",
            "password",
            "password_confirmation",
        ]

    def validate_email(self, value):

        value = value.lower().strip()

        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError(
                "Cette adresse email est déjà utilisée."
            )

        return value

    def validate_phone(self, value):

        if value:
            value = value.strip()

            if User.objects.filter(phone=value).exists():
                raise serializers.ValidationError(
                    "Ce numéro de téléphone est déjà utilisé."
                )

        return value

    def validate(self, attrs):

        if attrs["password"] != attrs["password_confirmation"]:
            raise serializers.ValidationError({
                "password_confirmation": (
                    "Les mots de passe ne correspondent pas."
                )
            })

        return attrs

    def create(self, validated_data):

        validated_data.pop("password_confirmation")

        password = validated_data.pop("password")

        user = User.objects.create_user(
            password=password,
            **validated_data
        )

        client_role, _ = Role.objects.get_or_create(
            name="CLIENT",
            defaults={
                "description": (
                    "Client de la plateforme BOMBAA"
                ),
            },
        )

        user.roles.add(client_role)

        return user


class MeSerializer(serializers.ModelSerializer):

    roles = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "first_name",
            "last_name",
            "email",
            "phone",
            "is_active",
            "roles",
            "permissions",
            "created_at",
            "updated_at",
        ]

    def get_roles(self, obj):
        return list(
            obj.roles.values_list(
                "name",
                flat=True
            )
        )

    def get_permissions(self, obj):
        return list(
            obj.roles.values_list(
                "permissions__name",
                flat=True
            ).distinct()
        )


class ProfileSerializer(serializers.ModelSerializer):

    class Meta:
        model = User
        fields = [
            "id",
            "first_name",
            "last_name",
            "email",
            "phone",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "is_active",
            "created_at",
            "updated_at",
        ]

    def validate_email(self, value):
        value = value.lower().strip()

        user = self.instance

        if User.objects.filter(
            email=value
        ).exclude(
            id=user.id
        ).exists():
            raise serializers.ValidationError(
                "Cette adresse email est déjà utilisée."
            )

        return value

    def validate_phone(self, value):

        if not value:
            return None

        value = value.strip()

        user = self.instance

        if User.objects.filter(
            phone=value
        ).exclude(
            id=user.id
        ).exists():
            raise serializers.ValidationError(
                "Ce numéro de téléphone est déjà utilisé."
            )

        return value


class ChangePasswordSerializer(serializers.Serializer):

    old_password = serializers.CharField(
        write_only=True
    )

    new_password = serializers.CharField(
        write_only=True,
        min_length=8
    )

    new_password_confirmation = serializers.CharField(
        write_only=True
    )

    def validate_old_password(self, value):

        user = self.context["request"].user

        if not user.check_password(value):
            raise serializers.ValidationError(
                "L'ancien mot de passe est incorrect."
            )

        return value

    def validate(self, attrs):

        if attrs["new_password"] != attrs[
            "new_password_confirmation"
        ]:
            raise serializers.ValidationError({
                "new_password_confirmation":
                    "Les mots de passe ne correspondent pas."
            })

        if attrs["old_password"] == attrs["new_password"]:
            raise serializers.ValidationError({
                "new_password":
                    "Le nouveau mot de passe doit être différent de l'ancien."
            })

        return attrs

    def save(self):

        user = self.context["request"].user

        user.set_password(
            self.validated_data["new_password"]
        )

        user.save(
            update_fields=[
                "password",
                "updated_at"
            ]
        )

        return user


class LogoutSerializer(serializers.Serializer):

    refresh = serializers.CharField()

    def validate(self, attrs):
        self.token = attrs["refresh"]

        try:
            RefreshToken(self.token)
        except Exception:
            raise serializers.ValidationError({
                "refresh": "Le refresh token est invalide ou expiré."
            })

        return attrs

    def save(self, **kwargs):
        try:
            token = RefreshToken(self.token)
            token.blacklist()
        except Exception:
            raise serializers.ValidationError({
                "refresh": "Impossible de déconnecter cette session."
            })


class RoleSummarySerializer(serializers.ModelSerializer):

    class Meta:
        model = Role
        fields = [
            "id",
            "name",
        ]
        read_only_fields = fields


class PermissionSerializer(serializers.ModelSerializer):

    roles_count = serializers.SerializerMethodField()

    class Meta:
        model = Permission
        fields = [
            "id",
            "name",
            "description",
            "roles_count",
        ]
        read_only_fields = [
            "id",
            "roles_count",
        ]

    def get_roles_count(self, obj):
        annotated_count = getattr(
            obj,
            "roles_count",
            None,
        )

        if annotated_count is not None:
            return annotated_count

        return obj.roles.count()

    def validate_name(self, value):
        value = value.strip().lower()

        queryset = Permission.objects.filter(
            name__iexact=value
        )

        if self.instance is not None:
            queryset = queryset.exclude(
                pk=self.instance.pk
            )

        if queryset.exists():
            raise serializers.ValidationError(
                "Cette permission existe déjà."
            )

        return value


class RoleSerializer(serializers.ModelSerializer):

    permissions = serializers.PrimaryKeyRelatedField(
        queryset=Permission.objects.all(),
        many=True,
        required=False,
    )

    permissions_detail = PermissionSerializer(
        source="permissions",
        many=True,
        read_only=True,
    )

    permission_names = serializers.SerializerMethodField()
    users_count = serializers.SerializerMethodField()

    class Meta:
        model = Role
        fields = [
            "id",
            "name",
            "description",
            "permissions",
            "permissions_detail",
            "permission_names",
            "users_count",
        ]
        read_only_fields = [
            "id",
            "permissions_detail",
            "permission_names",
            "users_count",
        ]

    def get_permission_names(self, obj):
        return sorted(
            obj.permissions.values_list(
                "name",
                flat=True,
            )
        )

    def get_users_count(self, obj):
        annotated_count = getattr(
            obj,
            "users_count",
            None,
        )

        if annotated_count is not None:
            return annotated_count

        return obj.users.count()

    def validate_name(self, value):
        value = value.strip().upper()

        queryset = Role.objects.filter(
            name__iexact=value
        )

        if self.instance is not None:
            queryset = queryset.exclude(
                pk=self.instance.pk
            )

        if queryset.exists():
            raise serializers.ValidationError(
                "Ce rôle existe déjà."
            )

        return value

    def create(self, validated_data):
        permissions = validated_data.pop(
            "permissions",
            [],
        )

        role = Role.objects.create(**validated_data)
        role.permissions.set(permissions)

        return role

    def update(self, instance, validated_data):
        permissions = validated_data.pop(
            "permissions",
            None,
        )

        role = super().update(
            instance,
            validated_data,
        )

        if permissions is not None:
            role.permissions.set(permissions)

        return role


class AdminUserListSerializer(serializers.ModelSerializer):

    full_name = serializers.SerializerMethodField()
    roles = serializers.SerializerMethodField()
    orders_count = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "first_name",
            "last_name",
            "full_name",
            "email",
            "phone",
            "is_active",
            "is_staff",
            "is_superuser",
            "roles",
            "orders_count",
            "last_login",
            "created_at",
        ]
        read_only_fields = fields

    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip()

    def get_roles(self, obj):
        return sorted(
            role.name
            for role in obj.roles.all()
        )

    def get_orders_count(self, obj):
        annotated_count = getattr(
            obj,
            "orders_count",
            None,
        )

        if annotated_count is not None:
            return annotated_count

        return obj.orders.count()


class AdminUserDetailSerializer(AdminUserListSerializer):

    roles_detail = RoleSummarySerializer(
        source="roles",
        many=True,
        read_only=True,
    )

    permissions = serializers.SerializerMethodField()

    class Meta(AdminUserListSerializer.Meta):
        fields = AdminUserListSerializer.Meta.fields + [
            "roles_detail",
            "permissions",
            "updated_at",
        ]
        read_only_fields = fields

    def get_permissions(self, obj):
        permission_names = set()

        for role in obj.roles.all():
            permission_names.update(
                role.permissions.values_list(
                    "name",
                    flat=True,
                )
            )

        return sorted(permission_names)


class AdminUserCreateSerializer(serializers.ModelSerializer):

    password = serializers.CharField(
        write_only=True,
        min_length=8,
    )

    is_active = serializers.BooleanField(
        required=False,
        default=True,
    )

    roles = serializers.PrimaryKeyRelatedField(
        queryset=Role.objects.all(),
        many=True,
        required=False,
    )

    class Meta:
        model = User
        fields = [
            "first_name",
            "last_name",
            "email",
            "phone",
            "password",
            "is_active",
            "roles",
        ]

    def validate_email(self, value):
        value = value.lower().strip()

        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError(
                "Cette adresse email est déjà utilisée."
            )

        return value

    def validate_phone(self, value):
        if not value:
            return None

        value = value.strip()

        if User.objects.filter(phone=value).exists():
            raise serializers.ValidationError(
                "Ce numéro de téléphone est déjà utilisé."
            )

        return value

    def create(self, validated_data):
        roles = validated_data.pop("roles", [])
        password = validated_data.pop("password")

        if not roles:
            client_role, _created = Role.objects.get_or_create(
                name="CLIENT",
                defaults={
                    "description": (
                        "Client de la plateforme BOMBAA"
                    )
                },
            )
            roles = [client_role]

        user = User.objects.create_user(
            password=password,
            **validated_data,
        )

        user.roles.set(roles)

        return user


class AdminUserUpdateSerializer(serializers.ModelSerializer):

    roles = serializers.PrimaryKeyRelatedField(
        queryset=Role.objects.all(),
        many=True,
        required=False,
    )

    is_active = serializers.BooleanField(
        required=False,
    )

    class Meta:
        model = User
        fields = [
            "first_name",
            "last_name",
            "email",
            "phone",
            "is_active",
            "roles",
        ]

    def validate_email(self, value):
        value = value.lower().strip()

        queryset = User.objects.filter(email=value)

        if self.instance is not None:
            queryset = queryset.exclude(pk=self.instance.pk)

        if queryset.exists():
            raise serializers.ValidationError(
                "Cette adresse email est déjà utilisée."
            )

        return value

    def validate_phone(self, value):
        if not value:
            return None

        value = value.strip()

        queryset = User.objects.filter(phone=value)

        if self.instance is not None:
            queryset = queryset.exclude(pk=self.instance.pk)

        if queryset.exists():
            raise serializers.ValidationError(
                "Ce numéro de téléphone est déjà utilisé."
            )

        return value

    def validate_is_active(self, value):
        request = self.context.get("request")
        user = self.instance

        if request is None or user is None or value:
            return value

        if user.pk == request.user.pk:
            raise serializers.ValidationError(
                "Vous ne pouvez pas désactiver votre propre compte."
            )

        if user.is_superuser and not request.user.is_superuser:
            raise serializers.ValidationError(
                "Seul un superadministrateur peut désactiver "
                "ce compte."
            )

        if (
            user.is_superuser
            and user.is_active
            and not User.objects.filter(
                is_superuser=True,
                is_active=True,
            ).exclude(pk=user.pk).exists()
        ):
            raise serializers.ValidationError(
                "Impossible de désactiver le dernier "
                "superadministrateur actif."
            )

        return value

    def update(self, instance, validated_data):
        roles = validated_data.pop("roles", None)

        user = super().update(
            instance,
            validated_data,
        )

        if roles is not None:
            user.roles.set(roles)

        return user