import requests
import json

# Configuración de credenciales y URL base
API_KEY = "sk_TU_LLAVE_AQUI"
BASE_URL = "https://aitinkerers.org/api/agents/v1"

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

def busqueda_cruzada_miembros_y_eventos(keyword_perfil: str, ciudad_filtro: str = None):
    print(f"=== 1. Buscando miembros con perfil/interés: '{keyword_perfil}' ===")
    
    # 1. Búsqueda estructurada de miembros por perfil o palabras clave
    res_search = requests.get(
        f"{BASE_URL}/clients/profile_search",
        headers=headers,
        params={"query": keyword_perfil, "limit": 3}
    )
    
    if res_search.status_code != 200:
        print(f"Error en búsqueda: {res_search.status_code} - {res_search.text}")
        return

    miembros = res_search.json().get("data", {}).get("clients", [])
    print(f"Se encontraron {len(miembros)} miembros coincidentes.\n")

    # 2. Consultar próximos eventos para cruzar la información
    print("=== 2. Obteniendo próximos eventos de AI Tinkerers ===")
    res_events = requests.get(
        f"{BASE_URL}/meetups/upcoming",
        headers=headers,
        params={"limit": 5, "city": ciudad_filtro} if ciudad_filtro else {"limit": 5}
    )
    eventos_futuros = res_events.json().get("data", {}).get("meetups", []) if res_events.status_code == 200 else []
    
    # 3. Enriquecimiento cruzado por cada miembro encontrado
    for m in miembros:
        client_token = m.get("token") or m.get("client_token")
        email = m.get("email")
        nombre = m.get("name", "Miembro")
        
        print(f"--------------------------------------------------")
        print(f"👤 PROCESANDO MIEMBRO: {nombre} ({email or client_token})")
        
        # Obtenemos el dossier detallado (evaluación, biografía y orientación)
        res_dossier = requests.get(
            f"{BASE_URL}/dossier/get",
            headers=headers,
            params={"email": email} if email else {"client_token": client_token}
        )
        dossier = res_dossier.json().get("data", {}) if res_dossier.status_code == 200 else {}
        
        # Obtenemos el historial de charlas impartidas por el miembro
        res_talks = requests.get(
            f"{BASE_URL}/rsvps/talk_history",
            headers=headers,
            params={"client_ref": client_token or email}
        )
        charlas = res_talks.json().get("data", {}).get("talks", []) if res_talks.status_code == 200 else []

        # Mostramos el expediente consolidado
        print(f" - Biografía / Bio: {dossier.get('bio', 'N/A')}")
        print(f" - Calificación / Screening Score: {dossier.get('screening_score', 'N/A')}")
        print(f" - Historial de Charlas ({len(charlas)}):")
        for talk in charlas:
            print(f"    * '{talk.get('title')}' en {talk.get('city', 'Evento')} ({talk.get('approval_status')})")
            
        print("\n - Coincidencia con próximos eventos:")
        for ev in eventos_futuros:
            print(f"    [Evento Disponible] {ev.get('title')} - {ev.get('city')} ({ev.get('starts_at')})")

if __name__ == "__main__":
    # Ejemplo: Buscar expertos en 'agents' y cruzar con eventos futuros
    busqueda_cruzada_miembros_y_eventos(keyword_perfil="agents")
