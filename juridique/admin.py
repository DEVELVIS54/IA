from django.contrib import admin
from .models import DocumentJuridique, ChunkDocument, Conversation, Message

@admin.register(DocumentJuridique)
class DocumentJuridiqueAdmin(admin.ModelAdmin):
    list_display = ['titre', 'categorie', 'indexe', 'created_at']
    list_filter = ['categorie', 'indexe']
    search_fields = ['titre']
    actions = ['indexer_documents']

    def indexer_documents(self, request, queryset):
        from .services.embedding_service import EmbeddingService
        service = EmbeddingService()
        for doc in queryset:
            service.indexer_document(doc)
        self.message_user(request, f"{queryset.count()} document(s) indexe(s).")
    indexer_documents.short_description = "Indexer les documents selectionnes"

@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ['utilisateur', 'titre', 'created_at']
    search_fields = ['titre']

@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ['conversation', 'role', 'created_at']
    list_filter = ['role']