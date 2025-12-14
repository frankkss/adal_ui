"""Admin Routes for Dashboard
Provides admin authentication and dashboard endpoints
"""
from flask import Blueprint, render_template, request, jsonify, session, redirect, url_for
from functools import wraps
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
import logging

from .admin_service import admin_service
from .upload_service import (
    process_pdf_upload, 
    get_uploaded_documents,
    delete_document,
    DuplicateDocumentError,
    PDFExtractionError
)

logger = logging.getLogger(__name__)

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


def admin_required(f):
    """Decorator to require admin access for routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('main.login'))
        
        user_id = session.get('user', {}).get('id')
        
        if not user_id or not admin_service.is_admin(user_id):
            return render_template('admin/unauthorized.html'), 403
        
        return f(*args, **kwargs)
    return decorated_function


def super_admin_required(f):
    """Decorator to require super admin access"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('main.login'))
        
        user_id = session.get('user', {}).get('id')
        
        if not user_id:
            return redirect(url_for('main.login'))
        
        role = admin_service.get_admin_role(user_id)
        if role != 'super_admin':
            return jsonify({'error': 'Super admin access required'}), 403
        
        return f(*args, **kwargs)
    return decorated_function


# ============================================
# Admin Dashboard Pages
# ============================================

@admin_bp.route('/')
@admin_required
def dashboard():
    """Admin dashboard main page"""
    user_id = session.get('user', {}).get('id')
    role = admin_service.get_admin_role(user_id)
    
    return render_template('admin/dashboard.html', 
                         user=session.get('user'),
                         admin_role=role)


@admin_bp.route('/users')
@admin_required
def users():
    """User management page"""
    user_id = session.get('user', {}).get('id')
    role = admin_service.get_admin_role(user_id)
    return render_template('admin/users.html', user=session.get('user'), admin_role=role)


@admin_bp.route('/queries')
@admin_required
def queries():
    """Query analytics page"""
    user_id = session.get('user', {}).get('id')
    role = admin_service.get_admin_role(user_id)
    return render_template('admin/queries.html', user=session.get('user'), admin_role=role)


@admin_bp.route('/settings')
@super_admin_required
def settings():
    """Admin settings page (super admin only)"""
    user_id = session.get('user', {}).get('id')
    role = admin_service.get_admin_role(user_id)
    return render_template('admin/settings.html', user=session.get('user'), admin_role=role)


# ============================================
# Admin API Endpoints
# ============================================

@admin_bp.route('/api/stats')
@admin_required
def api_stats():
    """Get dashboard statistics"""
    days = request.args.get('days', 30, type=int)
    stats, status = admin_service.get_dashboard_stats(days=days)
    
    return jsonify(stats), status


@admin_bp.route('/api/stats/summary')
@admin_required
def api_stats_summary():
    """Get summary statistics only"""
    days = request.args.get('days', 30, type=int)
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    summary = admin_service._get_summary_stats(start_date, end_date)
    return jsonify(summary), 200


@admin_bp.route('/api/stats/daily')
@admin_required
def api_stats_daily():
    """Get daily query statistics"""
    days = request.args.get('days', 30, type=int)
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    daily = admin_service._get_daily_query_stats(start_date, end_date)
    return jsonify(daily), 200


@admin_bp.route('/api/stats/hourly')
@admin_required
def api_stats_hourly():
    """Get hourly distribution"""
    days = request.args.get('days', 7, type=int)
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    hourly = admin_service._get_hourly_distribution(start_date, end_date)
    return jsonify(hourly), 200


@admin_bp.route('/api/stats/popular')
@admin_required
def api_popular_queries():
    """Get popular queries"""
    limit = request.args.get('limit', 10, type=int)
    popular = admin_service._get_popular_queries(limit=limit)
    return jsonify(popular), 200


@admin_bp.route('/api/stats/categories')
@admin_required
def api_query_categories():
    """Get query categories distribution"""
    categories = admin_service._get_query_categories()
    return jsonify(categories), 200


@admin_bp.route('/api/stats/recent')
@admin_required
def api_recent_queries():
    """Get recent queries"""
    limit = request.args.get('limit', 20, type=int)
    recent = admin_service._get_recent_queries(limit=limit)
    return jsonify(recent), 200


@admin_bp.route('/api/stats/errors')
@admin_required
def api_error_stats():
    """Get error statistics"""
    days = request.args.get('days', 30, type=int)
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=days)
    
    errors = admin_service._get_error_stats(start_date, end_date)
    return jsonify(errors), 200


# ============================================
# User Management API
# ============================================

@admin_bp.route('/api/users')
@admin_required
def api_users():
    """Get all users with pagination"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    
    result, status = admin_service.get_all_users(page=page, per_page=per_page)
    return jsonify(result), status


@admin_bp.route('/api/users/<user_id>')
@admin_required
def api_user_details(user_id):
    """Get user details"""
    result, status = admin_service.get_user_details(user_id)
    return jsonify(result), status


# ============================================
# Admin Management API (Super Admin Only)
# ============================================

@admin_bp.route('/api/admins', methods=['GET'])
@super_admin_required
def api_get_admins():
    """Get all admin users"""
    try:
        response = admin_service.supabase.table('admin_users')\
            .select('id, user_id, role, created_at')\
            .execute()
        
        return jsonify({'admins': response.data}), 200
    except Exception as e:
        logger.error(f"Error fetching admins: {e}")
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/api/admins', methods=['POST'])
@super_admin_required
def api_add_admin():
    """Add a new admin user"""
    data = request.get_json()
    user_id = data.get('user_id')
    role = data.get('role', 'admin')
    
    if not user_id:
        return jsonify({'error': 'user_id is required'}), 400
    
    if role not in ['admin', 'super_admin']:
        return jsonify({'error': 'Invalid role'}), 400
    
    result, status = admin_service.add_admin(user_id, role)
    return jsonify(result), status


@admin_bp.route('/api/admins/<user_id>', methods=['DELETE'])
@super_admin_required
def api_remove_admin(user_id):
    """Remove admin status from user"""
    # Prevent removing yourself
    current_user_id = session.get('user', {}).get('id')
    if user_id == current_user_id:
        return jsonify({'error': 'Cannot remove yourself as admin'}), 400
    
    result, status = admin_service.remove_admin(user_id)
    return jsonify(result), status


# ============================================
# Check Admin Status
# ============================================

@admin_bp.route('/api/check')
def api_check_admin():
    """Check if current user is admin"""
    if 'user' not in session:
        return jsonify({'is_admin': False}), 200
    
    user_id = session.get('user', {}).get('id')
    
    is_admin = admin_service.is_admin(user_id)
    role = admin_service.get_admin_role(user_id) if is_admin else None
    
    return jsonify({
        'is_admin': is_admin,
        'role': role
    }), 200


# ============================================
# Document Upload API (Admin Only)
# ============================================

ALLOWED_EXTENSIONS = {'pdf'}

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@admin_bp.route('/upload')
@admin_required
def upload_page():
    """Document upload page"""
    user_id = session.get('user', {}).get('id')
    role = admin_service.get_admin_role(user_id)
    return render_template('admin/upload.html', user=session.get('user'), admin_role=role)


@admin_bp.route('/api/upload', methods=['POST'])
@admin_required
def api_upload_document():
    """
    Upload and index a new PDF thesis document
    
    Form fields:
    - file: PDF file (required)
    - title: Thesis title (optional, extracted from PDF if not provided)
    - url: Google Drive URL (optional)
    - department: Department/College (optional)
    - year: Publication year (optional)
    - allow_duplicate: Allow uploading even if duplicate detected (optional)
    """
    # Check if file was provided
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if not allowed_file(file.filename):
        return jsonify({'error': 'Only PDF files are allowed'}), 400
    
    # Get form data
    title = request.form.get('title', '').strip()
    url = request.form.get('url', '').strip()
    department = request.form.get('department', '').strip()
    year = request.form.get('year', '').strip()
    allow_duplicate = request.form.get('allow_duplicate', '').lower() in ('true', '1', 'yes')
    
    filename = secure_filename(file.filename)
    
    try:
        result = process_pdf_upload(
            file=file,
            filename=filename,
            title=title,
            url=url,
            department=department,
            year=year,
            allow_duplicate=allow_duplicate
        )
        
        logger.info(f"Admin {session.get('user', {}).get('email')} uploaded document: {filename}")
        return jsonify(result), 200
        
    except DuplicateDocumentError as e:
        return jsonify({
            'error': str(e),
            'error_type': 'duplicate'
        }), 409
        
    except PDFExtractionError as e:
        return jsonify({
            'error': str(e),
            'error_type': 'extraction_failed'
        }), 422
        
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        return jsonify({
            'error': f'Upload failed: {str(e)}',
            'error_type': 'unknown'
        }), 500


@admin_bp.route('/api/documents')
@admin_required
def api_list_documents():
    """Get list of all uploaded documents"""
    try:
        documents = get_uploaded_documents()
        return jsonify({
            'documents': documents,
            'total': len(documents)
        }), 200
    except Exception as e:
        logger.error(f"Error fetching documents: {e}")
        return jsonify({'error': str(e)}), 500


@admin_bp.route('/api/documents/<filename>', methods=['DELETE'])
@super_admin_required
def api_delete_document(filename):
    """
    Delete a document (super admin only)
    Note: This removes metadata but the embeddings remain in FAISS
    """
    try:
        success = delete_document(filename)
        if success:
            logger.info(f"Admin {session.get('user', {}).get('email')} deleted document: {filename}")
            return jsonify({'message': f'Document {filename} deleted'}), 200
        else:
            return jsonify({'error': 'Document not found'}), 404
    except Exception as e:
        logger.error(f"Error deleting document: {e}")
        return jsonify({'error': str(e)}), 500
