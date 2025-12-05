import datetime
from sqlalchemy import text
from src.utils.database_client import get_db_connection
from src.utils.logging_utils import log_structured

# Global cache for subscription status: {user_email: {'is_active': bool, 'expires_at': datetime}}
# We cache for 24 hours.
_SUBSCRIPTION_CACHE = {}

def init_subscription_table():
    """Initializes the subscriptions table in Postgres."""
    engine = get_db_connection()
    try:
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS subscriptions (
                    user_email VARCHAR(255) PRIMARY KEY,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    contract_start_date DATE,
                    contract_end_date DATE,
                    is_active BOOLEAN DEFAULT FALSE,
                    last_renewal TIMESTAMP,
                    plan VARCHAR(50),
                    discount_applied BOOLEAN DEFAULT FALSE,
                    discount_amount FLOAT DEFAULT 0.0,
                    promo_code VARCHAR(50),
                    company_admin_email VARCHAR(255)
                );
            """))
            conn.commit()
            log_structured("SubscriptionTableInit", status="Success")
    except Exception as e:
        log_structured("SubscriptionTableInitError", error=str(e))

# Initialize table on module load
init_subscription_table()

def check_subscription_status(user_email: str) -> bool:
    """
    Checks if a user has an active subscription.
    Uses a 24-hour in-memory cache to reduce DB hits.
    """
    if not user_email:
        return False

    now = datetime.datetime.now()
    
    # Check cache
    if user_email in _SUBSCRIPTION_CACHE:
        cache_entry = _SUBSCRIPTION_CACHE[user_email]
        if cache_entry['expires_at'] > now:
            return cache_entry['is_active']

    # Cache miss or expired, check DB
    engine = get_db_connection()
    is_active = False
    
    try:
        with engine.connect() as conn:
            # Check if active AND within contract dates
            query = text("""
                SELECT is_active, contract_end_date 
                FROM subscriptions 
                WHERE lower(user_email) = lower(:email)
            """)
            result = conn.execute(query, {"email": user_email}).fetchone()
            
            if result:
                db_is_active, end_date = result
                # If marked active in DB, also check if contract hasn't expired
                if db_is_active:
                    if end_date and end_date < now.date():
                        is_active = False # Expired
                        # Optional: Update DB to set is_active=False? 
                        # For now, just return False to avoid side effects in a "check" function.
                    else:
                        is_active = True
                else:
                    is_active = False
            else:
                is_active = False # No record found

    except Exception as e:
        log_structured("SubscriptionCheckError", error=str(e), user=user_email)
        # Fail safe: if DB error, assume False or maybe True depending on policy? 
        # Safest is False to prevent unauthorized access, but might block valid users during outage.
        # Let's return False.
        return False

    # Update cache
    _SUBSCRIPTION_CACHE[user_email] = {
        'is_active': is_active,
        'expires_at': now + datetime.timedelta(hours=24)
    }
    
    return is_active

def get_subscription_details(user_email: str) -> dict:
    """Returns full subscription details for a user."""
    engine = get_db_connection()
    try:
        with engine.connect() as conn:
            query = text("SELECT * FROM subscriptions WHERE lower(user_email) = lower(:email)")
            result = conn.execute(query, {"email": user_email}).mappings().fetchone()
            if result:
                return dict(result)
            return {}
    except Exception as e:
        log_structured("GetSubscriptionDetailsError", error=str(e), user=user_email)
        return {}
