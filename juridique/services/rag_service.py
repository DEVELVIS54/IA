from pgvector.django import CosineDistance
from anthropic import Anthropic
from django.conf import settings
from django.core.cache import cache
import hashlib
import json
from juridique.models import ChunkDocument, Conversation, Message
from .embedding_service import EmbeddingService

class RAGService:
    def __init__(self):
        self.embedding_service = EmbeddingService()
        self.client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    def rechercher_contexte(self, question, top_k=5):
        # Clé de cache basée sur la question
        cache_key = f"rag_contexte:{hashlib.md5(question.encode()).hexdigest()}"

        # Vérifier le cache
        cached = cache.get(cache_key)
        if cached:
            print(f"Cache HIT pour : {question[:50]}")
            return cached

        # Pas en cache → chercher dans pgvector
        question_embedding = self.embedding_service.generer_embedding(question)
        chunks = (
            ChunkDocument.objects
            .annotate(distance=CosineDistance('embedding', question_embedding))
            .order_by('distance')
            .select_related('document')[:top_k]
        )

        # Préparer les données pour le cache
        chunks_data = [{
            'contenu': c.contenu,
            'categorie': c.document.categorie,
            'distance': float(c.distance)
        } for c in chunks]

        # Sauvegarder en cache (1 heure)
        cache.set(cache_key, chunks_data, 3600)
        print(f"Cache MISS pour : {question[:50]}")

        return chunks_data

    def construire_prompt(self, question, chunks, historique):
        contexte = "\n\n---\n\n".join([
            f"[{c['categorie'].upper()}] {c['contenu']}"
            for c in chunks
        ]) if chunks else "Aucun document juridique indexe."

        historique_texte = ""
        for m in historique:
            role = "Utilisateur" if m.role == "user" else "Assistant"
            historique_texte += f"{role} : {m.contenu}\n"

        prompt = f"""Contexte juridique :
{contexte}

Historique :
{historique_texte}

Question : {question}"""

        return prompt

    def repondre(self, question, conversation):
        # Cache de la réponse complète
        cache_key_reponse = f"rag_reponse:{hashlib.md5(question.encode()).hexdigest()}"
        cached_reponse = cache.get(cache_key_reponse)

        if cached_reponse:
            print(f"Reponse en cache pour : {question[:50]}")
            # Sauvegarder quand même dans l'historique
            Message.objects.create(
                conversation=conversation,
                role='user',
                contenu=question
            )
            Message.objects.create(
                conversation=conversation,
                role='assistant',
                contenu=cached_reponse
            )
            if not conversation.titre:
                conversation.titre = question[:100]
                conversation.save()
            return cached_reponse

        # Pas en cache → appel Claude
        historique = conversation.messages.order_by('created_at')[:10]
        chunks = self.rechercher_contexte(question)
        prompt = self.construire_prompt(question, chunks, historique)

        response = self.client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=1500,
            system="""Tu es un assistant juridique specialise en droit burkinabe.
Tu reponds UNIQUEMENT en francais.
Tu bases tes reponses sur les textes juridiques officiels fournis.
Tu cites toujours les articles sources.
Tes reponses ne remplacent pas un avis d'avocat.""",
            messages=[{"role": "user", "content": prompt}]
        )

        reponse_texte = response.content[0].text

        # Mettre en cache la réponse (1 heure)
        cache.set(cache_key_reponse, reponse_texte, 3600)

        # Sauvegarder dans l'historique
        Message.objects.create(
            conversation=conversation,
            role='user',
            contenu=question
        )
        Message.objects.create(
            conversation=conversation,
            role='assistant',
            contenu=reponse_texte
        )

        if not conversation.titre:
            conversation.titre = question[:100]
            conversation.save()

        return reponse_texte