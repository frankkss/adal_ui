-- ============================================
-- ADAL UI Database Schema
-- ============================================
-- This script creates the necessary tables for the ADAL chatbot application
-- Run this in your Supabase SQL Editor

-- ============================================
-- Chat Sessions Table
-- ============================================
CREATE TABLE IF NOT EXISTS public.chat_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Add index for faster user queries
CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_id ON public.chat_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_updated_at ON public.chat_sessions(updated_at DESC);

-- ============================================
-- Chat Messages Table
-- ============================================
CREATE TABLE IF NOT EXISTS public.chat_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chat_session_id UUID NOT NULL REFERENCES public.chat_sessions(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'bot')),
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Add index for faster chat queries
CREATE INDEX IF NOT EXISTS idx_chat_messages_session_id ON public.chat_messages(chat_session_id);
CREATE INDEX IF NOT EXISTS idx_chat_messages_created_at ON public.chat_messages(created_at);

-- ============================================
-- Row Level Security (RLS) Policies
-- ============================================

-- Enable RLS on tables
ALTER TABLE public.chat_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.chat_messages ENABLE ROW LEVEL SECURITY;

-- Chat Sessions Policies
-- Users can view their own chat sessions
CREATE POLICY "Users can view their own chat sessions"
    ON public.chat_sessions
    FOR SELECT
    USING (auth.uid() = user_id);

-- Users can create their own chat sessions
CREATE POLICY "Users can create their own chat sessions"
    ON public.chat_sessions
    FOR INSERT
    WITH CHECK (auth.uid() = user_id);

-- Users can update their own chat sessions
CREATE POLICY "Users can update their own chat sessions"
    ON public.chat_sessions
    FOR UPDATE
    USING (auth.uid() = user_id);

-- Users can delete their own chat sessions
CREATE POLICY "Users can delete their own chat sessions"
    ON public.chat_sessions
    FOR DELETE
    USING (auth.uid() = user_id);

-- Chat Messages Policies
-- Users can view messages from their own chat sessions
CREATE POLICY "Users can view their own chat messages"
    ON public.chat_messages
    FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM public.chat_sessions
            WHERE chat_sessions.id = chat_messages.chat_session_id
            AND chat_sessions.user_id = auth.uid()
        )
    );

-- Users can create messages in their own chat sessions
CREATE POLICY "Users can create messages in their own chats"
    ON public.chat_messages
    FOR INSERT
    WITH CHECK (
        EXISTS (
            SELECT 1 FROM public.chat_sessions
            WHERE chat_sessions.id = chat_messages.chat_session_id
            AND chat_sessions.user_id = auth.uid()
        )
    );

-- Users can delete messages from their own chat sessions
CREATE POLICY "Users can delete their own chat messages"
    ON public.chat_messages
    FOR DELETE
    USING (
        EXISTS (
            SELECT 1 FROM public.chat_sessions
            WHERE chat_sessions.id = chat_messages.chat_session_id
            AND chat_sessions.user_id = auth.uid()
        )
    );

-- ============================================
-- Functions
-- ============================================

-- Function to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to auto-update updated_at on chat_sessions
DROP TRIGGER IF EXISTS update_chat_sessions_updated_at ON public.chat_sessions;
CREATE TRIGGER update_chat_sessions_updated_at
    BEFORE UPDATE ON public.chat_sessions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- Service Role Bypass (for backend operations)
-- ============================================
-- The service_role key can bypass RLS, which is used in your Flask backend
-- This is already handled by Supabase when using the service_role key

-- ============================================
-- Grant Permissions
-- ============================================
-- Grant access to authenticated users
GRANT ALL ON public.chat_sessions TO authenticated;
GRANT ALL ON public.chat_messages TO authenticated;

-- Grant access to service role (for backend)
GRANT ALL ON public.chat_sessions TO service_role;
GRANT ALL ON public.chat_messages TO service_role;

-- ============================================
-- Verification Queries
-- ============================================
-- Run these to verify the tables were created successfully:
-- SELECT * FROM public.chat_sessions LIMIT 1;
-- SELECT * FROM public.chat_messages LIMIT 1;
