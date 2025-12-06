from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

# Get the base directory of the application
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


class Config:
    """Base configuration class"""
    
    # Security - MUST be set in production
    SECRET_KEY = os.getenv('SECRET_KEY')
    if not SECRET_KEY:
        import secrets
        SECRET_KEY = secrets.token_hex(32)
        print("⚠️  WARNING: SECRET_KEY not set. Using random key (sessions won't persist across restarts)")
    
    # Debug mode - defaults to False for production safety
    DEBUG = os.getenv('DEBUG', 'False').lower() in ('true', '1', 't')
    
    # Google API Configuration
    GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
    
    # RAG Configuration - use absolute path based on BASE_DIR
    INDEX_PATH = os.getenv('INDEX_PATH', os.path.join(BASE_DIR, 'index'))
    
    # Supabase Configuration
    SUPABASE_URL = os.getenv('SUPABASE_URL')
    SUPABASE_KEY = os.getenv('SUPABASE_KEY')
    SUPABASE_SERVICE_KEY = os.getenv('SUPABASE_SERVICE_KEY')
    
    # Application URL - MUST be set in production for OAuth callbacks
    APP_URL = os.getenv('APP_URL', 'http://localhost:5000')
    
    # Allowed email domains for CSPC
    ALLOWED_EMAIL_DOMAINS = os.getenv(
        'ALLOWED_EMAIL_DOMAINS', 
        '@cspc.edu.ph,@my.cspc.edu.ph'
    ).split(',')
    
    # Session configuration
    SESSION_COOKIE_SECURE = os.getenv('SESSION_COOKIE_SECURE', 'False').lower() in ('true', '1', 't')
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    
    @classmethod
    def validate(cls):
        """Validate required configuration"""
        errors = []
        
        if not cls.GOOGLE_API_KEY:
            errors.append("GOOGLE_API_KEY is required")
        if not cls.SUPABASE_URL:
            errors.append("SUPABASE_URL is required")
        if not cls.SUPABASE_KEY:
            errors.append("SUPABASE_KEY is required")
        
        if errors:
            raise ValueError(f"Configuration errors: {', '.join(errors)}")
        
        return True


class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    SESSION_COOKIE_SECURE = True  # Require HTTPS in production


class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    SESSION_COOKIE_SECURE = False


# Select configuration based on environment
def get_config():
    env = os.getenv('FLASK_ENV', 'production').lower()
    configs = {
        'development': DevelopmentConfig,
        'production': ProductionConfig,
    }
    return configs.get(env, ProductionConfig)