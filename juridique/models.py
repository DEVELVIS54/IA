from django.db import models
from django.conf import settings
from pgvector.django import VectorField

class Conversation(models.Model):
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='conversations'
    )
    titre = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.utilisateur.email} - {self.titre}"

class Message(models.Model):
    ROLES = [('user', 'Utilisateur'), ('assistant', 'Assistant')]
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='messages'
    )
    role = models.CharField(max_length=10, choices=ROLES)
    contenu = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.role} - {self.contenu[:50]}"

class DocumentJuridique(models.Model):
    CATEGORIES = [
        ('code_penal', 'Code Pénal'),
        ('code_civil', 'Code Civil'),
        ('code_travail', 'Code du Travail'),
        ('code_famille', 'Code de la Famille'),
        ('ohada', 'Droit OHADA'),
        ('uemoa', 'Règlements UEMOA'),
        ('jurisprudence', 'Jurisprudence'),
        ('constitution', 'Constitution'),
    ]
    titre = models.CharField(max_length=300)
    categorie = models.CharField(max_length=50, choices=CATEGORIES)
    fichier = models.FileField(upload_to='documents_juridiques/')
    indexe = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.titre

class ChunkDocument(models.Model):
    document = models.ForeignKey(
        DocumentJuridique,
        on_delete=models.CASCADE,
        related_name='chunks'
    )
    contenu = models.TextField()
    embedding = VectorField(dimensions=768)
    numero_page = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Chunk {self.numero_page} - {self.document.titre}"