#!/usr/bin/env python3
"""Setup guiado para conectar el agente "Mesa 4" con el workspace de Ambiguous AI.

Uso:
    AMBIGUOUS_ADMIN_KEY=... python3 scripts/ambiguous_setup.py

Usa AMBIGUOUS_ADMIN_KEY (llave de administrador, distinta de la llave del
agente) para provisionar a Mesa 4 y crear los recursos que necesita. Los
formatos de payload/respuesta fueron confirmados contra la API real; cada
paso igual explica qué hacer manualmente si algo falla. La api key del
agente nunca se imprime: se guarda directamente en .env.local.
"""
import json
import os
import sys
import urllib.error
import urllib.request

BASE_URL = 'https://app.ambiguous.ai/api/'
ADMIN_KEY = os.getenv('AMBIGUOUS_ADMIN_KEY')
EVENTO = os.getenv('EVENTO_NOMBRE', 'evento')


def enmascarar(key):
    """Oculta todo menos los últimos 4 caracteres de una llave."""
    if not key or len(key) <= 4:
        return '****'
    return '*' * (len(key) - 4) + key[-4:]


def _request(method, path, payload=None, timeout=5.0):
    """Llamada HTTP simple con la llave admin. Devuelve (status, dict|None)."""
    url = BASE_URL + path.lstrip('/')
    data = json.dumps(payload).encode('utf-8') if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header('Authorization', f'Bearer {ADMIN_KEY}')
    req.add_header('Content-Type', 'application/json')
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            return resp.status, (json.loads(body) if body else None)
    except urllib.error.HTTPError as exc:
        try:
            return exc.code, json.loads(exc.read())
        except (ValueError, json.JSONDecodeError):
            return exc.code, None
    except (urllib.error.URLError, TimeoutError, ValueError):
        return 0, None


def ocultar_llaves(data):
    """Devuelve una copia con cualquier campo tipo llave/token/secreto oculto (nunca se imprime el valor)."""
    if isinstance(data, dict):
        return {k: ('<omitida>' if k in ('api_key', 'apiKey', 'key', 'token', 'agent_key', 'secret') and isinstance(v, str) else ocultar_llaves(v)) for k, v in data.items()}
    if isinstance(data, list):
        return [ocultar_llaves(x) for x in data]
    return data


def recortar(data, n=300):
    texto = json.dumps(ocultar_llaves(data), ensure_ascii=False) if data is not None else 'null'
    return texto if len(texto) <= n else texto[:n] + '...'


def paso(titulo):
    print(f'\n== {titulo} ==')


def main():
    if not ADMIN_KEY:
        print('Falta AMBIGUOUS_ADMIN_KEY en el entorno. / Missing AMBIGUOUS_ADMIN_KEY env var.')
        sys.exit(1)
    print(f'Usando AMBIGUOUS_ADMIN_KEY={enmascarar(ADMIN_KEY)}')

    # 1. Validar la llave admin.
    paso('1. Validar llave admin')
    try:
        status, data = _request('GET', 'crm/contacts?limit=1')
        print(f'GET /api/crm/contacts?limit=1 -> {status} {recortar(data)}')
        if status != 200:
            print('No se pudo validar la llave. Revisa que AMBIGUOUS_ADMIN_KEY sea correcta y tenga permisos de CRM.')
    except Exception as exc:
        print(f'Error validando la llave: {exc}. Revisa la URL base y la llave.')

    # 2. Provisionar el agente "Mesa 4".
    paso('2. Provisionar agente "Mesa 4"')
    agente_guardado = False
    try:
        status, data = _request('POST', 'admin/users/provision-agent', {
            'display_name': 'Mesa 4',
            'role': 'member',
        })
        print(f'POST /api/admin/users/provision-agent -> {status} {recortar(data)}')
        if status in (200, 201) and isinstance(data, dict):
            user = data.get('user') or {}
            api_key = data.get('api_key')
            print(f"Usuario agente id: {user.get('id')}, username: {user.get('username')}, tipo: {user.get('type')}")
            if api_key:
                env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env.local')
                with open(env_path, 'a') as f:
                    f.write(f'\nAMBIGUOUS_AGENT_KEY={api_key}\n')
                agente_guardado = True
                print(f'La api key del agente quedó guardada en {env_path} como AMBIGUOUS_AGENT_KEY (no se imprime aquí).')
            else:
                print('No se encontró "api_key" en la respuesta. Revisa el JSON (arriba, redactado) o crea/copia la llave manualmente en app.ambiguous.ai/agents.')
        else:
            print('El endpoint puede tener otro nombre: revisa app.ambiguous.ai/agents/api y crea el agente "Mesa 4" ahí manualmente.')
    except Exception as exc:
        print(f'Error provisionando el agente: {exc}. Revisa app.ambiguous.ai/agents/api.')

    # 3. Crear la hoja de conexiones.
    paso('3. Crear hoja "Conexiones"')
    sheet_id = None
    try:
        status, data = _request('POST', 'documents', {
            'type': 'sheet',
            'title': f'Conexiones — {EVENTO}',
        })
        print(f'POST /api/documents (sheet) -> {status} {recortar(data)}')
        if status in (200, 201) and isinstance(data, dict):
            sheet_id = data.get('id')
            print(f'Hoja creada, id: {sheet_id} -> cópialo a AMBIGUOUS_SHEET_ID')
            if sheet_id:
                encabezados = ['fecha', 'evento', 'persona A', 'persona B', 'razon', 'estado']
                columnas = ('A', 'B', 'C', 'D', 'E', 'F')
                updates = [{'row': 0, 'column': col, 'value': val} for col, val in zip(columnas, encabezados)]
                status2, data2 = _request('PATCH', f'sheets/{sheet_id}/cells', {'updates': updates})
                print(f'PATCH /api/sheets/{sheet_id}/cells (encabezados) -> {status2} {recortar(data2)}')
        else:
            print('No se pudo crear la hoja automáticamente. Créala a mano en app.ambiguous.ai y copia su id a AMBIGUOUS_SHEET_ID.')
    except Exception as exc:
        print(f'Error creando la hoja: {exc}. Créala a mano y copia el id.')

    # 4. Crear o localizar el canal de staff.
    paso('4. Crear canal "staff-mesa4"')
    channel_id = None
    try:
        status, data = _request('POST', 'channels', {'name': 'staff-mesa4', 'type': 'public'})
        print(f'POST /api/channels -> {status} {recortar(data)}')
        if status in (200, 201) and isinstance(data, dict):
            channel_id = data.get('id')
            print(f'Canal creado, id: {channel_id} -> cópialo a AMBIGUOUS_CHANNEL_ID')
        else:
            print('No se pudo crear el canal automáticamente. Créalo a mano en la app ("staff-mesa4") y copia su id a AMBIGUOUS_CHANNEL_ID.')
    except Exception as exc:
        print(f'Error creando el canal: {exc}. Créalo a mano en la app y copia el id.')

    # 5. Resumen para pegar en .env.
    paso('5. Variables para tu .env')
    print('AMBIGUOUS_AGENT_KEY=' + ('ya guardada en .env.local, ver paso 2' if agente_guardado else '<pega aquí la api key del paso 2>'))
    print('AMBIGUOUS_ADMIN_KEY=' + enmascarar(ADMIN_KEY) + '  # ya la tienes en tu entorno; no la subas al repo')
    print(f'AMBIGUOUS_SHEET_ID={sheet_id or "<pega aquí el id de la hoja del paso 3>"}')
    print(f'AMBIGUOUS_CHANNEL_ID={channel_id or "<pega aquí el id del canal del paso 4>"}')
    print('AMBIGUOUS_ORGANIZER_USER_ID=<opcional: id del usuario organizador para asignar tareas>')


if __name__ == '__main__':
    main()
