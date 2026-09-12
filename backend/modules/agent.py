"""Participant-scoped interview tools. All identity comes from the HTTP session."""
import os
from backend.db import connect
from backend.modules import kiosk, encuentros
from backend.modules.auth import Problem
from backend.modules.profiles import check_event


def handle(user, event, action, payload):
    with connect() as db: check_event(db, event)
    uid = user['id']
    if payload.get('id') and str(payload['id']) != uid:
        raise Problem('Solo puedes modificar tu propio perfil.', 403)
    if action == 'token':
        from backend.adapters.profile_store import store
        if not store().get(uid,event).get('saved'):
            raise Problem('Completa y confirma tu perfil en la página principal antes de iniciar la entrevista.',409)
        if payload.get('ai_consent') is not True:
            raise Problem('Confirma el uso de OpenAI para la entrevista.', 400)
        return kiosk.crear_token_realtime()
    if action == 'buscar':
        with connect() as db:
            row = db.execute('SELECT u.id,u.profile,p.data FROM users u LEFT JOIN profiles p ON p.user_id=u.id AND p.event_id=? WHERE u.id=?', (event,uid)).fetchone()
        general, data = kiosk._perfil_de(row)
        return {'resultados':[{'id':uid,'name':general.get('name',''),'role':general.get('role',''),
            'sector':general.get('sector',''),'busca':data.get('help',''),'ofrece':data.get('skills',''),
            'registrado':row['data'] is not None,'confianza':'alta'}]}
    if action == 'confirmar':
        if payload.get('confirmed') is not True: raise Problem('Revisa y confirma los cambios antes de guardar.')
        return kiosk.confirmar_perfil(uid,payload.get('cambios',{}),event)
    if action == 'checkin':
        if payload.get('confirmed') is not True: raise Problem('Confirma la seña antes de registrar tu llegada.')
        return kiosk.hacer_checkin(uid,str(payload.get('sena',''))[:200],event)
    if action == 'recomendar':
        result = encuentros.estado(uid,event)
        present = [r for r in result['matches'] if r['checked_in_at']][:2]
        return {'recomendaciones':present,'pagina_personal':kiosk.pagina_personal_url(uid,event),
                'sugerencia':'Aún no hay coincidencias presentes. Consulta tu página personal más tarde.'}
    if action == 'qr': return kiosk.mostrar_qr_registro()
    if action == 'apariencia':
        if payload.get('photo_consent') is not True: raise Problem('Confirma el envío de la foto para describir la seña.')
        return kiosk.describir_apariencia(str(payload.get('imagen','')))
    raise Problem('Herramienta no disponible.',404)


def status():
    return {'route':'/agent','configured':bool(os.getenv('OPENAI_API_KEY')),
            'model':os.getenv('REALTIME_MODEL','gpt-realtime'),'requires_login':True}
