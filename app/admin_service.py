"""
Admin Service for Dashboard Analytics
Handles admin authentication and analytics data retrieval
"""
from datetime import datetime, timedelta
from collections import Counter
import re
import logging

logger = logging.getLogger(__name__)


class AdminService:
    def __init__(self):
        self.supabase = None
    
    def init_app(self, supabase_client):
        """Initialize with Supabase admin client"""
        self.supabase = supabase_client
    
    # ============================================
    # Admin Authentication
    # ============================================
    
    def is_admin(self, user_id: str) -> bool:
        """Check if user is an admin"""
        try:
            response = self.supabase.table('admin_users')\
                .select('id, role')\
                .eq('user_id', user_id)\
                .execute()
            
            return len(response.data) > 0
        except Exception as e:
            logger.error(f"Error checking admin status: {e}")
            return False
    
    def get_admin_role(self, user_id: str) -> str:
        """Get admin role (admin or super_admin)"""
        try:
            response = self.supabase.table('admin_users')\
                .select('role')\
                .eq('user_id', user_id)\
                .single()\
                .execute()
            
            if response.data:
                return response.data.get('role', 'admin')
            return None
        except Exception as e:
            logger.error(f"Error getting admin role: {e}")
            return None
    
    def add_admin(self, user_id: str, role: str = 'admin') -> tuple:
        """Add a user as admin"""
        try:
            response = self.supabase.table('admin_users').insert({
                'user_id': user_id,
                'role': role
            }).execute()
            
            if response.data:
                logger.info(f"Added admin user: {user_id} with role: {role}")
                return {'message': 'Admin added successfully'}, 200
            return {'error': 'Failed to add admin'}, 500
        except Exception as e:
            logger.error(f"Error adding admin: {e}")
            if 'duplicate' in str(e).lower():
                return {'error': 'User is already an admin'}, 400
            return {'error': str(e)}, 500
    
    def remove_admin(self, user_id: str) -> tuple:
        """Remove admin status from user"""
        try:
            response = self.supabase.table('admin_users')\
                .delete()\
                .eq('user_id', user_id)\
                .execute()
            
            logger.info(f"Removed admin user: {user_id}")
            return {'message': 'Admin removed successfully'}, 200
        except Exception as e:
            logger.error(f"Error removing admin: {e}")
            return {'error': str(e)}, 500
    
    # ============================================
    # Query Analytics
    # ============================================
    
    def log_query(self, user_id: str, query_text: str, query_type: str = 'chat',
                  response_time_ms: int = None, tokens_used: int = None,
                  was_successful: bool = True, error_type: str = None) -> tuple:
        """Log a user query for analytics"""
        try:
            response = self.supabase.table('query_analytics').insert({
                'user_id': user_id,
                'query_text': query_text,
                'query_type': query_type,
                'response_time_ms': response_time_ms,
                'tokens_used': tokens_used,
                'was_successful': was_successful,
                'error_type': error_type
            }).execute()
            
            if response.data:
                # Also update popular queries
                self._update_popular_query(query_text)
                return response.data[0], 200
            return {'error': 'Failed to log query'}, 500
        except Exception as e:
            logger.error(f"Error logging query: {e}")
            return {'error': str(e)}, 500
    
    def _update_popular_query(self, query_text: str):
        """Extract keywords and update popular queries"""
        try:
            # Simple keyword extraction - extract meaningful words
            words = re.findall(r'\b[a-zA-Z]{4,}\b', query_text.lower())
            # Remove common words
            stop_words = {'what', 'when', 'where', 'which', 'that', 'this', 'have', 'been', 
                         'with', 'from', 'your', 'about', 'they', 'would', 'there', 'their',
                         'will', 'each', 'make', 'like', 'into', 'more', 'could', 'some'}
            keywords = [w for w in words if w not in stop_words]
            
            if keywords:
                # Use most common keyword as pattern
                pattern = ' '.join(keywords[:3])  # Use first 3 keywords
                
                # Try to update existing pattern or insert new
                existing = self.supabase.table('popular_queries')\
                    .select('id, count')\
                    .eq('query_pattern', pattern)\
                    .execute()
                
                if existing.data:
                    # Update count
                    self.supabase.table('popular_queries')\
                        .update({'count': existing.data[0]['count'] + 1, 'last_queried_at': datetime.utcnow().isoformat()})\
                        .eq('id', existing.data[0]['id'])\
                        .execute()
                else:
                    # Insert new pattern
                    self.supabase.table('popular_queries').insert({
                        'query_pattern': pattern,
                        'category': self._categorize_query(query_text),
                        'count': 1
                    }).execute()
        except Exception as e:
            logger.debug(f"Error updating popular query: {e}")
    
    def _categorize_query(self, query_text: str) -> str:
        """Categorize query based on content"""
        query_lower = query_text.lower()
        
        categories = {
            'thesis': ['thesis', 'research', 'study', 'paper', 'dissertation'],
            'academic': ['course', 'subject', 'class', 'curriculum', 'syllabus'],
            'library': ['book', 'journal', 'publication', 'article', 'reference'],
            'technical': ['code', 'programming', 'software', 'system', 'database'],
            'general': ['how', 'what', 'when', 'where', 'why']
        }
        
        for category, keywords in categories.items():
            if any(kw in query_lower for kw in keywords):
                return category
        
        return 'other'
    
    # ============================================
    # Dashboard Statistics
    # ============================================
    
    def get_dashboard_stats(self, days: int = 30) -> tuple:
        """Get comprehensive dashboard statistics"""
        try:
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)
            
            stats = {
                'summary': self._get_summary_stats(start_date, end_date),
                'daily_queries': self._get_daily_query_stats(start_date, end_date),
                'hourly_distribution': self._get_hourly_distribution(start_date, end_date),
                'popular_queries': self._get_popular_queries(limit=10),
                'query_categories': self._get_query_categories(),
                'user_activity': self._get_user_activity_stats(start_date, end_date),
                'error_stats': self._get_error_stats(start_date, end_date),
                'recent_queries': self._get_recent_queries(limit=20)
            }
            
            return stats, 200
        except Exception as e:
            logger.error(f"Error getting dashboard stats: {e}")
            return {'error': str(e)}, 500
    
    def _get_summary_stats(self, start_date: datetime, end_date: datetime) -> dict:
        """Get summary statistics"""
        try:
            # Total queries in period
            queries_response = self.supabase.table('query_analytics')\
                .select('id', count='exact')\
                .gte('created_at', start_date.isoformat())\
                .lte('created_at', end_date.isoformat())\
                .execute()
            
            total_queries = queries_response.count or 0
            
            # Unique users in period
            users_response = self.supabase.table('query_analytics')\
                .select('user_id')\
                .gte('created_at', start_date.isoformat())\
                .lte('created_at', end_date.isoformat())\
                .execute()
            
            unique_users = len(set(q['user_id'] for q in users_response.data if q.get('user_id')))
            
            # Total chat sessions
            sessions_response = self.supabase.table('chat_sessions')\
                .select('id', count='exact')\
                .gte('created_at', start_date.isoformat())\
                .lte('created_at', end_date.isoformat())\
                .execute()
            
            total_sessions = sessions_response.count or 0
            
            # Average response time
            avg_response = self.supabase.table('query_analytics')\
                .select('response_time_ms')\
                .gte('created_at', start_date.isoformat())\
                .lte('created_at', end_date.isoformat())\
                .not_.is_('response_time_ms', 'null')\
                .execute()
            
            avg_time = 0
            if avg_response.data:
                times = [r['response_time_ms'] for r in avg_response.data if r.get('response_time_ms')]
                if times:
                    avg_time = sum(times) / len(times)
            
            # Success rate
            success_response = self.supabase.table('query_analytics')\
                .select('was_successful')\
                .gte('created_at', start_date.isoformat())\
                .lte('created_at', end_date.isoformat())\
                .execute()
            
            success_rate = 100.0
            if success_response.data:
                successful = sum(1 for r in success_response.data if r.get('was_successful', True))
                success_rate = (successful / len(success_response.data)) * 100 if success_response.data else 100
            
            # Compare with previous period
            prev_start = start_date - timedelta(days=(end_date - start_date).days)
            prev_queries_response = self.supabase.table('query_analytics')\
                .select('id', count='exact')\
                .gte('created_at', prev_start.isoformat())\
                .lt('created_at', start_date.isoformat())\
                .execute()
            
            prev_queries = prev_queries_response.count or 0
            query_growth = ((total_queries - prev_queries) / prev_queries * 100) if prev_queries > 0 else 0
            
            return {
                'total_queries': total_queries,
                'unique_users': unique_users,
                'total_sessions': total_sessions,
                'avg_response_time_ms': round(avg_time, 2),
                'success_rate': round(success_rate, 2),
                'query_growth_percent': round(query_growth, 2)
            }
        except Exception as e:
            logger.error(f"Error getting summary stats: {e}")
            return {}
    
    def _get_daily_query_stats(self, start_date: datetime, end_date: datetime) -> list:
        """Get daily query counts"""
        try:
            response = self.supabase.table('query_analytics')\
                .select('created_at, user_id')\
                .gte('created_at', start_date.isoformat())\
                .lte('created_at', end_date.isoformat())\
                .execute()
            
            # Group by date
            daily_stats = {}
            for item in response.data:
                date = item['created_at'][:10]  # Extract date part
                if date not in daily_stats:
                    daily_stats[date] = {'queries': 0, 'users': set()}
                daily_stats[date]['queries'] += 1
                if item.get('user_id'):
                    daily_stats[date]['users'].add(item['user_id'])
            
            # Convert to list format
            result = [
                {
                    'date': date,
                    'queries': stats['queries'],
                    'unique_users': len(stats['users'])
                }
                for date, stats in sorted(daily_stats.items())
            ]
            
            return result
        except Exception as e:
            logger.error(f"Error getting daily stats: {e}")
            return []
    
    def _get_hourly_distribution(self, start_date: datetime, end_date: datetime) -> list:
        """Get hourly query distribution"""
        try:
            response = self.supabase.table('query_analytics')\
                .select('created_at')\
                .gte('created_at', start_date.isoformat())\
                .lte('created_at', end_date.isoformat())\
                .execute()
            
            # Count by hour
            hourly_counts = Counter()
            for item in response.data:
                # Parse ISO timestamp and extract hour
                hour = int(item['created_at'][11:13])
                hourly_counts[hour] += 1
            
            # Ensure all 24 hours are represented
            result = [
                {'hour': h, 'count': hourly_counts.get(h, 0)}
                for h in range(24)
            ]
            
            return result
        except Exception as e:
            logger.error(f"Error getting hourly distribution: {e}")
            return []
    
    def _get_popular_queries(self, limit: int = 10) -> list:
        """Get most popular query patterns"""
        try:
            response = self.supabase.table('popular_queries')\
                .select('query_pattern, category, count, last_queried_at')\
                .order('count', desc=True)\
                .limit(limit)\
                .execute()
            
            return response.data
        except Exception as e:
            logger.error(f"Error getting popular queries: {e}")
            return []
    
    def _get_query_categories(self) -> list:
        """Get query distribution by category"""
        try:
            response = self.supabase.table('popular_queries')\
                .select('category, count')\
                .execute()
            
            # Aggregate by category
            category_counts = Counter()
            for item in response.data:
                category = item.get('category', 'other')
                category_counts[category] += item.get('count', 0)
            
            result = [
                {'category': cat, 'count': count}
                for cat, count in category_counts.most_common()
            ]
            
            return result
        except Exception as e:
            logger.error(f"Error getting query categories: {e}")
            return []
    
    def _get_user_activity_stats(self, start_date: datetime, end_date: datetime) -> dict:
        """Get user activity statistics"""
        try:
            response = self.supabase.table('query_analytics')\
                .select('user_id')\
                .gte('created_at', start_date.isoformat())\
                .lte('created_at', end_date.isoformat())\
                .execute()
            
            user_query_counts = Counter()
            for item in response.data:
                if item.get('user_id'):
                    user_query_counts[item['user_id']] += 1
            
            if not user_query_counts:
                return {
                    'most_active_users': [],
                    'avg_queries_per_user': 0,
                    'power_users': 0  # Users with >10 queries
                }
            
            # Get top 5 most active users
            top_users = user_query_counts.most_common(5)
            
            return {
                'most_active_users': [
                    {'user_id': uid, 'query_count': count}
                    for uid, count in top_users
                ],
                'avg_queries_per_user': round(sum(user_query_counts.values()) / len(user_query_counts), 2),
                'power_users': sum(1 for count in user_query_counts.values() if count > 10)
            }
        except Exception as e:
            logger.error(f"Error getting user activity stats: {e}")
            return {}
    
    def _get_error_stats(self, start_date: datetime, end_date: datetime) -> dict:
        """Get error statistics"""
        try:
            response = self.supabase.table('query_analytics')\
                .select('was_successful, error_type')\
                .gte('created_at', start_date.isoformat())\
                .lte('created_at', end_date.isoformat())\
                .eq('was_successful', False)\
                .execute()
            
            error_counts = Counter()
            for item in response.data:
                error_type = item.get('error_type', 'unknown')
                error_counts[error_type] += 1
            
            return {
                'total_errors': len(response.data),
                'error_types': [
                    {'type': err_type, 'count': count}
                    for err_type, count in error_counts.most_common()
                ]
            }
        except Exception as e:
            logger.error(f"Error getting error stats: {e}")
            return {'total_errors': 0, 'error_types': []}
    
    def _get_recent_queries(self, limit: int = 20) -> list:
        """Get recent queries for activity feed"""
        try:
            response = self.supabase.table('query_analytics')\
                .select('id, user_id, query_text, query_type, response_time_ms, was_successful, created_at')\
                .order('created_at', desc=True)\
                .limit(limit)\
                .execute()
            
            # Truncate query text for display
            for item in response.data:
                if len(item.get('query_text', '')) > 100:
                    item['query_text'] = item['query_text'][:100] + '...'
            
            return response.data
        except Exception as e:
            logger.error(f"Error getting recent queries: {e}")
            return []
    
    # ============================================
    # User Management
    # ============================================
    
    def get_all_users(self, page: int = 1, per_page: int = 50) -> tuple:
        """Get all users with their query counts"""
        try:
            # Get users from auth.users via chat_sessions (since we can't directly query auth.users)
            offset = (page - 1) * per_page
            
            response = self.supabase.table('chat_sessions')\
                .select('user_id')\
                .execute()
            
            # Get unique users and their session counts
            user_sessions = Counter()
            for item in response.data:
                user_sessions[item['user_id']] += 1
            
            # Get query counts
            query_response = self.supabase.table('query_analytics')\
                .select('user_id')\
                .execute()
            
            user_queries = Counter()
            for item in query_response.data:
                if item.get('user_id'):
                    user_queries[item['user_id']] += 1
            
            # Combine data
            users = []
            for user_id in set(user_sessions.keys()) | set(user_queries.keys()):
                users.append({
                    'user_id': user_id,
                    'session_count': user_sessions.get(user_id, 0),
                    'query_count': user_queries.get(user_id, 0)
                })
            
            # Sort by query count
            users.sort(key=lambda x: x['query_count'], reverse=True)
            
            # Paginate
            paginated = users[offset:offset + per_page]
            
            return {
                'users': paginated,
                'total': len(users),
                'page': page,
                'per_page': per_page
            }, 200
        except Exception as e:
            logger.error(f"Error getting users: {e}")
            return {'error': str(e)}, 500
    
    def get_user_details(self, user_id: str) -> tuple:
        """Get detailed information about a specific user"""
        try:
            # Get user's chat sessions
            sessions_response = self.supabase.table('chat_sessions')\
                .select('id, title, created_at, updated_at')\
                .eq('user_id', user_id)\
                .order('updated_at', desc=True)\
                .limit(10)\
                .execute()
            
            # Get user's recent queries
            queries_response = self.supabase.table('query_analytics')\
                .select('query_text, query_type, response_time_ms, was_successful, created_at')\
                .eq('user_id', user_id)\
                .order('created_at', desc=True)\
                .limit(20)\
                .execute()
            
            # Get query count
            query_count_response = self.supabase.table('query_analytics')\
                .select('id', count='exact')\
                .eq('user_id', user_id)\
                .execute()
            
            return {
                'user_id': user_id,
                'total_queries': query_count_response.count or 0,
                'recent_sessions': sessions_response.data,
                'recent_queries': queries_response.data
            }, 200
        except Exception as e:
            logger.error(f"Error getting user details: {e}")
            return {'error': str(e)}, 500


# Global instance
admin_service = AdminService()
