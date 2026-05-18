"""
Test de la recherche vectorielle
Lancer depuis le dossier racine du projet Django :
    python test_vector_search.py
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from juridique.models import ChunkDocument
from juridique.services.embedding_service import EmbeddingService
from pgvector.django import CosineDistance

def test_vectoriel(question, top_k=5):
    print(f"\n{'='*60}")
    print(f"Question : {question}")
    print('='*60)

    service = EmbeddingService()
    
    # 1. Vérifier le nombre de chunks indexés
    total = ChunkDocument.objects.count()
    print(f"\n📊 Chunks indexés en base : {total}")
    
    if total == 0:
        print("❌ Aucun document indexé. Indexez d'abord un document.")
        return

    # 2. Générer l'embedding de la question
    print(f"\n🔍 Génération de l'embedding pour la question...")
    embedding = service.generer_embedding(question)
    print(f"✅ Embedding généré : {len(embedding)} dimensions")

    # 3. Recherche vectorielle
    print(f"\n📚 Recherche des {top_k} chunks les plus pertinents...")
    chunks = (
        ChunkDocument.objects
        .annotate(distance=CosineDistance('embedding', embedding))
        .order_by('distance')[:top_k]
    )

    # 4. Afficher les résultats
    print(f"\n{'─'*60}")
    for i, chunk in enumerate(chunks, 1):
        similarite = 1 - chunk.distance
        print(f"\n[Chunk {i}] Similarité: {similarite:.4f} | Document: {chunk.document.titre}")
        print(f"Page/Numéro: {chunk.numero_page}")
        print(f"Extrait: {chunk.contenu[:200]}...")
        print('─'*40)

    # 5. Test inverse : trouver les questions similaires à un chunk
    print(f"\n{'='*60}")
    print("Test INVERSE : similarité entre chunks du Code du travail")
    print('='*60)
    
    # Prendre le chunk le plus pertinent et chercher d'autres similaires
    if chunks:
        premier_chunk = chunks[0]
        print(f"\nChunk de référence : {premier_chunk.contenu[:100]}...")
        
        similaires = (
            ChunkDocument.objects
            .annotate(distance=CosineDistance('embedding', list(premier_chunk.embedding)))
            .order_by('distance')[1:4]  # Exclure lui-même
        )
        
        print("\nChunks les plus similaires :")
        for c in similaires:
            print(f"  - Similarité: {1-c.distance:.4f} | {c.contenu[:100]}...")

if __name__ == '__main__':
    # Test avec des questions sur le Code du travail burkinabè
    questions = [
        "Quelle est la durée légale du travail au Burkina Faso ?",
        "Quels sont les droits du travailleur en cas de licenciement ?",
        "Comment fonctionne le contrat à durée déterminée ?",
    ]
    
    for q in questions:
        test_vectoriel(q, top_k=3)
        print()