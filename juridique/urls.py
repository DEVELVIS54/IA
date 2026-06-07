from django.urls import path
from .views import (
    ConversationListView,
    ConversationDeleteView,
    MessageListView,
    AskQuestionView,
    AskStreamView,
    FeedbackView,
    LogEchecRAGView,
)

urlpatterns = [
    path('conversations/', ConversationListView.as_view()),
    path('conversations/<int:pk>/', ConversationDeleteView.as_view()),
    path('conversations/<int:pk>/messages/', MessageListView.as_view()),
    path('ask/', AskQuestionView.as_view()),
    path('ask/stream/', AskStreamView.as_view()),
    path('messages/<int:message_id>/feedback/', FeedbackView.as_view()),
    path('logs/echecs/', LogEchecRAGView.as_view()),
]