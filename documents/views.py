# documents/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, generics
from rest_framework.permissions import IsAuthenticated
from django_ratelimit.decorators import ratelimit
from django.utils.decorators import method_decorator
from django.conf import settings
from openai import OpenAI
from pypdf import PdfReader
from .models import DocumentUtilisateur
from .serializers import DocumentUploadSerializer, DocumentSerializer

ANALYSE_PROMPT = """Tu es FasoX IA, expert juridique burkinabè de haut niveau.

Analyse ce document avec une précision chirurgicale et structure ta réponse ainsi :

## 📄 IDENTIFICATION DU DOCUMENT
- Type exact (contrat, jugement, acte notarié, bail, etc.)
- Date et lieu si mentionnés
- Référence ou numéro si présent

## 👥 PARTIES IMPLIQUÉES
- Nom, qualité et rôle de chaque partie
- Représentants légaux si applicable

## ⚖️ ANALYSE JURIDIQUE
### Objet principal
- Ce que le document établit ou décide concrètement

### Clauses essentielles
- Les obligations de chaque partie
- Les droits accordés
- Les délais et conditions

### Base légale applicable
- Articles précis du droit burkinabè applicable
- Codes concernés (Code Civil, Code du Travail, OHADA, etc.)

## 🚨 POINTS DE RISQUE
- Clauses abusives ou déséquilibrées
- Obligations cachées ou imprécises
- Délais dangereux
- Ce qui manque et devrait être présent

## ✅ CONFORMITÉ LÉGALE
- Le document est-il légalement valide ?
- Ce qui est conforme au droit burkinabè
- Ce qui pourrait être contesté

## 💡 RECOMMANDATIONS
- Actions concrètes à prendre
- Points à négocier ou modifier
- Professionnels à consulter si nécessaire

## 📊 SCORE DE RISQUE
Évalue le document : [FAIBLE / MOYEN / ÉLEVÉ / CRITIQUE]
Justifie en une phrase.

---
DOCUMENT À ANALYSER :
{texte}

---
⚠️ Cette analyse est fournie à titre informatif et ne remplace pas l'avis d'un juriste qualifié."""


class DocumentUploadView(APIView):
    permission_classes = [IsAuthenticated]

    @method_decorator(ratelimit(key='user', rate='10/h', block=True))
    def post(self, request):
        serializer = DocumentUploadSerializer(data=request.FILES)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        fichier = request.FILES['fichier']

        # Vérification type de fichier
        if not fichier.name.lower().endswith('.pdf'):
            return Response(
                {'erreur': 'Seuls les fichiers PDF sont acceptés.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Vérification taille (max 10 Mo)
        if fichier.size > 10 * 1024 * 1024:
            return Response(
                {'erreur': 'Le fichier ne doit pas dépasser 10 Mo.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        document = DocumentUtilisateur.objects.create(
            utilisateur=request.user,
            fichier=fichier,
            nom_original=fichier.name,
            taille=fichier.size,
            statut='en_attente'
        )

        try:
            # Extraction intelligente du texte
            texte = self._extraire_texte(document.fichier.path)

            if not texte.strip():
                raise ValueError("Le PDF ne contient pas de texte extractible. Il est peut-être scanné.")

            # Analyse avec Groq
            client = OpenAI(
                api_key=settings.GROQ_API_KEY,
                base_url="https://api.groq.com/openai/v1"
            )

            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {
                        "role": "system",
                        "content": "Tu es un expert juridique burkinabè rigoureux. Tu analyses des documents avec précision et honnêteté."
                    },
                    {
                        "role": "user",
                        "content": ANALYSE_PROMPT.format(texte=texte)
                    }
                ],
                max_tokens=3000,
                temperature=0.3,
            )

            analyse = response.choices[0].message.content
            document.resultat_analyse = analyse
            document.statut = 'analyse'
            document.save()

            return Response(DocumentSerializer(document).data, status=status.HTTP_200_OK)

        except ValueError as e:
            document.statut = 'erreur'
            document.resultat_analyse = str(e)
            document.save()
            return Response({'erreur': str(e)}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        except Exception as e:
            document.statut = 'erreur'
            document.save()
            return Response(
                {'erreur': f'Erreur lors de l\'analyse : {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _extraire_texte(self, chemin: str) -> str:
        reader = PdfReader(chemin)
        parties = []

        for i, page in enumerate(reader.pages):
            texte_page = page.extract_text()
            if texte_page and texte_page.strip():
                parties.append(f"[Page {i+1}]\n{texte_page}")

        texte_complet = "\n\n".join(parties)

        # Limite intelligente : garde début + fin du document
        if len(texte_complet) > 15000:
            debut = texte_complet[:10000]
            fin = texte_complet[-3000:]
            texte_complet = debut + "\n\n[...document tronqué...]\n\n" + fin

        return texte_complet


class DocumentListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = DocumentSerializer

    def get_queryset(self):
        return DocumentUtilisateur.objects.filter(
            utilisateur=self.request.user
        ).order_by('-created_at')