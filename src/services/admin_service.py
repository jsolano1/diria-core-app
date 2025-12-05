from sqlalchemy import text
from src.utils.database_client import get_db_connection
from src.utils.logging_utils import log_structured
import datetime

# --- Global Admin Functions ---

def create_subscription(user_email: str, plan: str, start_date: datetime.date, end_date: datetime.date, company_admin_email: str = None):
    """Creates a new subscription for a user."""
    engine = get_db_connection()
    try:
        with engine.connect() as conn:
            stmt = text("""
                INSERT INTO subscriptions (user_email, plan, contract_start_date, contract_end_date, is_active, company_admin_email, created_at)
                VALUES (:email, :plan, :start, :end, TRUE, :admin, NOW())
                ON CONFLICT (user_email) DO UPDATE SET
                    plan = EXCLUDED.plan,
                    contract_start_date = EXCLUDED.contract_start_date,
                    contract_end_date = EXCLUDED.contract_end_date,
                    is_active = TRUE,
                    company_admin_email = EXCLUDED.company_admin_email;
            """)
            conn.execute(stmt, {
                "email": user_email,
                "plan": plan,
                "start": start_date,
                "end": end_date,
                "admin": company_admin_email
            })
            conn.commit()
            return True
    except Exception as e:
        log_structured("CreateSubscriptionError", error=str(e), user=user_email)
        return False

def get_global_stats():
    """Returns global stats for App Admin."""
    engine = get_db_connection()
    try:
        with engine.connect() as conn:
            total_users = conn.execute(text("SELECT COUNT(*) FROM subscriptions")).scalar()
            active_users = conn.execute(text("SELECT COUNT(*) FROM subscriptions WHERE is_active = TRUE")).scalar()
            return {"total_users": total_users, "active_users": active_users}
    except Exception as e:
        log_structured("GlobalStatsError", error=str(e))
        return {}

# --- Company Admin Functions ---

def get_company_users(admin_email: str):
    """Returns all users managed by a specific company admin."""
    engine = get_db_connection()
    try:
        with engine.connect() as conn:
            stmt = text("SELECT * FROM subscriptions WHERE lower(company_admin_email) = lower(:admin)")
            result = conn.execute(stmt, {"admin": admin_email}).mappings().fetchall()
            return [dict(row) for row in result]
    except Exception as e:
        log_structured("GetCompanyUsersError", error=str(e), admin=admin_email)
        return []

def update_user_limit(admin_email: str, target_user_email: str, is_active: bool):
    """Allows a Company Admin to activate/deactivate their users."""
    engine = get_db_connection()
    try:
        with engine.connect() as conn:
            # Verify ownership first
            check_stmt = text("SELECT 1 FROM subscriptions WHERE lower(user_email) = lower(:user) AND lower(company_admin_email) = lower(:admin)")
            exists = conn.execute(check_stmt, {"user": target_user_email, "admin": admin_email}).scalar()
            
            if not exists:
                return False # Not authorized or user not found
            
            update_stmt = text("UPDATE subscriptions SET is_active = :active WHERE lower(user_email) = lower(:user)")
            conn.execute(update_stmt, {"active": is_active, "user": target_user_email})
            conn.commit()
            return True
    except Exception as e:
        log_structured("UpdateUserLimitError", error=str(e), admin=admin_email, target=target_user_email)
        return False
