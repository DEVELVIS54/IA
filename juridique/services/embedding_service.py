from sentence_transformers import SentenceTransformer
from pypdf import PdfReader
from juridique.models import ChunkDocument

class EmbeddingService:
    def __init__(self):
        print("Chargement du modele d'embedding...")
        self.model = SentenceTransformer('paraphrase-multilingual-mpnet-base-v2')
        print("Modele charge !")

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

        # 1. Extraire le texte
        texte = self.extraire_texte_pdf(document_juridique.fichier.path)
        print(f"Texte extrait : {len(texte)} caracteres")

        # 2. Découper en chunks
        chunks = self.decouper_en_chunks(texte)
        print(f"Nombre de chunks : {len(chunks)}")

        # 3. Supprimer anciens chunks si réindexation
        ChunkDocument.objects.filter(document=document_juridique).delete()

        # 4. Générer embeddings et sauvegarder
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