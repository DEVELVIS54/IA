import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from juridique.models import DocumentJuridique
from juridique.services.embedding_service import EmbeddingService

DOCS = [
    ('documents_juridiques/Code_Penal.pdf', 'Code Pénal du Burkina Faso', 'code_penal'),
    ('documents_juridiques/CODE CIVIL DU BURKINA FASO.pdf', 'Code Civil du Burkina Faso', 'code_civil'),
    ('documents_juridiques/CODE PROCEDURE PENALE.pdf', 'Code de Procédure Pénale', 'code_penal'),
    ('documents_juridiques/Nouveau-Code-de-la-famille.pdf', 'Code de la Famille', 'code_famille'),
    ('documents_juridiques/Burkina-Faso-Code-personnes-famille-2025.pdf', 'Code des Personnes et de la Famille 2025', 'code_famille'),
    ('documents_juridiques/CODE-GENERAL-DES-IMPOTS-2021.pdf', 'Code Général des Impôts 2021', 'ohada'),
    ('documents_juridiques/22-08-2021-C7-Loi_28-2008AN_du_13_mai_2008_portant_code_du_travail__XL9uNhB.pdf', 'Code du Travail du Burkina Faso', 'code_travail'),
]

service = EmbeddingService()
total = 0

for chemin, titre, categorie in DOCS:
    plein_chemin = f'/app/media/{chemin}'
    if not os.path.exists(plein_chemin):
        print(f"FICHIER INTROUVABLE: {plein_chemin}")
        continue
    doc, created = DocumentJuridique.objects.get_or_create(
        titre=titre,
        defaults={'categorie': categorie, 'fichier': chemin, 'indexe': False}
    )
    if not created:
        doc.fichier = chemin
        doc.save()
    print(f"\nIndexation: {titre}")
    try:
      n = service.indexer_document(doc)
    except Exception as e:
     print(f"ERREUR: {e}")
    n = 0
    total += n
    print(f"OK: {n} chunks")

print(f"\nTOTAL: {total} chunks indexes")