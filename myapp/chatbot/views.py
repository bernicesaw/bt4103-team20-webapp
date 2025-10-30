"""
Django Views for Career Chatbot
NOW RUNS AGENT DIRECTLY - No FastAPI needed!
"""
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.cache import never_cache
import json
import time
import logging

# Import the agent directly from this Django app
from .agents import career_rag_agent_executor

logger = logging.getLogger(__name__)


@never_cache
def chatbot_view(request):
    """
    Main chat interface view
    Renders the chat template
    """
    return render(request, 'chatbot/chat.html', {
        'page_title': 'Career Chatbot',
        'user': request.user
    })


@require_http_methods(["POST"])
async def query_chatbot_api(request):
    """
    Async endpoint that runs the career agent DIRECTLY in Django
    No FastAPI needed anymore!
    
    POST /askai/api/query/
    Body: {"text": "user query", "session_id": "optional"}
    
    Returns: {
        "success": true,
        "input": "user query",
        "output": "AI response",
        "intermediate_steps": [...],
        "response_time": 3.45
    }
    """
    start_time = time.time()
    
    try:
        # Parse request body
        if request.content_type == 'application/json':
            data = json.loads(request.body)
        else:
            data = {
                'text': request.POST.get('text', ''),
                'session_id': request.POST.get('session_id', 'default')
            }
        
        text = data.get('text', '').strip()
        session_id = data.get('session_id', 'default')
        
        if not text:
            return JsonResponse({
                'success': False,
                'error': 'Text parameter is required'
            }, status=400)
        
        logger.info(f"Processing query: {text[:50]}...")
        
        # Call the agent DIRECTLY (no HTTP request to FastAPI!)
        # This runs your LangChain agent in Django
        result = await career_rag_agent_executor.ainvoke({"input": text})
        
        # Calculate response time
        response_time = time.time() - start_time
        
        logger.info(f"Query processed in {response_time:.2f}s")
        
        # Optional: Save to database
        # from .models import ChatHistory
        # ChatHistory.objects.create(
        #     user=request.user if request.user.is_authenticated else None,
        #     session_id=session_id,
        #     query=text,
        #     response=result.get('output', ''),
        #     response_time=response_time
        # )
        
        # Ensure intermediate steps are JSON-serializable
        intermediate_steps = []
        if "intermediate_steps" in result:
            intermediate_steps = [
                str(step) for step in result["intermediate_steps"]
            ]
        
        # Return successful response
        return JsonResponse({
            'success': True,
            'input': text,
            'output': result.get('output', 'No response generated'),
            'intermediate_steps': intermediate_steps,
            'response_time': round(response_time, 2)
        })
        
    except Exception as e:
        logger.error(f"Error processing query: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': f'Error: {str(e)}'
        }, status=500)


@require_http_methods(["GET"])
def health_check(request):
    """
    Health check - verifies Django and all dependencies are working
    
    GET /askai/api/health/
    """
    try:
        # Check if chains are initialized
        from .chains import career_cypher_chain, qa_chain
        
        health_status = {
            'status': 'healthy',
            'django': 'running',
            'career_chain': 'initialized',
            'course_chain': 'initialized',
            'agent': 'initialized'
        }
        
        # Optional: Test Neo4j connection
        try:
            from .chains import graph
            graph.query("RETURN 1 as test")
            health_status['neo4j'] = 'connected'
        except Exception as e:
            health_status['neo4j'] = f'error: {str(e)}'
        
        # Optional: Test Supabase connection
        try:
            from .chains import supabase_vector_store
            # Simple test query
            supabase_vector_store.similarity_search("test", k=1)
            health_status['supabase'] = 'connected'
        except Exception as e:
            health_status['supabase'] = f'error: {str(e)}'
        
        return JsonResponse(health_status)
        
    except Exception as e:
        return JsonResponse({
            'status': 'unhealthy',
            'django': 'running',
            'error': str(e)
        }, status=503)


# Optional: Synchronous version if async doesn't work in your Django version
@require_http_methods(["POST"])
def query_chatbot_sync(request):
    """
    Synchronous version of query_chatbot_api
    Use this if your Django version doesn't fully support async views
    """
    start_time = time.time()
    
    try:
        # Parse request
        if request.content_type == 'application/json':
            data = json.loads(request.body)
        else:
            data = {
                'text': request.POST.get('text', ''),
                'session_id': request.POST.get('session_id', 'default')
            }
        
        text = data.get('text', '').strip()
        session_id = data.get('session_id', 'default')
        
        if not text:
            return JsonResponse({
                'success': False,
                'error': 'Text parameter is required'
            }, status=400)
        
        logger.info(f"Processing query (sync): {text[:50]}...")
        
        # Call agent synchronously
        result = career_rag_agent_executor.invoke({"input": text})
        
        response_time = time.time() - start_time
        logger.info(f"Query processed in {response_time:.2f}s")
        
        # Ensure intermediate steps are JSON-serializable
        intermediate_steps = []
        if "intermediate_steps" in result:
            intermediate_steps = [
                str(step) for step in result["intermediate_steps"]
            ]
        
        return JsonResponse({
            'success': True,
            'input': text,
            'output': result.get('output', 'No response generated'),
            'intermediate_steps': intermediate_steps,
            'response_time': round(response_time, 2)
        })
        
    except Exception as e:
        logger.error(f"Error processing query: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': f'Error: {str(e)}'
        }, status=500)