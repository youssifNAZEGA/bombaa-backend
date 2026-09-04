from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.generics import CreateAPIView

from .serializers import (
    LoginSerializer, 
    RegisterSerializer, 
    MeSerializer,
    ProfileSerializer,
    ChangePasswordSerializer,
    LogoutSerializer
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


