"""
Django Admin Configuration for Chatbot
"""
from django.contrib import admin
from .models import ChatHistory


@admin.register(ChatHistory)
class ChatHistoryAdmin(admin.ModelAdmin):
    list_display = ['user_or_session', 'query_preview', 'tool_used', 'timestamp', 'response_time']
    list_filter = ['timestamp', 'tool_used']
    search_fields = ['query', 'response', 'session_id', 'user__username']
    readonly_fields = ['timestamp']
    date_hierarchy = 'timestamp'
    
    def user_or_session(self, obj):
        return obj.user.username if obj.user else f"Session {obj.session_id[:8]}"
    user_or_session.short_description = "User"
    
    def query_preview(self, obj):
        return obj.query[:50] + '...' if len(obj.query) > 50 else obj.query
    query_preview.short_description = "Query"