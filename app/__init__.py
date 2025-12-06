from flask import Flask
from config import Config, get_config
import os
import traceback
import logging


def create_app(config_class=None):
    """Application factory for Flask app"""
    
    # Use provided config or get based on environment
    if config_class is None:
        config_class = get_config()
    
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Configure logging based on environment
    log_level = getattr(logging, app.config.get('LOG_LEVEL', 'INFO').upper(), logging.INFO)
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
    # Suppress verbose warnings in production
    if not app.config.get('DEBUG'):
        # Suppress Abseil/gRPC warnings
        os.environ['GRPC_VERBOSITY'] = 'ERROR'
        os.environ['GLOG_minloglevel'] = '2'
        logging.getLogger('absl').setLevel(logging.ERROR)
        logging.getLogger('google.auth').setLevel(logging.WARNING)
        logging.getLogger('urllib3').setLevel(logging.WARNING)
        logging.getLogger('httpx').setLevel(logging.WARNING)
    
    # Validate configuration
    try:
        config_class.validate()
    except ValueError as e:
        logger.error(f"Configuration validation failed: {e}")
        raise
    
    # Initialize Supabase Auth
    try:
        from .auth_service import auth_service
        auth_service.init_app(app)
        logger.info("Supabase authentication initialized")
    except Exception as e:
        logger.error(f"Failed to initialize Supabase auth: {str(e)}")
        raise
    
    # Verify GOOGLE_API_KEY is loaded
    google_api_key = os.getenv("GOOGLE_API_KEY")
    if not google_api_key:
        logger.error("GOOGLE_API_KEY not found in environment variables")
        raise ValueError("GOOGLE_API_KEY not found in environment variables")
    
    logger.info(f"Google API Key loaded: {google_api_key[:10]}...")
    
    # Set the API key in environment for langchain
    os.environ["GOOGLE_API_KEY"] = google_api_key
    
    # Initialize RAG components (cached globally)
    try:
        logger.info("Initializing RAG components...")
        from .rag_service import build_streaming_chain
        
        # Check if index exists
        index_path = app.config.get('INDEX_PATH', os.path.join(os.path.dirname(__file__), '..', 'index'))
        if not os.path.exists(index_path):
            logger.warning(f"Index path not found: {index_path}")
            logger.debug(f"Current directory: {os.getcwd()}")
        
        llm, vectorstore = build_streaming_chain(persist_dir=index_path)
        app.config['RAG_LLM'] = llm
        app.config['RAG_VECTORSTORE'] = vectorstore
        logger.info("RAG components initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize RAG components: {str(e)}")
        logger.debug(f"Traceback: {traceback.format_exc()}")
        logger.warning("App will continue but RAG features may not work")
        app.config['RAG_LLM'] = None
        app.config['RAG_VECTORSTORE'] = None
    
    # Register blueprints
    with app.app_context():
        from . import routes
        app.register_blueprint(routes.bp)
    
    return app