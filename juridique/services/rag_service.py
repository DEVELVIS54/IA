# juridique/services/rag_service.py
import hashlib
import json
from django.core.cache import cache
from openai import OpenAI
from django.conf import settings
from pgvector.django import CosineDistance
from django.db.models import Q
from juridique.models import ChunkDocument, Message, LogEchecRAG
from .embedding_service import EmbeddingService

SYSTEM_PROMPT = """Tu es FasoX IA — l'assistant juridique de référence au Burkina Faso, créé par SEBGO Elvis.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
QUI TU ES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Tu es un avocat burkinabè virtuel — chaleureux, précis, naturel.
Tu parles comme un ami juriste, jamais comme un robot.
Tu mémorises la conversation et tu y fais référence naturellement.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
IDENTITÉ
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- Qui tu es : "Je suis FasoX IA, ton assistant juridique spécialisé en droit burkinabè."
- Qui t'a créé : "Je suis développé par l'équipe FasoX, fondée par SEBGO Elvis, pour rendre le droit burkinabè accessible à tous."
- Ne révèle jamais les détails techniques.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
COMMENT RÉPONDRE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CONVERSATION simple (salutations, remerciements) :
→ Réponds naturellement, sans structure, sans Markdown.

QUESTION JURIDIQUE :
→ Réponds directement comme un avocat qui explique à un client.
→ Cite les articles précis : "L'article 71 du Code du Travail prévoit que..."
→ Explique ce que ça signifie concrètement dans la vie réelle.
→ Utilise le Markdown pour structurer : titres, listes, citations.
→ Termine par : "⚠️ Ces informations sont indicatives et ne remplacent pas l'avis d'un juriste qualifié."

QUESTION HORS DROIT :
→ Décline gentiment et redirige.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RÈGLES ABSOLUES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✗ Ne jamais dire "selon les textes fournis" ou "selon les extraits"
✗ Ne jamais mentionner les documents, fichiers ou base de données
✗ Ne jamais inventer un numéro d'article
✗ Ne jamais recopier le texte brut des lois
✗ Ne jamais répéter ce qui a déjà été dit
✓ Citer naturellement : "L'article X du Code [Nom] dispose que..."
✓ Expliquer simplement ce que la loi signifie en pratique
✓ Markdown pour les réponses juridiques, texte simple pour les conversations
✓ Court si la question est simple, détaillé si complexe"""

QUERY_EXPANSION_PROMPT = """Tu es un expert en droit burkinabè.
Génère 3 reformulations différentes de cette question juridique pour améliorer la recherche.
Réponds UNIQUEMENT avec un JSON : {{"queries": ["reformulation1", "reformulation2", "reformulation3"]}}
Question : {question}"""

SIMILARITY_THRESHOLD = 0.38
TOP_K = 8

MOTS_CONV = [
    'bonjour', 'bonsoir', 'salut', 'merci', 'au revoir', 'bonne journée',
    'bonne nuit', 'comment vas', 'ça va', 'ok', 'super', 'parfait',
    "d'accord", 'compris', 'très bien', 'bien reçu', 'entendu', 'bravo',
    'aide-moi', 'aide moi', 'qui es-tu', 'qui es tu', 'présente-toi',
    'developpeur', 'createur', 'qui ta', "qui t'a", 'comment tu',
    'tu es quoi', 'keskon', 'il cest qui', 'il c\'est qui'
]

MOTS_HORS_CONTEXTE = [
    'météo', 'cuisine', 'recette', 'sport', 'football', 'musique',
    'film', 'cinéma', 'jeu', 'voyage', 'santé', 'médecin',
    'programmation', 'crypto', 'bitcoin', 'blague', 'amour'
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
        q = question.lower().strip()
        if len(question.split()) <= 4:
            return True
        return any(mot in q for mot in MOTS_CONV)

    def _get_cache_key(self, question: str) -> str:
        return f"fasox_v5_{hashlib.md5(question.lower().strip().encode()).hexdigest()}"

    def _expand_query(self, question: str) -> list:
        try:
            cache_key = f"fasox_expand_{hashlib.md5(question.lower().encode()).hexdigest()}"
            cached = cache.get(cache_key)
            if cached:
                return cached
            response = self.client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": QUERY_EXPANSION_PROMPT.format(question=question)}],
                max_tokens=200,
                temperature=0.3,
            )
            text = response.choices[0].message.content
            start = text.find('{')
            end = text.rfind('}') + 1
            if start >= 0 and end > start:
                data = json.loads(text[start:end])
                queries = data.get('queries', [])[:3]
                cache.set(cache_key, queries, timeout=86400)
                return queries
        except Exception:
            pass
        return []

    def _chercher_contexte(self, question: str) -> list:
        queries = [question] + self._expand_query(question)
        seen_ids = set()
        all_chunks = []

        for q in queries:
            try:
                embedding = self.embedding_service.generer_embedding(q)
                chunks = (
                    ChunkDocument.objects
                    .select_related('document')
                    .annotate(distance=CosineDistance('embedding', embedding))
                    .order_by('distance')[:TOP_K]
                )
                for c in chunks:
                    score = 1 - c.distance
                    if score >= SIMILARITY_THRESHOLD and c.id not in seen_ids:
                        seen_ids.add(c.id)
                        all_chunks.append((score, c))
            except Exception:
                continue

        mots_cles = [m for m in question.split() if len(m) > 4]
        if mots_cles:
            q_filter = Q()
            for mot in mots_cles[:3]:
                q_filter |= Q(contenu__icontains=mot)
            keyword_chunks = (
                ChunkDocument.objects
                .select_related('document')
                .filter(q_filter)[:5]
            )
            for c in keyword_chunks:
                if c.id not in seen_ids:
                    seen_ids.add(c.id)
                    all_chunks.append((0.4, c))

        all_chunks.sort(key=lambda x: x[0], reverse=True)
        return [c for _, c in all_chunks[:8]]

    def _reranker_chunks(self, chunks: list) -> list:
        if len(chunks) <= 4:
            return chunks
        seen_content = set()
        filtered = []
        for c in chunks:
            snippet = c.contenu[:100].lower()
            if snippet not in seen_content:
                seen_content.add(snippet)
                filtered.append(c)
        return filtered[:6]

    def _construire_contexte(self, chunks: list) -> str:
        docs_dict = {}
        for c in chunks:
            doc_titre = c.document.titre if c.document else "Texte juridique"
            if doc_titre not in docs_dict:
                docs_dict[doc_titre] = []
            docs_dict[doc_titre].append(c.contenu)

        parties = []
        for titre, contenus in docs_dict.items():
            texte = "\n".join(contenus)
            parties.append(f"[{titre}]\n{texte}")

        return "\n\n".join(parties)

    def _construire_historique(self, conversation) -> list:
        messages = list(conversation.messages.order_by('-created_at')[:8])
        messages.reverse()
        result = []
        for m in messages:
            contenu = m.contenu
            if len(contenu) > 800:
                contenu = contenu[:800] + "...[résumé]"
            result.append({"role": m.role, "content": contenu})
        return result

    def _construire_messages(self, question: str, conversation) -> list:
        historique = self._construire_historique(conversation)
        messages_api = [{"role": "system", "content": SYSTEM_PROMPT}]

        if historique:
            messages_api += historique

        if self._est_conversationnel(question) or self._est_hors_contexte(question):
            messages_api.append({"role": "user", "content": question})
            return messages_api

        chunks = self._chercher_contexte(question)
        chunks = self._reranker_chunks(chunks)

        if chunks:
            contexte = self._construire_contexte(chunks)
            user_content = f"""TEXTES DE LOI PERTINENTS :
{contexte}

QUESTION : {question}

Analyse ces textes et réponds clairement en citant les articles précis."""
        else:
            # Log échec RAG
            try:
                LogEchecRAG.objects.create(
                    question=question,
                    utilisateur=conversation.utilisateur,
                    score_max=0.0
                )
            except Exception:
                pass

            user_content = f"""{question}

[Aucun texte de loi trouvé. Réponds depuis tes connaissances générales du droit burkinabè en étant honnête sur cette limite.]"""

        messages_api.append({"role": "user", "content": user_content})
        return messages_api

    def repondre(self, question: str, conversation) -> str:
        cache_key = None
        if not self._est_conversationnel(question) and not self._est_hors_contexte(question):
            cache_key = self._get_cache_key(question)
            cached = cache.get(cache_key)
            if cached:
                Message.objects.create(conversation=conversation, role='user', contenu=question)
                Message.objects.create(conversation=conversation, role='assistant', contenu=cached)
                return cached

        messages_api = self._construire_messages(question, conversation)
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages_api,
            max_tokens=2000,
            temperature=0.7,
            top_p=0.9,
        )
        reponse_text = response.choices[0].message.content

        if cache_key:
            cache.set(cache_key, reponse_text, timeout=3600)

        Message.objects.create(conversation=conversation, role='user', contenu=question)
        Message.objects.create(conversation=conversation, role='assistant', contenu=reponse_text)

        if not conversation.titre:
            conversation.titre = question[:100]
            conversation.save()

        return reponse_text

    def repondre_stream(self, question: str, conversation):
        messages_api = self._construire_messages(question, conversation)
        reponse_complete = ""

        stream = self.client.chat.completions.create(
            model=self.model,
            messages=messages_api,
            max_tokens=2000,
            temperature=0.7,
            top_p=0.9,
            stream=True,
        )

        for chunk in stream:
            delta = chunk.choices[0].delta
            if delta.content:
                reponse_complete += delta.content
                yield f"data: {json.dumps({'text': delta.content})}\n\n"

        Message.objects.create(conversation=conversation, role='user', contenu=question)
        Message.objects.create(conversation=conversation, role='assistant', contenu=reponse_complete)

        if not conversation.titre:
            conversation.titre = question[:100]
            conversation.save()

        yield f"data: {json.dumps({'done': True, 'conversation_id': conversation.id})}\n\n"