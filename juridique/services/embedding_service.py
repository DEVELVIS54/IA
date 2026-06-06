# juridique/services/embedding_service.py
import os
import threading
import hashlib
from django.core.cache import cache
from pypdf import PdfReader
from juridique.models import ChunkDocument

# ── Singleton thread-safe ──────────────────────────────────────────────────
_model = None
_model_lock = threading.Lock()

def get_model():
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                from sentence_transformers import SentenceTransformer
                print("Chargement du modele d'embedding...")
                _model = SentenceTransformer(
                    'paraphrase-multilingual-mpnet-base-v2',
                    device='cpu'
                )
                # Warm-up
                _model.encode("test", normalize_embeddings=True)
                print("Modele charge !")
    return _model


class EmbeddingService:

    def __init__(self):
        self.model = get_model()

    # ── Extraction PDF optimisée ───────────────────────────────────────

    def extraire_texte_pdf(self, chemin_fichier: str) -> str:
        reader = PdfReader(chemin_fichier)
        pages = []
        for page in reader.pages:
            texte = page.extract_text()
            if texte and texte.strip():
                pages.append(texte.strip())
        return "\n".join(pages)

    # ── Découpage intelligent ──────────────────────────────────────────

    def decouper_en_chunks(self, texte: str, taille: int = 500, chevauchement: int = 50) -> list:
        mots = texte.split()
        chunks = []
        i = 0
        while i < len(mots):
            chunk = ' '.join(mots[i:i + taille])
            # Ignore les chunks trop courts (table des matières, etc.)
            if len(chunk.strip()) > 100:
                chunks.append(chunk)
            i += taille - chevauchement
        return chunks

    # ── Embedding unique avec cache Redis ─────────────────────────────

    def generer_embedding(self, texte: str) -> list:
        cache_key = f"emb_{hashlib.md5(texte[:200].encode()).hexdigest()}"
        cached = cache.get(cache_key)
        if cached:
            return cached

        vecteur = self.model.encode(
            texte,
            normalize_embeddings=True,
            show_progress_bar=False
        ).tolist()

        cache.set(cache_key, vecteur, timeout=86400)
        return vecteur

    # ── Embedding batch ultra-optimisé ────────────────────────────────

    def generer_embeddings_batch(self, textes: list, batch_size: int = 64) -> list:
        """Encode tous les chunks en une seule passe GPU/CPU optimisée."""
        import numpy as np

        tous_embeddings = []
        total = len(textes)

        for i in range(0, total, batch_size):
            batch = textes[i:i + batch_size]
            embeddings = self.model.encode(
                batch,
                normalize_embeddings=True,
                show_progress_bar=False,
                batch_size=batch_size,
                convert_to_numpy=True
            )
            tous_embeddings.extend(embeddings.tolist())
            print(f"  {min(i + batch_size, total)}/{total} embeddings générés")

        return tous_embeddings

    # ── Indexation complète optimisée ─────────────────────────────────

    def indexer_document(self, document_juridique) -> int:
        print(f"\nIndexation : {document_juridique.titre}")

        # Extraction
        texte = self.extraire_texte_pdf(document_juridique.fichier.path)
        if not texte.strip():
            raise ValueError("PDF sans texte (PDF scanné ?)")
        print(f"  Texte : {len(texte)} caractères")

        # Découpage
        chunks = self.decouper_en_chunks(texte)
        if not chunks:
            raise ValueError("Aucun chunk extrait du document")
        print(f"  Chunks : {len(chunks)}")

        # Embeddings en batch (beaucoup plus rapide qu'un par un)
        print(f"  Génération des embeddings en batch...")
        embeddings = self.generer_embeddings_batch([c for c in chunks])

        # Suppression anciens chunks
        ChunkDocument.objects.filter(document=document_juridique).delete()

        # Insertion optimisée en base
        chunks_a_creer = [
            ChunkDocument(
                document=document_juridique,
                contenu=chunks[i],
                embedding=embeddings[i],
                numero_page=i
            )
            for i in range(len(chunks))
        ]
        # bulk_create par lots de 100 pour éviter les timeouts PostgreSQL
        for i in range(0, len(chunks_a_creer), 100):
            ChunkDocument.objects.bulk_create(chunks_a_creer[i:i + 100])

        document_juridique.indexe = True
        document_juridique.save()

        print(f"  ✅ {len(chunks_a_creer)} chunks indexés")
        return len(chunks_a_creer)