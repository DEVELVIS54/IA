from pgvector.django import CosineDistance
from google import genai
from django.conf import settings
from juridique.models import ChunkDocument, Conversation, Message
from .embedding_service import EmbeddingService

class RAGService:
    def __init__(self):
        self.embedding_service = EmbeddingService()
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)

    def rechercher_contexte(self, question, top_k=5):
        question_embedding = self.embedding_service.generer_embedding(question)
        chunks = (
            ChunkDocument.objects
            .annotate(distance=CosineDistance('embedding', question_embedding))
            .order_by('distance')[:top_k]
        )
        return chunks

    def construire_prompt(self, question, chunks, historique):
        contexte = "\n\n---\n\n".join([
            f"[{c.document.categorie.upper()}] {c.contenu}"
            for c in chunks
        ]) if chunks else "Aucun document juridique indexe pour le moment."

        historique_texte = ""
        for m in historique:
            role = "Utilisateur" if m.role == "user" else "Assistant"
            historique_texte += f"{role} : {m.contenu}\n"

        prompt = f"""Tu es un assistant juridique specialise en droit burkinabe.
Tu reponds UNIQUEMENT en francais.
Tu bases tes reponses sur les textes juridiques officiels fournis.
Tu cites toujours les articles sources utilises.
Tu rappelles que tes reponses ne remplacent pas un avis d'avocat.

Contexte juridique :
{contexte}

Historique :
{historique_texte}

Question : {question}"""

        return prompt

    def repondre(self, question, conversation):
        historique = conversation.messages.order_by('created_at')[:10]
        chunks = self.rechercher_contexte(question)
        prompt = self.construire_prompt(question, chunks, historique)

        response = self.client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt
        )

        reponse_texte = response.text

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