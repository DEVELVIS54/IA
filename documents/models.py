from django.db import models
from django.conf import settings

class DocumentUtilisateur(models.Model):
    STATUTS = [
        ('en_attente', 'En attente'),
        ('analyse', 'Analysé'),
        ('erreur', 'Erreur'),
    ]
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='documents'
    )
    fichier = models.FileField(upload_to='documents_utilisateurs/')
    nom_original = models.CharField(max_length=255)
    taille = models.IntegerField(default=0)
    statut = models.CharField(max_length=20, choices=STATUTS, default='en_attente')
    resultat_analyse = models.TextField(blank=True)
    texte_extrait = models.TextField(blank=True)
    conversation = models.ForeignKey(
        'juridique.Conversation',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='document_source'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.utilisateur.email} - {self.nom_original}"