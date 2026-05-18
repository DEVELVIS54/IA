from django.urls import path
from .views import (
    ConversationListView,
    ConversationDeleteView,
    MessageListView,
    AskQuestionView,
    AskStreamView,
)

urlpatterns = [
    path('conversations/', ConversationListView.as_view()),
    path('conversations/<int:pk>/', ConversationDeleteView.as_view()),
    path('conversations/<int:pk>/messages/', MessageListView.as_view()),
    path('ask/', AskQuestionView.as_view()),
   # path('ask/stream/', AskStreamView.as_view()),
    path('ask/stream/', AskStreamView.as_view()),  # nouveau endpoint streaming
]