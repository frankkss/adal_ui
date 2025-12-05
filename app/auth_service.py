from supabase import create_client, Client
from flask import current_app
import re
from datetime import datetime
import logging

# Configure logger
logger = logging.getLogger(__name__)


class AuthService:
    def __init__(self):
        self.supabase: Client = None
        self.admin_supabase: Client = None  # For bypassing RLS
    
    def init_app(self, app):
        """Initialize Supabase clients"""
        url = app.config.get('SUPABASE_URL')
        anon_key = app.config.get('SUPABASE_KEY')
        service_key = app.config.get('SUPABASE_SERVICE_KEY')
        
        if not url or not anon_key:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set")
        
        self.supabase = create_client(url, anon_key)
        
        # Initialize admin client if service key is available
        if service_key:
            self.admin_supabase = create_client(url, service_key)
            logger.info("Supabase clients initialized (anon + service)")
        else:
            self.admin_supabase = self.supabase
            logger.warning("Supabase client initialized (anon only - service key recommended)")
    
    def is_cspc_email(self, email: str) -> bool:
        """Check if email is from CSPC domain"""
        domains = current_app.config.get('ALLOWED_EMAIL_DOMAINS', ['@cspc.edu.ph', '@my.cspc.edu.ph'])
        return any(email.lower().endswith(domain.strip()) for domain in domains)
    
    def validate_email(self, email: str) -> tuple:
        """Validate email format and domain"""
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email):
            return False, "Invalid email format"
        
        if not self.is_cspc_email(email):
            return False, "Only CSPC email addresses (@cspc.edu.ph or @my.cspc.edu.ph) are allowed"
        
        return True, ""
    
    def sign_up_with_email(self, email: str, password: str, full_name: str = None):
        """Sign up with email and password"""
        try:
            is_valid, error_msg = self.validate_email(email)
            if not is_valid:
                return {"error": error_msg}, 400
            
            email_domain = "@my.cspc.edu.ph" if email.lower().endswith("@my.cspc.edu.ph") else "@cspc.edu.ph"
            
            # Sign up user with email confirmation disabled
            response = self.supabase.auth.sign_up({
                "email": email,
                "password": password,
                "options": {
                    "email_redirect_to": None,
                    "data": {
                        "full_name": full_name,
                        "email_domain": email_domain
                    }
                }
            })
            
            if response.user:
                # Check if we got a session (email confirmation disabled)
                if response.session:
                    return {
                        "message": "Account created successfully! You can now sign in.",
                        "user": {
                            "id": response.user.id,
                            "email": response.user.email,
                            "full_name": full_name
                        },
                        "can_login_immediately": True
                    }, 200
                else:
                    # Email confirmation required
                    return {
                        "message": "Account created! Please check your email to verify before signing in.",
                        "user": {
                            "id": response.user.id,
                            "email": response.user.email,
                            "full_name": full_name
                        },
                        "can_login_immediately": False
                    }, 200
            else:
                return {"error": "Sign up failed"}, 400
                
        except Exception as e:
            error_message = str(e)
            logger.error(f"Signup error: {error_message}")
            
            if "already registered" in error_message.lower() or "user already exists" in error_message.lower():
                return {"error": "This email is already registered. Please sign in instead."}, 400
            if "email" in error_message.lower() and "rate limit" in error_message.lower():
                return {"error": "Too many signup attempts. Please try again later."}, 429
            
            return {"error": f"Sign up failed: {error_message}"}, 500
    
    def sign_in_with_email(self, email: str, password: str):
        """Sign in with email and password"""
        try:
            response = self.supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            
            if response.user and response.session:
                return {
                    "message": "Sign in successful",
                    "user": {
                        "id": response.user.id,
                        "email": response.user.email,
                        "full_name": response.user.user_metadata.get("full_name", "Student"),
                        "email_confirmed": response.user.email_confirmed_at is not None
                    },
                    "session": {
                        "access_token": response.session.access_token,
                        "refresh_token": response.session.refresh_token
                    }
                }, 200
            else:
                return {"error": "Invalid credentials"}, 401
                
        except Exception as e:
            error_message = str(e)
            logger.error(f"Signin error: {error_message}")
            
            if "invalid login credentials" in error_message.lower():
                return {"error": "Invalid email or password. Please check your credentials and try again."}, 401
            if "email not confirmed" in error_message.lower():
                return {"error": "Please verify your email before signing in. Check your inbox for the verification link."}, 401
            
            return {"error": "Sign in failed. Please try again."}, 500
    
    def sign_in_with_google(self):
        """Get Google OAuth URL"""
        try:
            app_url = current_app.config.get('APP_URL', 'http://localhost:5000')
            
            response = self.supabase.auth.sign_in_with_oauth({
                "provider": "google",
                "options": {
                    "redirect_to": f"{app_url}/auth/callback",
                    "scopes": "email profile"
                }
            })
            
            if response and hasattr(response, 'url'):
                return {"url": response.url}, 200
            else:
                return {"error": "Failed to generate Google OAuth URL"}, 500
            
        except Exception as e:
            logger.error(f"Google OAuth error: {str(e)}")
            return {"error": f"Google sign in failed: {str(e)}"}, 500
    
    def exchange_code_for_session(self, code: str):
        """Exchange OAuth code for session"""
        try:
            response = self.supabase.auth.exchange_code_for_session(code)
            
            if response.user and response.session:
                return {
                    "user": {
                        "id": response.user.id,
                        "email": response.user.email,
                        "full_name": response.user.user_metadata.get("full_name", "Student")
                    },
                    "session": {
                        "access_token": response.session.access_token,
                        "refresh_token": response.session.refresh_token
                    }
                }, 200
            else:
                return {"error": "Failed to exchange code for session"}, 400
                
        except Exception as e:
            logger.error(f"Code exchange error: {str(e)}")
            return {"error": f"Authentication failed: {str(e)}"}, 500
    
    def sign_out(self):
        """Sign out current user"""
        try:
            self.supabase.auth.sign_out()
            return {"message": "Signed out successfully"}, 200
        except Exception as e:
            return {"error": f"Sign out failed: {str(e)}"}, 500
    
    def get_user(self, access_token: str):
        """Get user from access token"""
        try:
            response = self.supabase.auth.get_user(access_token)
            if response.user:
                return {
                    "user": {
                        "id": response.user.id,
                        "email": response.user.email,
                        "full_name": response.user.user_metadata.get("full_name", "Student"),
                        "email_confirmed": response.user.email_confirmed_at is not None
                    }
                }, 200
            return {"error": "User not found"}, 404
        except Exception as e:
            return {"error": f"Failed to get user: {str(e)}"}, 500
    
    # ============================================
    # Chat Session Management Methods (using service key to bypass RLS)
    # ============================================
    
    def _is_service_unavailable(self, error_str: str) -> bool:
        """Check if error is due to service unavailability"""
        unavailable_indicators = [
            'cloudflare', '500 internal server error', '502', '503', '504',
            'connection', 'timeout', 'unavailable'
        ]
        error_lower = error_str.lower()
        return any(indicator in error_lower for indicator in unavailable_indicators)
    
    def create_chat_session(self, user_id: str, title: str):
        """Create a new chat session (using service key to bypass RLS)"""
        try:
            # Use admin client to bypass RLS
            response = self.admin_supabase.table('chat_sessions').insert({
                'user_id': user_id,
                'title': title
            }).execute()
            
            if response.data and len(response.data) > 0:
                logger.debug(f"Created chat session: {response.data[0]['id']}")
                return response.data[0], 200
            
            logger.error("No data returned from insert")
            return {"error": "Failed to create chat session"}, 500
            
        except Exception as e:
            error_str = str(e)
            logger.error(f"Create chat session error: {error_str}")
            
            if self._is_service_unavailable(error_str):
                return {"error": "Database service is temporarily unavailable. Please try again in a moment."}, 503
            
            return {"error": "Failed to create chat session. Please try again."}, 500
    
    def get_user_chat_sessions(self, user_id: str):
        """Get all chat sessions for a user"""
        try:
            response = self.admin_supabase.table('chat_sessions')\
                .select('*')\
                .eq('user_id', user_id)\
                .order('updated_at', desc=True)\
                .execute()
            
            logger.debug(f"Fetched {len(response.data)} chat sessions")
            return response.data, 200
            
        except Exception as e:
            error_str = str(e)
            logger.error(f"Get chat sessions error: {error_str}")
            
            if self._is_service_unavailable(error_str):
                return [], 200  # Return empty list instead of error for better UX
            
            return {"error": "Failed to load chat history"}, 500
    
    def save_chat_message(self, chat_session_id: str, role: str, content: str):
        """Save a chat message"""
        try:
            # Insert message
            response = self.admin_supabase.table('chat_messages').insert({
                'chat_session_id': chat_session_id,
                'role': role,
                'content': content
            }).execute()
            
            if response.data and len(response.data) > 0:
                logger.debug(f"Saved {role} message to chat {chat_session_id}")
                
                # Update chat session timestamp
                try:
                    self.admin_supabase.table('chat_sessions')\
                        .update({'updated_at': datetime.utcnow().isoformat()})\
                        .eq('id', chat_session_id)\
                        .execute()
                except Exception:
                    pass  # Non-critical, don't fail if timestamp update fails
                
                return response.data[0], 200
            
            return {"error": "Failed to save message"}, 500
            
        except Exception as e:
            error_str = str(e)
            logger.error(f"Save message error: {error_str}")
            
            if self._is_service_unavailable(error_str):
                # Log but don't fail - message saving is non-critical for UX
                logger.warning("Database unavailable, message not saved")
                return {"warning": "Message not saved due to service unavailability"}, 200
            
            return {"error": "Failed to save message"}, 500
    
    def get_chat_messages(self, chat_session_id: str):
        """Get all messages for a chat session"""
        try:
            response = self.admin_supabase.table('chat_messages')\
                .select('*')\
                .eq('chat_session_id', chat_session_id)\
                .order('created_at', desc=False)\
                .execute()
            
            logger.debug(f"Fetched {len(response.data)} messages")
            return response.data, 200
            
        except Exception as e:
            logger.error(f"Get messages error: {str(e)}")
            return {"error": f"Database error: {str(e)}"}, 500
    
    def delete_chat_session(self, chat_session_id: str):
        """Delete a chat session (CASCADE deletes messages)"""
        try:
            response = self.admin_supabase.table('chat_sessions')\
                .delete()\
                .eq('id', chat_session_id)\
                .execute()
            
            logger.debug(f"Deleted chat session: {chat_session_id}")
            return {"message": "Chat session deleted successfully"}, 200
            
        except Exception as e:
            logger.error(f"Delete chat session error: {str(e)}")
            return {"error": f"Database error: {str(e)}"}, 500
    
    def update_chat_session_title(self, chat_session_id: str, title: str):
        """Update chat session title"""
        try:
            response = self.admin_supabase.table('chat_sessions')\
                .update({'title': title})\
                .eq('id', chat_session_id)\
                .execute()
            
            if response.data and len(response.data) > 0:
                logger.debug(f"Updated chat title: {chat_session_id}")
                return response.data[0], 200
            
            return {"error": "Failed to update title"}, 500
            
        except Exception as e:
            logger.error(f"Update title error: {str(e)}")
            return {"error": f"Database error: {str(e)}"}, 500

auth_service = AuthService()