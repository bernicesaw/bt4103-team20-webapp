"""
URL Configuration for Chatbot App
"""
from django.urls import path
from . import views

app_name = 'chatbot'

urlpatterns = [
    # Main chat interface
    path('', views.chatbot_view, name='chat'),
    
    # API endpoints
    path('api/query/', views.query_chatbot_api, name='query'),  # ← Make sure this exists
    path('api/health/', views.health_check, name='health'),
]