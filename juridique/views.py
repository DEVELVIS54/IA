# juridique/views.py
import json
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, generics
from rest_framework.permissions import IsAuthenticated
from django_ratelimit.decorators import ratelimit
from django.utils.decorators import method_decorator
from django.http import StreamingHttpResponse
from .models import Conversation, Message, FeedbackMessage, LogEchecRAG
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
            conversation = Conversation.objects.get(id=pk, utilisateur=request.user)
            conversation.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except Conversation.DoesNotExist:
            return Response({'erreur': 'Conversation introuvable.'}, status=status.HTTP_404_NOT_FOUND)


class MessageListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            conversation = Conversation.objects.get(id=pk, utilisateur=request.user)
            messages = conversation.messages.order_by('created_at')
            data = [{
                'id': m.id,
                'role': m.role,
                'contenu': m.contenu,
                'created_at': m.created_at,
                'feedback': m.feedback.vote if hasattr(m, 'feedback') else None
            } for m in messages]
            return Response(data)
        except Conversation.DoesNotExist:
            return Response({'erreur': 'Conversation introuvable.'}, status=status.HTTP_404_NOT_FOUND)


class AskQuestionView(APIView):
    permission_classes = [IsAuthenticated]

    @method_decorator(ratelimit(key='user', rate='30/h', block=True))
    def post(self, request):
        question = request.data.get('question')
        conversation_id = request.data.get('conversation_id')

        if not question:
            return Response({'erreur': 'La question est obligatoire.'}, status=status.HTTP_400_BAD_REQUEST)

        if conversation_id:
            try:
                conversation = Conversation.objects.get(id=conversation_id, utilisateur=request.user)
            except Conversation.DoesNotExist:
                return Response({'erreur': 'Conversation introuvable.'}, status=status.HTTP_404_NOT_FOUND)
        else:
            conversation = Conversation.objects.create(utilisateur=request.user, titre=question[:100])

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
            return Response({'erreur': f'Erreur IA : {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AskStreamView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        question = request.data.get('question')
        conversation_id = request.data.get('conversation_id')

        if not question:
            return Response({'erreur': 'La question est obligatoire.'}, status=status.HTTP_400_BAD_REQUEST)

        if conversation_id:
            try:
                conversation = Conversation.objects.get(id=conversation_id, utilisateur=request.user)
            except Conversation.DoesNotExist:
                return Response({'erreur': 'Conversation introuvable.'}, status=status.HTTP_404_NOT_FOUND)
        else:
            conversation = Conversation.objects.create(utilisateur=request.user, titre=question[:100])

        def generer():
            try:
                yield f"data: {json.dumps({'ping': True})}\n\n"
                rag = RAGService()
                for chunk in rag.repondre_stream(question, conversation):
                    yield chunk
            except Exception as e:
                import traceback
                traceback.print_exc()
                yield f"data: {json.dumps({'erreur': str(e)})}\n\n"

        response = StreamingHttpResponse(generer(), content_type='text/event-stream; charset=utf-8')
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response['X-Accel-Buffering'] = 'no'
        response['Connection'] = 'keep-alive'
        return response


class FeedbackView(APIView):
    """Endpoint pour 👍/👎 sur un message."""
    permission_classes = [IsAuthenticated]

    def post(self, request, message_id):
        vote = request.data.get('vote')
        commentaire = request.data.get('commentaire', '')

        if vote not in ['positif', 'negatif']:
            return Response({'erreur': 'Vote invalide.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            message = Message.objects.get(
                id=message_id,
                role='assistant',
                conversation__utilisateur=request.user
            )
        except Message.DoesNotExist:
            return Response({'erreur': 'Message introuvable.'}, status=status.HTTP_404_NOT_FOUND)

        feedback, created = FeedbackMessage.objects.update_or_create(
            message=message,
            defaults={
                'utilisateur': request.user,
                'vote': vote,
                'commentaire': commentaire
            }
        )
        return Response({'status': 'ok', 'vote': vote})


class LogEchecRAGView(APIView):
    """Stats des questions sans bonne réponse — admin only."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.is_staff:
            return Response({'erreur': 'Accès refusé.'}, status=status.HTTP_403_FORBIDDEN)
        logs = LogEchecRAG.objects.order_by('-created_at')[:50]
        data = [{
            'question': l.question,
            'score_max': l.score_max,
            'created_at': l.created_at
        } for l in logs]
        return Response(data)