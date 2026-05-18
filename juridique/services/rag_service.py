# juridique/services/rag_service.py
import hashlib
from django.core.cache import cache
from openai import OpenAI
from django.conf import settings
from pgvector.django import CosineDistance
from juridique.models import ChunkDocument, Message
from .embedding_service import EmbeddingService

SYSTEM_PROMPT = """Tu es FasoX IA, un assistant juridique conversationnel spécialisé en droit burkinabè.

═══════════════════════════════════════
PERSONNALITÉ
═══════════════════════════════════════
- Tu es chaleureux, professionnel et accessible
- Tu converses naturellement comme un humain
- Tu utilises "je", "nous", tu poses des questions de clarification si besoin
- Tu mémorises le fil de la conversation et tu y fais référence
- Tu réponds TOUJOURS en français

═══════════════════════════════════════
COMPORTEMENT SELON LE TYPE DE MESSAGE
═══════════════════════════════════════

1. CONVERSATION GÉNÉRALE (salutations, remerciements, questions personnelles) :
   → Réponds naturellement et chaleureusement, comme un humain

2. QUESTIONS JURIDIQUES (droit du travail, pénal, civil, foncier, commercial...) :
   → Réponds en professionnel avec tes connaissances en droit burkinabè
   → Si des documents pertinents sont fournis, base-toi dessus en priorité
   → Cite les articles de référence (ex: "Selon l'Art. 71 du Code du travail...")
   → Structure ta réponse clairement
   → Conclus par : "⚠️ Cette information est donnée à titre indicatif et ne remplace pas l'avis d'un juriste qualifié."

3. QUESTIONS HORS CONTEXTE JURIDIQUE :
   → Décline poliment et redirige vers le juridique

═══════════════════════════════════════
RÈGLES DE QUALITÉ
═══════════════════════════════════════
- Ne recopie JAMAIS les textes bruts des documents
- Analyse, synthétise et explique en termes simples
- Si tu n'es pas sûr, dis-le honnêtement"""

SIMILARITY_THRESHOLD = 0.48

MOTS_HORS_CONTEXTE = [
    'météo', 'cuisine', 'recette', 'sport', 'football', 'musique',
    'film', 'cinéma', 'jeu', 'voyage', 'tourisme', 'santé', 'médecin',
    'informatique', 'programmation', 'crypto', 'bitcoin', 'blague'
]


class RAGService:
    def __init__(self):
        self.embedding_service = EmbeddingService()
        self.client = OpenAI(
            api_key=settings.GROQ_API_KEY,
            base_url="https://api.groq.com/openai/v1"
        )
        self.model = "llama-3.3-70b-versatile"

    def _est_hors_contexte(self, question: str) -> bool:
        q = question.lower()
        return any(mot in q for mot in MOTS_HORS_CONTEXTE)

    def _est_conversationnel(self, question: str) -> bool:
        mots_conv = [
            'bonjour', 'bonsoir', 'salut', 'merci', 'au revoir',
            'bonne journée', 'bonne nuit', 'comment vas', 'ça va',
            'ok', 'super', 'parfait', "d'accord", 'compris',
            'très bien', 'bien reçu', 'entendu'
        ]
        q = question.lower().strip()
        return any(q.startswith(m) or q == m for m in mots_conv) or len(question.split()) <= 3

    def _get_cache_key(self, question: str) -> str:
        q_normalized = question.lower().strip()
        return f"fasox_rag_{hashlib.md5(q_normalized.encode()).hexdigest()}"

    def _chercher_contexte(self, question: str, top_k: int = 5) -> list:
        embedding = self.embedding_service.generer_embedding(question)
        chunks = (
            ChunkDocument.objects
            .annotate(distance=CosineDistance('embedding', embedding))
            .order_by('distance')[:top_k]
        )
        return [c for c in chunks if (1 - c.distance) >= SIMILARITY_THRESHOLD]

    def _construire_historique(self, conversation) -> list:
        messages = []
        for m in conversation.messages.order_by('created_at')[:10]:
            messages.append({"role": m.role, "content": m.contenu})
        return messages

    def _construire_messages(self, question: str, conversation) -> list:
        historique = self._construire_historique(conversation)
        messages_api = [{"role": "system", "content": SYSTEM_PROMPT}]

        if historique:
            messages_api += historique

        if self._est_conversationnel(question):
            messages_api.append({"role": "user", "content": question})
            return messages_api

        if self._est_hors_contexte(question):
            messages_api.append({"role": "user", "content": question})
            return messages_api

        chunks = self._chercher_contexte(question)

        if chunks:
            contexte = "\n\n".join([
                f"[Art. {c.numero_page}] {c.contenu}" for c in chunks
            ])
            user_content = f"""[EXTRAITS DOCUMENTS JURIDIQUES]
{contexte}

[QUESTION]
{question}

Analyse ces extraits et réponds clairement. Ne recopie pas le texte brut."""
        else:
            user_content = f"""{question}

(Aucun extrait trouvé — réponds depuis tes connaissances générales en droit burkinabè)"""

        messages_api.append({"role": "user", "content": user_content})
        return messages_api

    def repondre(self, question: str, conversation) -> str:
        # Vérifier le cache pour les questions juridiques
        cache_key = None
        if not self._est_conversationnel(question) and not self._est_hors_contexte(question):
            cache_key = self._get_cache_key(question)
            cached = cache.get(cache_key)
            if cached:
                Message.objects.create(
                    conversation=conversation, role='user', contenu=question)
                Message.objects.create(
                    conversation=conversation, role='assistant', contenu=cached)
                return cached

        # Appel API
        messages_api = self._construire_messages(question, conversation)
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages_api,
            max_tokens=1500,
            temperature=0.5,
        )
        reponse_text = response.choices[0].message.content

        # Mettre en cache
        if cache_key:
            cache.set(cache_key, reponse_text, timeout=3600)

        # Sauvegarder les messages
        Message.objects.create(
            conversation=conversation, role='user', contenu=question)
        Message.objects.create(
            conversation=conversation, role='assistant', contenu=reponse_text)

        return reponse_text

    def repondre_stream(self, question: str, conversation):
        import json
        messages_api = self._construire_messages(question, conversation)
        reponse_complete = ""

        stream = self.client.chat.completions.create(
            model=self.model,
            messages=messages_api,
            max_tokens=1500,
            temperature=0.5,
            stream=True,
        )

        for chunk in stream:
            delta = chunk.choices[0].delta
            if delta.content:
                reponse_complete += delta.content
                yield f"data: {json.dumps({'text': delta.content})}\n\n"

        Message.objects.create(
            conversation=conversation, role='user', contenu=question)
        Message.objects.create(
            conversation=conversation, role='assistant', contenu=reponse_complete)

        if not conversation.titre:
            conversation.titre = question[:100]
            conversation.save()

        yield f"data: {json.dumps({'done': True, 'conversation_id': conversation.id})}\n\n"