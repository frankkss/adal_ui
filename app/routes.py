from flask import Blueprint, render_template, request, jsonify, Response, current_app, redirect, url_for, session
import json
import time
import traceback
import threading
import logging
from functools import wraps

# Configure logger
logger = logging.getLogger(__name__)

bp = Blueprint('main', __name__)

def login_required(f):
    """Decorator to require login for routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('main.login'))
        return f(*args, **kwargs)
    return decorated_function

@bp.route('/')
def index():
    if 'user' not in session:
        return redirect(url_for('main.login'))
    return render_template('chat.html')

@bp.route('/login')
def login():
    if 'user' in session:
        return redirect(url_for('main.chat'))
    return render_template('login.html')

@bp.route('/signup')
def signup():
    if 'user' in session:
        return redirect(url_for('main.chat'))
    return render_template('signup.html')

@bp.route('/chat')
@login_required
def chat():
    return render_template('chat.html')

@bp.route('/about')
def about():
    """About page"""
    return render_template('about.html')

@bp.route('/charter')
def charter():
    """Charter page"""
    return render_template('charter.html')

@bp.route('/pricing')
def pricing():
    """Pricing page"""
    return render_template('pricing.html')

# Authentication API Routes
@bp.route('/api/auth/signup', methods=['POST'])
def api_signup():
    """Handle email signup"""
    from .auth_service import auth_service
    
    data = request.get_json()
    email = data.get('email', '').strip()
    password = data.get('password', '')
    full_name = data.get('full_name', '').strip()
    
    if not email or not password:
        return jsonify({'error': 'Email and password are required'}), 400
    
    if len(password) < 8:
        return jsonify({'error': 'Password must be at least 8 characters'}), 400
    
    result, status_code = auth_service.sign_up_with_email(email, password, full_name)
    return jsonify(result), status_code

@bp.route('/api/auth/signin', methods=['POST'])
def api_signin():
    """Handle email signin"""
    from .auth_service import auth_service
    
    data = request.get_json()
    email = data.get('email', '').strip()
    password = data.get('password', '')
    
    if not email or not password:
        return jsonify({'error': 'Email and password are required'}), 400
    
    result, status_code = auth_service.sign_in_with_email(email, password)
    
    if status_code == 200:
        session['user'] = result['user']
        session['access_token'] = result['session']['access_token']
    
    return jsonify(result), status_code

@bp.route('/api/auth/google')
def api_google_auth():
    """Get Google OAuth URL"""
    from .auth_service import auth_service
    
    result, status_code = auth_service.sign_in_with_google()
    return jsonify(result), status_code

@bp.route('/auth/callback')
def auth_callback():
    """Handle OAuth callback - both hash fragment and query params"""
    from .auth_service import auth_service
    
    # Check for authorization code in query params (OAuth flow)
    code = request.args.get('code')
    
    if code:
        # Exchange code for session
        result, status_code = auth_service.exchange_code_for_session(code)
        
        if status_code == 200:
            session['user'] = result['user']
            session['access_token'] = result['session']['access_token']
            return redirect(url_for('main.chat'))
        else:
            return redirect(url_for('main.login', error='auth_failed'))
    
    # Otherwise render callback page to handle hash fragment
    return render_template('auth_callback.html')

@bp.route('/api/auth/callback/session', methods=['POST'])
def api_callback_session():
    """Handle session creation from OAuth callback"""
    from .auth_service import auth_service
    
    data = request.get_json()
    access_token = data.get('access_token')
    
    if not access_token:
        return jsonify({'error': 'Access token required'}), 400
    
    # Get user info from token
    result, status_code = auth_service.get_user(access_token)
    
    if status_code == 200:
        session['user'] = result['user']
        session['access_token'] = access_token
        return jsonify({'success': True, 'redirect': '/chat'}), 200
    
    return jsonify({'error': 'Failed to get user info'}), status_code

@bp.route('/api/auth/signout', methods=['POST'])
def api_signout():
    """Handle signout"""
    from .auth_service import auth_service
    
    session.clear()
    result, status_code = auth_service.sign_out()
    return jsonify(result), status_code

@bp.route('/api/auth/user', methods=['GET'])
def api_get_user():
    """Get current user"""
    if 'user' in session:
        return jsonify({'user': session['user']}), 200
    return jsonify({'error': 'Not authenticated'}), 401

# Chat API Routes - OPTIMIZED FOR STREAMING WITH CONVERSATION HISTORY
@bp.route('/api/chat', methods=['POST'])
@login_required
def chat_api():
    """Handle chat messages with streaming and conversation history support"""
    from .rag_service import is_allowed, stream_with_history
    from .auth_service import auth_service
    
    try:
        data = request.get_json()
        user_message = data.get('message', '')
        chat_id = data.get('chat_id', None)
        
        logger.debug(f"Received message: {user_message[:100]}...")
        
        if not is_allowed(user_message):
            return jsonify({'error': 'Sorry, I can\'t assist with that.'}), 400
        
        user_id = session.get('user', {}).get('id')
        if not user_id:
            return jsonify({'error': 'User not authenticated'}), 401
        
        # Create new chat session if needed (lightweight operation)
        # If database is unavailable, still allow chatting with a temporary session
        db_available = True
        conversation_history = []
        
        if not chat_id:
            title = user_message[:50] + ('...' if len(user_message) > 50 else '')
            chat_session, status = auth_service.create_chat_session(user_id, title)
            
            if status == 200:
                chat_id = chat_session['id']
                logger.debug(f"Created new chat session: {chat_id}")
            elif status == 503:
                # Database unavailable - use temporary session ID
                import uuid
                chat_id = f"temp_{uuid.uuid4().hex[:8]}"
                db_available = False
                logger.warning(f"Database unavailable, using temporary session: {chat_id}")
            else:
                logger.error(f"Failed to create chat session: {chat_session}")
                return jsonify({'error': 'Failed to create chat session. Please try again.'}), 500
        else:
            # Existing chat session - fetch conversation history
            if db_available and not chat_id.startswith('temp_'):
                try:
                    messages, msg_status = auth_service.get_chat_messages(chat_id)
                    if msg_status == 200 and messages:
                        # Convert to conversation history format (last 10 messages for context)
                        for msg in messages[-10:]:
                            role = "user" if msg.get('role') == 'user' else "assistant"
                            conversation_history.append({
                                "role": role,
                                "content": msg.get('content', '')
                            })
                        logger.debug(f"Loaded {len(conversation_history)} messages for context")
                except Exception as e:
                    logger.warning(f"Could not fetch conversation history: {e}")
        
        # Get RAG components
        vectorstore = current_app.config.get('RAG_VECTORSTORE')
        llm = current_app.config.get('RAG_LLM')
        
        if vectorstore is None or llm is None:
            logger.warning("RAG components not available, using fallback")
            def generate_fallback():
                yield json.dumps({'chat_id': chat_id}) + '\n'
                response = "I apologize, but the AI system is currently unavailable. Please try again later."
                for char in response:
                    yield json.dumps({'token': char}) + '\n'
                    time.sleep(0.03)
                yield json.dumps({'done': True, 'error': 'system_unavailable'}) + '\n'
            
            return Response(generate_fallback(), mimetype='application/json')
        
        bot_response = ""
        stream_error = None
        
        def save_messages_async():
            """Save messages to database in background thread AFTER streaming completes"""
            # Skip saving for temporary sessions (database unavailable)
            if chat_id.startswith('temp_'):
                logger.debug("Skipping message save for temporary session")
                return
            
            try:
                logger.debug("Saving messages to database in background...")
                
                # Save user message
                msg_result, msg_status = auth_service.save_chat_message(chat_id, 'user', user_message)
                if msg_status == 200:
                    logger.debug("User message saved")
                else:
                    logger.warning(f"Failed to save user message: {msg_result}")
                
                # Save bot response (even if partial due to error)
                if bot_response:
                    msg_result, msg_status = auth_service.save_chat_message(chat_id, 'bot', bot_response)
                    if msg_status == 200:
                        logger.debug(f"Bot response saved ({len(bot_response)} chars)")
                    else:
                        logger.warning(f"Failed to save bot response: {msg_result}")
                        
            except Exception as e:
                logger.error(f"Error saving messages in background: {str(e)}")
                logger.debug(f"Traceback: {traceback.format_exc()}")
        
        def generate():
            nonlocal bot_response, stream_error
            try:
                logger.debug("Starting streaming with conversation history...")
                chunk_count = 0
                start_time = time.time()
                max_chunks = 10000  # Safety limit to prevent infinite loops
                last_chunk_time = start_time
                
                # Send chat_id FIRST - immediate flush
                yield json.dumps({'chat_id': chat_id}) + '\n'
                
                # Stream the response with conversation history
                for chunk in stream_with_history(user_message, vectorstore, llm, conversation_history):
                    if chunk:
                        bot_response += chunk
                        chunk_count += 1
                        current_time = time.time()
                        
                        # Safety check for max chunks
                        if chunk_count > max_chunks:
                            logger.warning(f"Hit max chunk limit ({max_chunks}) - stopping stream")
                            stream_error = "response_too_long"
                            break
                        
                        # Timeout check (if no chunks for 30 seconds)
                        if current_time - last_chunk_time > 30:
                            logger.warning("Stream timeout - no chunks for 30s")
                            stream_error = "stream_timeout"
                            break
                        
                        last_chunk_time = current_time
                        
                        # Yield each token immediately - no buffering
                        yield json.dumps({'token': chunk}) + '\n'
                        
                        # Log progress every 100 chunks (debug level)
                        if chunk_count % 100 == 0:
                            elapsed = current_time - start_time
                            logger.debug(f"Progress: {chunk_count} chunks, {len(bot_response)} chars, {elapsed:.1f}s")
                
                elapsed_time = time.time() - start_time
                logger.debug(f"Stream completed: {chunk_count} chunks, {len(bot_response)} chars in {elapsed_time:.2f}s")
                
                # Send completion signal with metadata
                completion_data = {
                    'done': True,
                    'chunks': chunk_count,
                    'chars': len(bot_response),
                    'time': round(elapsed_time, 2)
                }
                
                if stream_error:
                    completion_data['warning'] = stream_error
                    logger.warning(f"Stream completed with warning: {stream_error}")
                
                yield json.dumps(completion_data) + '\n'
                
                # Save to database AFTER streaming completes (in background thread)
                threading.Thread(target=save_messages_async, daemon=True).start()
                
            except Exception as e:
                # Better error handling with actual error message
                error_type = type(e).__name__
                error_msg = str(e)
                logger.error(f"Error in RAG chain ({error_type}): {error_msg}")
                logger.debug(f"Traceback: {traceback.format_exc()}")
                
                # If we have partial response, send it
                if bot_response:
                    logger.warning(f"Sending partial response ({len(bot_response)} chars)")
                
                # Send error with details
                error_data = {
                    'error': 'An error occurred while generating the response.',
                    'error_type': error_type,
                    'done': True,
                    'partial': len(bot_response) > 0
                }
                
                # Don't expose internal errors to user, but log them
                if 'timeout' in error_msg.lower():
                    error_data['user_message'] = 'The request took too long. Please try a simpler question.'
                elif 'rate' in error_msg.lower() or 'quota' in error_msg.lower():
                    error_data['user_message'] = 'The service is currently busy. Please try again in a moment.'
                else:
                    error_data['user_message'] = 'An unexpected error occurred. Please try again.'
                
                yield json.dumps(error_data) + '\n'
                
                # Still save partial response if available
                if bot_response:
                    threading.Thread(target=save_messages_async, daemon=True).start()
        
        return Response(generate(), mimetype='application/json')
        
    except Exception as e:
        logger.error(f"Error in chat_api: {str(e)}")
        logger.debug(f"Traceback: {traceback.format_exc()}")
        return jsonify({'error': 'Internal server error'}), 500

@bp.route('/api/chat/history', methods=['GET'])
@login_required
def get_chat_history():
    """Return chat history for student"""
    from .auth_service import auth_service
    
    user_id = session.get('user', {}).get('id')
    if not user_id:
        return jsonify({'error': 'User not authenticated'}), 401
    
    sessions, status = auth_service.get_user_chat_sessions(user_id)
    
    if status == 200:
        return jsonify({'history': sessions})
    
    return jsonify({'error': 'Failed to load chat history'}), 500

@bp.route('/api/chat/<chat_id>', methods=['GET'])
@login_required
def get_chat(chat_id):
    """Get specific chat conversation"""
    from .auth_service import auth_service
    
    messages, status = auth_service.get_chat_messages(chat_id)
    
    if status == 200:
        return jsonify({'chat_id': chat_id, 'messages': messages})
    
    return jsonify({'error': 'Failed to load chat'}), 500

@bp.route('/api/chat/<chat_id>', methods=['DELETE'])
@login_required
def delete_chat(chat_id):
    """Delete a chat session"""
    from .auth_service import auth_service
    
    result, status = auth_service.delete_chat_session(chat_id)
    return jsonify(result), status

@bp.route('/api/chat/<chat_id>/title', methods=['PUT'])
@login_required
def update_chat_title(chat_id):
    """Update chat session title"""
    from .auth_service import auth_service
    
    data = request.get_json()
    title = data.get('title', '')
    
    if not title:
        return jsonify({'error': 'Title is required'}), 400
    
    result, status = auth_service.update_chat_session_title(chat_id, title)
    return jsonify(result), status

@bp.route('/api/search', methods=['POST'])
@login_required
def search_documents():
    """Search for relevant documents using the vectorstore"""
    from .rag_service import is_allowed, smart_retrieve
    
    data = request.get_json()
    query = data.get('query', '')
    
    if not is_allowed(query):
        return jsonify({'error': 'Sorry, I can\'t assist with that.'}), 400
    
    vectorstore = current_app.config.get('RAG_VECTORSTORE')
    
    if vectorstore is None:
        return jsonify({'error': 'Search system unavailable'}), 503
    
    try:
        # Use smart retrieval
        docs = smart_retrieve(query, vectorstore)
        
        results = []
        for doc in docs:
            results.append({
                'content': doc.page_content,
                'metadata': doc.metadata
            })
        
        return jsonify({'results': results})
    
    except Exception as e:
        logger.error(f"Search error: {e}")
        return jsonify({'error': 'Search failed'}), 500