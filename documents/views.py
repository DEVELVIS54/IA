from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, generics
from rest_framework.permissions import IsAuthenticated
from django_ratelimit.decorators import ratelimit
from django.utils.decorators import method_decorator
from django.conf import settings
from google import genai
from pypdf import PdfReader
from .models import DocumentUtilisateur
from .serializers import DocumentUploadSerializer, DocumentSerializer

class DocumentUploadView(APIView):
    permission_classes = [IsAuthenticated]

    @method_decorator(ratelimit(key='user', rate='10/h', block=True))
    def post(self, request):
        serializer = DocumentUploadSerializer(data=request.FILES)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        fichier = request.FILES['fichier']

        # Sauvegarder le document
        document = DocumentUtilisateur.objects.create(
            utilisateur=request.user,
            fichier=fichier,
            nom_original=fichier.name,
            taille=fichier.size,
            statut='en_attente'
        )

        try:
            # Extraire le texte du PDF
            reader = PdfReader(document.fichier.path)
            texte = ""
            for page in reader.pages:
                texte += page.extract_text() + "\n"

            # Limiter le texte à 10000 caractères
            texte = texte[:10000]

            # Analyser avec Gemini
            client = genai.Client(api_key=settings.GEMINI_API_KEY)
            prompt = f"""Tu es un assistant juridique specialise en droit burkinabe.
Analyse ce document juridique et fournis :
1. Type de document
2. Parties impliquees
3. Clauses importantes
4. Points de risque potentiels
5. Articles du droit burkinabe applicables

Document :
{texte}

Note : Cette analyse ne remplace pas un avis d'avocat professionnel."""

            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt
            )

            # Mettre à jour le statut
            document.resultat_analyse = response.text
            document.statut = 'analyse'
            document.save()

            return Response(
                DocumentSerializer(document).data,
                status=status.HTTP_200_OK
            )

        except Exception as e:
            document.statut = 'erreur'
            document.save()
            return Response(
                {'erreur': f'Erreur analyse : {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class DocumentListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = DocumentSerializer

    def get_queryset(self):
        return DocumentUtilisateur.objects.filter(
            utilisateur=self.request.user
        ).order_by('-created_at')