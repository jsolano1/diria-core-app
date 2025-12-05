from sqlalchemy import text
from src.utils.database_client import get_db_connection
from src.utils.logging_utils import log_structured
from src.utils.geolocation import get_location_from_ip

def init_roles_table():
    """Initializes the roles_usuarios table if it doesn't exist."""
    engine = get_db_connection()
    try:
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS roles_usuarios (
                    user_email VARCHAR(255) PRIMARY KEY,
                    nombre VARCHAR(100),
                    apellido VARCHAR(100),
                    company VARCHAR(255),
                    ubicacion VARCHAR(255),
                    ip_registro VARCHAR(50),
                    chat_user_id VARCHAR(255),
                    can_query_dwh BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """))
            conn.commit()
            log_structured("RolesTableInit", status="Success")
    except Exception as e:
        log_structured("RolesTableInitError", error=str(e))

# Initialize table on module load
init_roles_table()

def register_user(email: str, first_name: str, last_name: str, company: str, ip_address: str):
    """
    Registers a new user or updates an existing one with location data.
    """
    location = get_location_from_ip(ip_address)
    engine = get_db_connection()
    
    try:
        with engine.connect() as conn:
            stmt = text("""
                INSERT INTO roles_usuarios (user_email, nombre, apellido, company, ubicacion, ip_registro, created_at)
                VALUES (:email, :first_name, :last_name, :company, :location, :ip, NOW())
                ON CONFLICT (user_email) DO UPDATE SET
                    nombre = EXCLUDED.nombre,
                    apellido = EXCLUDED.apellido,
                    company = EXCLUDED.company,
                    ubicacion = EXCLUDED.ubicacion,
                    ip_registro = EXCLUDED.ip_registro;
            """)
            conn.execute(stmt, {
                "email": email,
                "first_name": first_name,
                "last_name": last_name,
                "company": company,
                "location": location,
                "ip": ip_address
            })
            conn.commit()
            log_structured("UserRegistered", email=email, location=location)
            return {"status": "success", "location": location}
    except Exception as e:
        log_structured("UserRegistrationError", email=email, error=str(e))
        raise e
