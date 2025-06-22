import os
from supabase import create_client, Client

supabase: Client = None

def init_supabase():
    global supabase
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    
    if not url or not key:
        print("Warning: Supabase credentials not found in environment variables")
        print("Please set SUPABASE_URL and SUPABASE_KEY in your .env file")
        return None
    
    supabase = create_client(url, key)
    return supabase

def get_supabase_client():
    global supabase
    if supabase is None:
        supabase = init_supabase()
    return supabase

