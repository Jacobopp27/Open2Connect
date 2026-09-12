"""Puente best-effort hacia Ambiguous AI para el agente de evento "Mesa 4".

Sin AMBIGUOUS_AGENT_KEY el módulo queda en modo "local": solo hace logging,
no llama a la red y nunca falla. Con la llave presente, cada función pública
dispara una llamada HTTP en un hilo aparte y responde de inmediato — estas
escrituras son informativas (CRM, hoja de conexiones, canal de staff, tareas,
informes) y jamás deben romper el flujo de registro/matching del evento.

Los formatos de payload/respuesta abajo fueron confirmados probando la API
real de Ambiguous. Lo único no confirmado (marcado "# verificar") es la
forma exacta del PATCH para actualizar un contacto CRM existente.
"""
import json
import logging
import os
import threading
import urllib.error
import urllib.request
from datetime import datetime, timezone

BASE_URL = 'https://app.ambiguous.ai/api/'
AGENT_KEY = os.getenv('AMBIGUOUS_AGENT_KEY')
SHEET_ID = os.getenv('AMBIGUOUS_SHEET_ID')
CHANNEL_ID = os.getenv('AMBIGUOUS_CHANNEL_ID')
ORGANIZER_USER_ID = os.getenv('AMBIGUOUS_ORGANIZER_USER_ID')


def _request(method, path, payload=None, timeout=3.0):
    """Llama a la API de Ambiguous con la llave del agente. Nunca lanza excepción."""
    url = BASE_URL + path.lstrip('/')
    data = json.dumps(payload).encode('utf-8') if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header('Authorization', f'Bearer {AGENT_KEY}')
    req.add_header('Content-Type', 'application/json')
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            return resp.status, (json.loads(body) if body else None)
    except urllib.error.HTTPError as exc:
        logging.warning('[ambiguous] %s %s -> HTTP %s', method, path, exc.code)
        try:
            return exc.code, json.loads(exc.read())
        except (ValueError, json.JSONDecodeError):
            return exc.code, None
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        logging.warning('[ambiguous] %s %s -> %s', method, path, type(exc).__name__)
        return 0, None


def _background(fn, *args):
    threading.Thread(target=fn, args=args, daemon=True).start()


def _buscar_contacto(email, name):
    # No hay parámetro de búsqueda confirmado: se lista y filtra en Python.
    status, data = _request('GET', 'crm/contacts?limit=200')
    if status == 200 and isinstance(data, dict):
        for item in data.get('data') or []:
            if email and item.get('email') == email:
                return item.get('id')
            if not email and name and item.get('name') == name:
                return item.get('id')
    return None


def _custom_properties(profile):
    props = {}
    if profile.get('sector'):
        props['company'] = profile['sector']
    for campo in ('interests', 'purpose', 'problem', 'help', 'skills', 'availability'):
        if profile.get(campo):
            props[campo] = profile[campo]
    if profile.get('sena'):
        props['sena'] = profile['sena']
    if profile.get('checked_in_at'):
        props['checked_in_at'] = profile['checked_in_at']
    return props


def _registrar_asistente(profile, event):
    payload = {
        'type': 'person',
        'name': profile.get('name', ''),
        'email': profile.get('email', ''),
        'title': profile.get('role', ''),
        'custom_properties': _custom_properties(profile),
    }
    contact_id = _buscar_contacto(payload['email'], payload['name'])
    if contact_id:
        _request('PATCH', f'crm/contacts/{contact_id}', payload)  # verificar: formato exacto del PATCH
    else:
        _request('POST', 'crm/contacts', payload)


def registrar_asistente(profile: dict, event: str):
    """Crea/actualiza el contacto CRM de un asistente. Best-effort, corre en segundo plano."""
    if not AGENT_KEY:
        logging.info('[ambiguous:local] asistente registrado: %s (%s)', profile.get('name', ''), event)
        return None
    _background(_registrar_asistente, profile, event)
    return None


def _filas_actuales(sheet_id):
    status, data = _request('GET', f'sheets/{sheet_id}')
    if status == 200 and isinstance(data, dict):
        # La API responde {"id", "title", "data": {"sheets": [{"rows": [...]}]}}.
        sheets = (data.get('data') or {}).get('sheets') or []
        if sheets and isinstance(sheets[0], dict):
            return sheets[0].get('rows') or []
    return []


_SHEET_LOCK = threading.Lock()


def _registrar_conexion(a, b, razon, event):
    fecha = datetime.now(timezone.utc).isoformat()
    valores = [fecha, event, a.get('name', ''), b.get('name', ''), razon, 'sugerida']
    columnas = ('A', 'B', 'C', 'D', 'E', 'F')
    # Candado: dos check-ins a la vez no deben calcular la misma fila.
    with _SHEET_LOCK:
        fila = max(len(_filas_actuales(SHEET_ID)), 1)  # nunca pisar los encabezados (fila 0)
        updates = [{'row': fila, 'column': col, 'value': val} for col, val in zip(columnas, valores)]
        _request('PATCH', f'sheets/{SHEET_ID}/cells', {'updates': updates})


def registrar_conexion(a: dict, b: dict, razon: str, event: str):
    """Agrega una fila a la hoja de conexiones del evento en Ambiguous."""
    if not AGENT_KEY or not SHEET_ID:
        logging.info('[ambiguous:local] conexion sugerida: %s <-> %s (%s)', a.get('name', ''), b.get('name', ''), razon)
        return None
    _background(_registrar_conexion, a, b, razon, event)
    return None


def _avisar_staff(mensaje):
    _request('POST', f'channels/{CHANNEL_ID}/messages', {'content': mensaje})


def avisar_staff(mensaje: str):
    """Envía un mensaje al canal de staff configurado."""
    if not AGENT_KEY or not CHANNEL_ID:
        logging.info('[ambiguous:local] aviso al staff: %s', mensaje)
        return None
    _background(_avisar_staff, mensaje)
    return None


def _crear_tarea(titulo, descripcion, priority):
    payload = {'title': titulo, 'description': descripcion, 'priority': priority}
    if ORGANIZER_USER_ID:
        payload['assignee_id'] = ORGANIZER_USER_ID
    _request('POST', 'tasks', payload)


def crear_tarea(titulo: str, descripcion: str = '', priority: str = 'medium'):
    """Crea una tarea para el staff del evento; se asigna al organizador si está configurado."""
    if not AGENT_KEY:
        logging.info('[ambiguous:local] tarea: %s (%s)', titulo, priority)
        return None
    _background(_crear_tarea, titulo, descripcion, priority)
    return None


def _escribir_informe(titulo, markdown):
    _request('POST', 'documents', {'type': 'doc', 'title': titulo, 'content': markdown})


def escribir_informe(titulo: str, markdown: str):
    """Crea un documento en Ambiguous con el resumen del evento; el servidor convierte el markdown."""
    if not AGENT_KEY:
        logging.info('[ambiguous:local] informe: %s', titulo)
        return None
    _background(_escribir_informe, titulo, markdown)
    return None


def estado():
    """Estado del módulo para exponer en /api/config, por ejemplo."""
    return {'modo': 'ambiguous' if AGENT_KEY else 'local', 'sheet': bool(SHEET_ID), 'channel': bool(CHANNEL_ID)}
