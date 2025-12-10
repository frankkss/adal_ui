-- ============================================
-- ADAL UI Admin Dashboard Database Schema
-- ============================================
-- Run this in your Supabase SQL Editor after the main schema

-- ============================================
-- Admin Users Table
-- ============================================
CREATE TABLE IF NOT EXISTS public.admin_users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    role TEXT NOT NULL DEFAULT 'admin' CHECK (role IN ('admin', 'super_admin')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id)
);

-- Index for admin lookups
CREATE INDEX IF NOT EXISTS idx_admin_users_user_id ON public.admin_users(user_id);

-- ============================================
-- Query Analytics Table (for tracking searches/queries)
-- ============================================
CREATE TABLE IF NOT EXISTS public.query_analytics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    query_text TEXT NOT NULL,
    query_type TEXT DEFAULT 'chat' CHECK (query_type IN ('chat', 'search')),
    response_time_ms INTEGER,
    tokens_used INTEGER,
    was_successful BOOLEAN DEFAULT TRUE,
    error_type TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for analytics queries
CREATE INDEX IF NOT EXISTS idx_query_analytics_user_id ON public.query_analytics(user_id);
CREATE INDEX IF NOT EXISTS idx_query_analytics_created_at ON public.query_analytics(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_query_analytics_query_type ON public.query_analytics(query_type);

-- ============================================
-- Daily Statistics Table (aggregated data)
-- ============================================
CREATE TABLE IF NOT EXISTS public.daily_statistics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    date DATE NOT NULL UNIQUE,
    total_queries INTEGER DEFAULT 0,
    total_users INTEGER DEFAULT 0,
    active_users INTEGER DEFAULT 0,
    new_users INTEGER DEFAULT 0,
    total_chat_sessions INTEGER DEFAULT 0,
    avg_response_time_ms INTEGER,
    total_tokens_used INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for date lookups
CREATE INDEX IF NOT EXISTS idx_daily_statistics_date ON public.daily_statistics(date DESC);

-- ============================================
-- Popular Queries Table (for trending topics)
-- ============================================
CREATE TABLE IF NOT EXISTS public.popular_queries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query_pattern TEXT NOT NULL,
    category TEXT,
    count INTEGER DEFAULT 1,
    last_queried_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for popular queries
CREATE INDEX IF NOT EXISTS idx_popular_queries_count ON public.popular_queries(count DESC);
CREATE INDEX IF NOT EXISTS idx_popular_queries_category ON public.popular_queries(category);

-- ============================================
-- Row Level Security (RLS) Policies
-- ============================================

-- Enable RLS on admin tables
ALTER TABLE public.admin_users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.query_analytics ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.daily_statistics ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.popular_queries ENABLE ROW LEVEL SECURITY;

-- Admin Users Policies - Only service role can manage
CREATE POLICY "Service role can manage admin_users"
    ON public.admin_users
    FOR ALL
    USING (true)
    WITH CHECK (true);

-- Query Analytics Policies - Admins can view all, users can view their own
CREATE POLICY "Admins can view all query analytics"
    ON public.query_analytics
    FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM public.admin_users
            WHERE admin_users.user_id = auth.uid()
        )
    );

CREATE POLICY "Users can view their own query analytics"
    ON public.query_analytics
    FOR SELECT
    USING (auth.uid() = user_id);

-- Daily Statistics Policies - Admins only
CREATE POLICY "Admins can view daily statistics"
    ON public.daily_statistics
    FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM public.admin_users
            WHERE admin_users.user_id = auth.uid()
        )
    );

-- Popular Queries Policies - Admins only
CREATE POLICY "Admins can view popular queries"
    ON public.popular_queries
    FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM public.admin_users
            WHERE admin_users.user_id = auth.uid()
        )
    );

-- ============================================
-- Grant Permissions
-- ============================================
GRANT ALL ON public.admin_users TO service_role;
GRANT ALL ON public.query_analytics TO service_role;
GRANT ALL ON public.daily_statistics TO service_role;
GRANT ALL ON public.popular_queries TO service_role;

GRANT SELECT ON public.query_analytics TO authenticated;
GRANT SELECT ON public.daily_statistics TO authenticated;
GRANT SELECT ON public.popular_queries TO authenticated;

-- ============================================
-- Helper Functions for Analytics
-- ============================================

-- Function to get hourly query distribution for a date range
CREATE OR REPLACE FUNCTION get_hourly_query_distribution(start_date TIMESTAMPTZ, end_date TIMESTAMPTZ)
RETURNS TABLE(hour INTEGER, query_count BIGINT) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        EXTRACT(HOUR FROM created_at)::INTEGER as hour,
        COUNT(*)::BIGINT as query_count
    FROM public.query_analytics
    WHERE created_at >= start_date AND created_at <= end_date
    GROUP BY EXTRACT(HOUR FROM created_at)
    ORDER BY hour;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to get daily query counts for a date range
CREATE OR REPLACE FUNCTION get_daily_query_counts(start_date DATE, end_date DATE)
RETURNS TABLE(date DATE, query_count BIGINT, user_count BIGINT) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        created_at::DATE as date,
        COUNT(*)::BIGINT as query_count,
        COUNT(DISTINCT user_id)::BIGINT as user_count
    FROM public.query_analytics
    WHERE created_at::DATE >= start_date AND created_at::DATE <= end_date
    GROUP BY created_at::DATE
    ORDER BY date;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to update daily statistics
CREATE OR REPLACE FUNCTION update_daily_statistics()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.daily_statistics (date, total_queries, avg_response_time_ms)
    VALUES (
        NEW.created_at::DATE,
        1,
        NEW.response_time_ms
    )
    ON CONFLICT (date) DO UPDATE
    SET 
        total_queries = daily_statistics.total_queries + 1,
        avg_response_time_ms = (
            (daily_statistics.avg_response_time_ms * daily_statistics.total_queries + COALESCE(NEW.response_time_ms, 0)) 
            / (daily_statistics.total_queries + 1)
        ),
        updated_at = NOW();
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to auto-update daily statistics
DROP TRIGGER IF EXISTS update_daily_stats_trigger ON public.query_analytics;
CREATE TRIGGER update_daily_stats_trigger
    AFTER INSERT ON public.query_analytics
    FOR EACH ROW
    EXECUTE FUNCTION update_daily_statistics();

-- ============================================
-- Insert initial admin user (Update with your admin user ID)
-- ============================================
-- To make a user an admin, run:
-- INSERT INTO public.admin_users (user_id, role) VALUES ('YOUR_USER_UUID', 'super_admin');

-- ============================================
-- Verification Queries
-- ============================================
-- SELECT * FROM public.admin_users;
-- SELECT * FROM public.query_analytics LIMIT 10;
-- SELECT * FROM public.daily_statistics ORDER BY date DESC LIMIT 7;
-- SELECT * FROM public.popular_queries ORDER BY count DESC LIMIT 10;
