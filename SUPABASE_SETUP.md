# Supabase Setup Instructions for ADAL UI

Follow these steps to set up your Supabase database and authentication.

## Step 1: Enable Email Authentication

1. Go to [Supabase Dashboard](https://app.supabase.com)
2. Log in and select your project
3. Navigate to **Authentication** → **Providers** (left sidebar)
4. Find **Email** provider in the list
5. Toggle it **ON** (enable it)
6. Configure email settings:
   - **Disable** "Confirm email" for development (or keep enabled for production)
   - Click **Save**

## Step 2: Create Database Tables

1. In Supabase Dashboard, click **SQL Editor** in the left sidebar
2. Click **New query** button
3. Copy the entire content from `database_schema.sql` file
4. Paste it into the SQL Editor
5. Click **Run** button (or press Ctrl+Enter)
6. Wait for success message: "Success. No rows returned"

### What this creates:
- ✅ `chat_sessions` table - stores user chat sessions
- ✅ `chat_messages` table - stores individual messages
- ✅ Row Level Security (RLS) policies - ensures users can only access their own data
- ✅ Indexes - for faster queries
- ✅ Triggers - auto-updates timestamps

## Step 3: Verify Tables Were Created

Run this query in SQL Editor to verify:

```sql
SELECT table_name 
FROM information_schema.tables 
WHERE table_schema = 'public' 
AND table_name IN ('chat_sessions', 'chat_messages');
```

You should see both tables listed.

## Step 4: (Optional) Enable Google OAuth

If you want to use Google sign-in:

1. Go to **Authentication** → **Providers**
2. Find **Google** provider
3. Toggle it **ON**
4. You'll need:
   - **Google Client ID**
   - **Google Client Secret**
   
   Get these from [Google Cloud Console](https://console.cloud.google.com/):
   - Create a new project or select existing
   - Enable Google+ API
   - Create OAuth 2.0 credentials
   - Add authorized redirect URIs:
     - `https://YOUR-PROJECT-REF.supabase.co/auth/v1/callback`
     - `http://localhost:5002/auth/callback` (for development)

5. Paste the credentials into Supabase
6. Click **Save**

## Step 5: Update Your .env File

Make sure your `.env` file has the correct Supabase credentials:

```bash
SUPABASE_URL="https://YOUR-PROJECT-REF.supabase.co"
SUPABASE_KEY="your-anon-key"
SUPABASE_SERVICE_KEY="your-service-role-key"
```

To find these:
1. Go to **Settings** → **API**
2. Copy **Project URL** → `SUPABASE_URL`
3. Copy **anon/public** key → `SUPABASE_KEY`
4. Copy **service_role** key → `SUPABASE_SERVICE_KEY` (click "Reveal" to see it)

## Step 6: Test the Application

1. Stop your Flask server (Ctrl+C)
2. Restart it:
   ```bash
   python run.py
   ```
3. Open browser to `http://localhost:5002`
4. Try to sign up with a CSPC email:
   - Email: `yourname@cspc.edu.ph` or `yourname@my.cspc.edu.ph`
   - Password: At least 8 characters
5. After signup, try to sign in
6. Test the chat functionality

## Troubleshooting

### "Email signups are disabled"
- Go to Authentication → Providers → Enable Email provider

### "Could not find the table 'chat_sessions'"
- Run the SQL script from Step 2

### "Invalid login credentials"
- Make sure you signed up first
- Check that email confirmation is disabled (or check your email)
- Verify the password is correct

### "Only CSPC email addresses are allowed"
- Use an email ending with `@cspc.edu.ph` or `@my.cspc.edu.ph`

### RLS Policy Errors
- Make sure you're using the `SUPABASE_SERVICE_KEY` in your `.env` file
- The service key bypasses RLS for backend operations

## Security Notes

⚠️ **IMPORTANT:**
- Never commit `.env` file to git
- Add `.env` to your `.gitignore`
- Keep `SUPABASE_SERVICE_KEY` secret (server-side only)
- The `service_role` key has full database access - handle with care

## Next Steps

Once everything is working:
1. ✅ Add more users for testing
2. ✅ Configure email templates in Supabase
3. ✅ Set up custom domain (production)
4. ✅ Enable rate limiting
5. ✅ Configure proper CORS settings
