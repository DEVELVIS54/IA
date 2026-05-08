from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, generics
from rest_framework.permissions import IsAuthenticated
from django_ratelimit.decorators import ratelimit
from django.utils.decorators import method_decorator
from .models import Conversation, Message
from .services.rag_service import RAGService

class ConversationListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        conversations = Conversation.objects.filter(
            utilisateur=request.user
        ).order_by('-updated_at')
        data = [{
            'id': c.id,
            'titre': c.titre,
            'created_at': c.created_at,
            'updated_at': c.updated_at
        } for c in conversations]
        return Response(data)

class ConversationDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        try:
            conversation = Conversation.objects.get(
                id=pk,
                utilisateur=request.user
            )
            conversation.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Conversation.DoesNotExist:
            return Response(
                {'erreur': 'Conversation introuvable.'},
                status=status.HTTP_404_NOT_FOUND
            )

class MessageListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            conversation = Conversation.objects.get(
                id=pk,
                utilisateur=request.user
            )
            messages = conversation.messages.order_by('created_at')
            data = [{
                'id': m.id,
                'role': m.role,
                'contenu': m.contenu,
                'created_at': m.created_at
            } for m in messages]
            return Response(data)
        except Conversation.DoesNotExist:
            return Response(
                {'erreur': 'Conversation introuvable.'},
                status=status.HTTP_404_NOT_FOUND
            )

class AskQuestionView(APIView):
    permission_classes = [IsAuthenticated]

    @method_decorator(ratelimit(key='user', rate='30/h', block=True))
    def post(self, request):
        question = request.data.get('question')
        conversation_id = request.data.get('conversation_id')

        if not question:
            return Response(
                {'erreur': 'La question est obligatoire.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if conversation_id:
            try:
                conversation = Conversation.objects.get(
                    id=conversation_id,
                    utilisateur=request.user
                )
            except Conversation.DoesNotExist:
                return Response(
                    {'erreur': 'Conversation introuvable.'},
                    status=status.HTTP_404_NOT_FOUND
                )
        else:
            conversation = Conversation.objects.create(
                utilisateur=request.user,
                titre=question[:100]
            )

        try:
            rag = RAGService()
            reponse = rag.repondre(question, conversation)
            return Response({
                'reponse': reponse,
                'conversation_id': conversation.id,
                'titre_conversation': conversation.titre
            })
        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response(
                {'erreur': f'Erreur IA : {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

            
from django.http import StreamingHttpResponse
import json

class AskStreamView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        question = request.data.get('question')
        conversation_id = request.data.get('conversation_id')

        if not question:
            return Response(
                {'erreur': 'La question est obligatoire.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if conversation_id:
            try:
                conversation = Conversation.objects.get(
                    id=conversation_id,
                    utilisateur=request.user
                )
            except Conversation.DoesNotExist:
                return Response(
                    {'erreur': 'Conversation introuvable.'},
                    status=status.HTTP_404_NOT_FOUND
                )
        else:
            conversation = Conversation.objects.create(
                utilisateur=request.user,
                titre=question[:100]
            )

        def generer_stream():
            try:
                from .services.embedding_service import EmbeddingService
                from .services.rag_service import RAGService
                from anthropic import Anthropic
                from django.conf import settings

                embedding_service = EmbeddingService()
                client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)

                # Chercher le contexte
                historique = conversation.messages.order_by('created_at')[:10]
                chunks = embedding_service.generer_embedding(question)

                from pgvector.django import CosineDistance
                chunks_pertinents = (
                    ChunkDocument.objects
                    .annotate(distance=CosineDistance('embedding', chunks))
                    .order_by('distance')[:5]
                )

                contexte = "\n\n---\n\n".join([
                    f"[{c.document.categorie.upper()}] {c.contenu}"
                    for c in chunks_pertinents
                ]) if chunks_pertinents else "Aucun document indexe."

                historique_texte = ""
                for m in historique:
                    role = "Utilisateur" if m.role == "user" else "Assistant"
                    historique_texte += f"{role} : {m.contenu}\n"

                prompt = f"""Contexte juridique :
{contexte}

Historique :
{historique_texte}

Question : {question}"""

                reponse_complete = ""

                # Streaming avec Claude
                with client.messages.stream(
                    model="claude-haiku-4-5",
                    max_tokens=1500,
                    system="""Tu es un assistant juridique specialise en droit burkinabe.
Tu reponds UNIQUEMENT en francais.
Tu cites toujours les articles sources.
Tes reponses ne remplacent pas un avis d'avocat.""",
                    messages=[{"role": "user", "content": prompt}]
                ) as stream:
                    for text in stream.text_stream:
                        reponse_complete += text
                        yield f"data: {json.dumps({'text': text})}\n\n"

                # Sauvegarder après streaming
                Message.objects.create(
                    conversation=conversation,
                    role='user',
                    contenu=question
                )
                Message.objects.create(
                    conversation=conversation,
                    role='assistant',
                    contenu=reponse_complete
                )

                if not conversation.titre:
                    conversation.titre = question[:100]
                    conversation.save()

                # Signal fin du stream
                yield f"data: {json.dumps({'done': True, 'conversation_id': conversation.id})}\n\n"

            except Exception as e:
                import traceback
                traceback.print_exc()
                yield f"data: {json.dumps({'erreur': str(e)})}\n\n"

        response = StreamingHttpResponse(
            generer_stream(),
            content_type='text/event-stream'
        )
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        return response            