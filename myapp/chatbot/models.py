"""
Django Models for Chatbot
Optional: For storing chat history
"""
from django.db import models
from django.contrib.auth.models import User


class ChatHistory(models.Model):
    """
    Store chat interactions for analytics and history
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="User who made the query (null for anonymous)"
    )
    session_id = models.CharField(
        max_length=100,
        help_text="Session identifier"
    )
    query = models.TextField(
        help_text="User's query"
    )
    response = models.TextField(
        help_text="AI-generated response"
    )
    tool_used = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="Which tool was used (CareerGraph or CourseRecommendations)"
    )
    timestamp = models.DateTimeField(
        auto_now_add=True,
        db_index=True
    )
    response_time = models.FloatField(
        null=True,
        blank=True,
        help_text="Response time in seconds"
    )
    
    class Meta:
        ordering = ['-timestamp']
        verbose_name = "Chat History"
        verbose_name_plural = "Chat Histories"
    
    def __str__(self):
        user_display = self.user.username if self.user else f"Session {self.session_id[:8]}"
        return f"{user_display} - {self.query[:50]} - {self.timestamp.strftime('%Y-%m-%d %H:%M')}"


# Note: After creating this model, run:
# python manage.py makemigrations
# python manage.py migrate