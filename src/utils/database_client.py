import sqlalchemy
from sqlalchemy.sql import text
from google.cloud.sql.connector import Connector, IPTypes
from src.config import settings
from src.utils.logging_utils import log_structured
import traceback

db_pool = None

def get_db_connection() -> sqlalchemy.engine.base.Engine:
    """Inicializa y devuelve el pool de conexiones a Cloud SQL."""
    global db_pool
    if db_pool:
        return db_pool

    connector = Connector()

    def getconn():
        conn = connector.connect(
            settings.DB_CONNECTION_NAME,
            "pg8000",
            user=settings.DB_USER,
            password=settings.DB_PASS,
            db=settings.DB_NAME,
            ip_type=IPTypes.PUBLIC  
        )
        
        cur = conn.cursor()
        try:
            cur.execute("SET search_path TO core, helpdesk, claims, public")
            conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"Error configurando search_path: {e}")
            raise e
        finally:
            cur.close()
            
        return conn

    try:
        db_pool = sqlalchemy.create_engine(
            "postgresql+pg8000://",
            creator=getconn,
            pool_size=settings.DB_POOL_SIZE,
            max_overflow=settings.DB_MAX_OVERFLOW,
            pool_timeout=settings.DB_POOL_TIMEOUT,
        )
        log_structured("DBPoolInitialized", pool_size=settings.DB_POOL_SIZE)
        return db_pool
    except Exception as e:
        log_structured("DBPoolInitError", error=str(e), traceback=traceback.format_exc())
        raise

def get_dm_space_name_for_user(user_email: str) -> str | None:
    """
    Consulta la DB de Postgres para obtener el chat_user_id (space_name del DM 1:1).
    Este ID (ej. spaces/AAAA...) es necesario para enviar mensajes privados via API.
    """
    if not user_email: return None
    
    engine = get_db_connection()
    try:
        with engine.connect() as conn:
            query = text("SELECT chat_user_id FROM roles_usuarios WHERE lower(user_email) = lower(:email) LIMIT 1")
            result = conn.execute(query, {"email": user_email.strip()}).scalar()
            
            if result and str(result).startswith("spaces/"):
                return str(result)
            return None
    except Exception as e:
        log_structured("GetDMSpaceError", error=str(e), user=user_email)
        return None

def check_dwh_permission(user_email: str) -> bool:
    """
    Verifica en la tabla roles_usuarios si el usuario tiene permiso 'can_query_dwh'.
    """
    if not user_email: return False
    engine = get_db_connection()
    try:
        with engine.connect() as conn:
            query = text("SELECT can_query_dwh FROM roles_usuarios WHERE lower(user_email) = lower(:email) LIMIT 1")
            result = conn.execute(query, {"email": user_email.strip()}).scalar()
            return bool(result)
    except Exception as e:
        log_structured("CheckDwhPermissionError", error=str(e), user=user_email)
        return False

def get_all_departments():
    """Obtiene lista de departamentos."""
    engine = get_db_connection()
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT department_name FROM departments"))
            return [row[0] for row in result]
    except Exception as e:
        log_structured("DBQueryError", query="get_all_departments", error=str(e))
        return []

def get_all_priorities():
    """Obtiene lista de prioridades."""
    engine = get_db_connection()
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT DISTINCT priority FROM sla_configuracion"))
            return [row[0] for row in result]
    except Exception as e:
        log_structured("DBQueryError", query="get_all_priorities", error=str(e))
        return ["alta", "media", "baja"]