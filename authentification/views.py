from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.throttling import AnonRateThrottle
from rest_framework_simplejwt.views import TokenObtainPairView
from django.contrib.auth import get_user_model
from .serializers import InscriptionSerializer, UserSerializer
from .serializers import CustomTokenObtainPairSerializer
from .serializers import InscriptionSerializer, UserSerializer, ChangePasswordSerializer
from rest_framework.throttling import AnonRateThrottle
from rest_framework.throttling import AnonRateThrottle
User = get_user_model()

class InscriptionRateThrottle(AnonRateThrottle):
    rate = '5/hour'

class InscriptionView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [InscriptionRateThrottle]

    def post(self, request):
        serializer = InscriptionSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            refresh = RefreshToken.for_user(user)
            return Response({
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'user': UserSerializer(user).data
            }, status=status.HTTP_201_CREATED)
        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )
class LoginRateThrottle(AnonRateThrottle):
    scope = 'login'


class CustomTokenObtainPairView(TokenObtainPairView):
    throttle_classes = [LoginRateThrottle]
    serializer_class = CustomTokenObtainPairSerializer

class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)
  
  
  
class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(
            data=request.data, context={'request': request}
        )
        if serializer.is_valid():
            request.user.set_password(serializer.validated_data['new_password'])
            request.user.save()
            return Response({'message': 'Mot de passe modifié.'})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class LoginRateThrottle(AnonRateThrottle):
    scope = 'login'