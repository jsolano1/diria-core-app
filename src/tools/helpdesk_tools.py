from src.services import ticket_manager
from src.utils.logging_utils import log_structured

def crear_tiquete_tool(descripcion: str, prioridad: str, equipo: str, solicitante_email: str = "unknown") -> str:
    """Crea un nuevo tiquete de soporte. Prioridad: 'alta', 'media', 'baja'."""
    return ticket_manager.crear_tiquete(descripcion, prioridad, equipo, solicitante_email, "system")

def cerrar_tiquete_tool(ticket_id: str, resolucion: str, solicitante_email: str = "unknown") -> str:
    """Cierra un tiquete existente. Requiere ID del tiquete y una resolución clara."""
    return ticket_manager.cerrar_tiquete(ticket_id, resolucion, solicitante_email)

def reasignar_tiquete_tool(ticket_id: str, nuevo_responsable_email: str, solicitante_email: str = "unknown") -> str:
    """Reasigna un tiquete a un nuevo responsable (email)."""
    return ticket_manager.reasignar_tiquete(ticket_id, nuevo_responsable_email, solicitante_email)

def consultar_estado_tool(ticket_id: str) -> str:
    """Consulta el estado actual de un tiquete por su ID (ej. dir-2025-XXXX)."""
    return ticket_manager.consultar_estado_tiquete(ticket_id)

def snow_connector_tool(operation: str, payload: dict, solicitante_email: str = "unknown") -> str:
    """
    Realiza operaciones CRUD en la tabla de Incidentes de ServiceNow.
    Args:
        operation: 'CREATE', 'READ', 'UPDATE', 'DELETE'
        payload: Diccionario con los datos del incidente (ej. {'short_description': '...', 'urgency': '1'})
    """
    # En un entorno real, esto usaría el Application Integration Connector.
    # Aquí simulamos la respuesta.
    import json
    log_structured("SnowConnectorCall", operation=operation, user=solicitante_email, payload=payload)
    
    if operation == "CREATE":
        return json.dumps({"result": "Incidente creado exitosamente", "sys_id": "mock_sys_id_123", "number": "INC0012345"})
    elif operation == "READ":
        return json.dumps({"result": "Incidente encontrado", "number": "INC0012345", "state": "New", "short_description": "Mock Incident"})
    elif operation == "UPDATE":
        return json.dumps({"result": "Incidente actualizado", "number": "INC0012345"})
    else:
        return json.dumps({"result": "Operación simulada completada"})

def consultar_tiquetes_nlp_tool(query: str, solicitante_email: str = "unknown") -> str:
    """
    Consulta tiquetes usando lenguaje natural (ej. 'mis tiquetes abiertos', 'tiquetes de mi equipo').
    """
    return ticket_manager.consultar_tiquetes_nlp(query, solicitante_email)

tools_list = [crear_tiquete_tool, cerrar_tiquete_tool, reasignar_tiquete_tool, consultar_estado_tool, snow_connector_tool, consultar_tiquetes_nlp_tool]