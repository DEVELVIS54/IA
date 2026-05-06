from rest_framework import serializers
from .models import DocumentUtilisateur

class DocumentUploadSerializer(serializers.ModelSerializer):
    fichier = serializers.FileField()

    class Meta:
        model = DocumentUtilisateur
        fields = ['fichier']

    def validate_fichier(self, value):
        # Vérifier que c'est un PDF
        if not value.name.endswith('.pdf'):
            raise serializers.ValidationError("Seuls les fichiers PDF sont acceptés.")

        # Vérifier la taille max 10MB
        if value.size > 10 * 1024 * 1024:
            raise serializers.ValidationError("Fichier trop volumineux (max 10MB).")

        return value

class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentUtilisateur
        fields = ['id', 'nom_original', 'taille', 'statut', 'resultat_analyse', 'created_at']