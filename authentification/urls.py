# Avant
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from django.urls import path
# Après
from rest_framework_simplejwt.views import TokenRefreshView
from .views import InscriptionView, MeView, CustomTokenObtainPairView

urlpatterns = [
    path('inscription/', InscriptionView.as_view()),
    path('connexion/', CustomTokenObtainPairView.as_view()),  # ← changé
    path('refresh/', TokenRefreshView.as_view()),
    path('me/', MeView.as_view()),
]