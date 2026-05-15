from rest_framework import serializers
from django.contrib.auth import get_user_model

User = get_user_model()

class InscriptionSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ['email', 'password']

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Cet email est déjà utilisé.")
        return value

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['email'],
            email=validated_data['email'],
            password=validated_data['password']
        )
        return user

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'email', 'created_at']
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import authenticate

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    username_field = 'email'

    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')

        # Cherche l'utilisateur par email
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError("Email ou mot de passe incorrect.")

        # Vérifie le mot de passe
        if not user.check_password(password):
            raise serializers.ValidationError("Email ou mot de passe incorrect.")

        if not user.is_active:
            raise serializers.ValidationError("Compte inactif.")

        refresh = self.get_token(user)
        return {
            'access': str(refresh.access_token),
            'refresh': str(refresh),
        }
        
class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, min_length=6)

    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Mot de passe actuel incorrect.")
        return value