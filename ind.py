"""
Verification rapide des documents indexes
Usage : python check_index.py
"""
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from juridique.models import ChunkDocument
from documents.models import Document  # adapter si nom different

print("\n" + "="*55)
print("  VERIFICATION DES DOCUMENTS INDEXES")
print("="*55)

# ── Documents ──────────────────────────────────────────────
try:
    docs = Document.objects.all().order_by('-created_at')
    print(f"\n📄 DOCUMENTS EN BASE : {docs.count()}\n")

    for doc in docs:
        chunks = ChunkDocument.objects.filter(document=doc).count()
        statut = "✅ Indexe" if chunks > 0 else "❌ Non indexe"
        taille = f"{doc.taille / 1024:.1f} Ko" if hasattr(doc, 'taille') and doc.taille else "?"
        print(f"  {statut}")
        print(f"  Nom      : {doc.nom_original if hasattr(doc, 'nom_original') else doc.titre}")
        print(f"  Taille   : {taille}")
        print(f"  Chunks   : {chunks}")
        print(f"  Date     : {doc.created_at.strftime('%d/%m/%Y %H:%M') if hasattr(doc, 'created_at') else '?'}")
        print()

except Exception as e:
    print(f"  Erreur acces documents : {e}")
    print("  Adapter le nom du modele Document dans le script\n")

# ── Chunks total ───────────────────────────────────────────
total = ChunkDocument.objects.count()
print(f"{'─'*55}")
print(f"  TOTAL CHUNKS EN BASE : {total}")
print(f"  Taille embedding     : 768 dimensions")
print(f"{'─'*55}")

# ── Test rapide de recherche ───────────────────────────────
print("\n🔍 TEST RECHERCHE VECTORIELLE RAPIDE\n")

from juridique.services.embedding_service import EmbeddingService
from pgvector.django import CosineDistance

questions_test = [
    "licenciement abusif",
    "contrat de travail",
    "droit penal",
]

service = EmbeddingService()
for q in questions_test:
    embedding = service.generer_embedding(q)
    top = (
        ChunkDocument.objects
        .annotate(distance=CosineDistance('embedding', embedding))
        .order_by('distance')
        .first()
    )
    if top:
        sim = round((1 - top.distance) * 100, 1)
        try:
            doc_nom = top.document.nom_original
        except:
            doc_nom = top.document.titre
        print(f"  '{q}'")
        print(f"   → {doc_nom} | Similarite : {sim}%")
        print(f"   → {top.contenu[:80]}...")
        print()

print("="*55 + "\n")