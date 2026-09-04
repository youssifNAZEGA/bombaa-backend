from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User, Role


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

        client_role = Role.objects.get(
            name="CLIENT"
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