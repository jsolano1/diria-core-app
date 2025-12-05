import requests
from src.utils.logging_utils import log_structured

def get_location_from_ip(ip_address: str) -> str:
    """
    Retrieves the location (City, Country) for a given IP address using ip-api.com.
    Returns "Unknown" if the lookup fails.
    """
    if not ip_address:
        return "Unknown"
        
    # Localhost check
    if ip_address in ["127.0.0.1", "::1", "localhost"]:
        return "Localhost"

    try:
        response = requests.get(f"http://ip-api.com/json/{ip_address}", timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "success":
                city = data.get("city", "")
                country = data.get("country", "")
                return f"{city}, {country}".strip(", ")
            else:
                log_structured("GeoLookupFailed", ip=ip_address, reason=data.get("message"))
    except Exception as e:
        log_structured("GeoLookupError", ip=ip_address, error=str(e))
    
    return "Unknown"
