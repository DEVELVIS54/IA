# juridique/services/embedding_service.py
from sentence_transformers import SentenceTransformer
from pypdf import PdfReader
from juridique.models import ChunkDocument

# Singleton — chargé une seule fois au démarrage
_model_instance = None

def get_model():
    global _model_instance
    if _model_instance is None:
        print("Chargement du modele d'embedding...")
        _model_instance = SentenceTransformer('paraphrase-multilingual-mpnet-base-v2')
        print("Modele charge !")
    return _model_instance


class EmbeddingService:
    def __init__(self):
        self.model = get_model()

    def extraire_texte_pdf(self, chemin_fichier):
        reader = PdfReader(chemin_fichier)
        texte = ""
        for page in reader.pages:
            texte += page.extract_text() + "\n"
        return texte

    def decouper_en_chunks(self, texte, taille=500, chevauchement=50):
        mots = texte.split()
        chunks = []
        i = 0
        while i < len(mots):
            chunk = ' '.join(mots[i:i + taille])
            chunks.append(chunk)
            i += taille - chevauchement
        return chunks

    def generer_embedding(self, texte):
        vecteur = self.model.encode(texte, normalize_embeddings=True)
        return vecteur.tolist()

    def indexer_document(self, document_juridique):
        print(f"Indexation de : {document_juridique.titre}")
        texte = self.extraire_texte_pdf(document_juridique.fichier.path)
        print(f"Texte extrait : {len(texte)} caracteres")
        chunks = self.decouper_en_chunks(texte)
        print(f"Nombre de chunks : {len(chunks)}")
        ChunkDocument.objects.filter(document=document_juridique).delete()
        chunks_a_creer = []
        for i, chunk in enumerate(chunks):
            embedding = self.generer_embedding(chunk)
            chunks_a_creer.append(ChunkDocument(
                document=document_juridique,
                contenu=chunk,
                embedding=embedding,
                numero_page=i
            ))
        ChunkDocument.objects.bulk_create(chunks_a_creer)
        document_juridique.indexe = True
        document_juridique.save()
        print(f"Indexation terminee : {len(chunks_a_creer)} chunks crees")
        return len(chunks_a_creer)