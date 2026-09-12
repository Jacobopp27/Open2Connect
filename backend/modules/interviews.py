"""User/event-scoped interview state. Raw speech is never written to disk.

Sessions live in process memory for 2 hours. Only explicitly confirmed structured
profile fields reach the selected repository; temporary evidence is discarded.
"""
import copy
import hashlib
import secrets
import threading
import time
from backend.modules.auth import Problem
from backend.modules import profiles, conversation
from backend.adapters.interview_ai import FIELDS, OpenAIInterview

TTL=7200
SESSIONS={}
LOCK=threading.RLock()
QUESTIONS={
 'name':('¿Cómo te llamas?','What is your name?'),
 'role':('¿Qué haces o cuál es tu rol?','What do you do, or what is your role?'),
 'experience':('¿Qué experiencia quieres compartir? Puedes decir «omitir».','What experience would you like to share? You can say “skip”.'),
 'sector':('¿En qué sector trabajas? Puedes omitirlo.','What industry do you work in? You can skip this.'),
 'interests':('¿Qué temas te interesan? Puedes omitirlos.','What topics interest you? You can skip this.'),
 'languages':('¿En qué idiomas puedes conversar?','Which languages can you converse in?'),
 'purpose':('¿Qué te gustaría lograr en este evento?','What would you like to achieve at this event?'),
 'needs_status':('¿Necesitas ayuda de alguien en este evento, o no tienes una necesidad ahora?','Do you need help from someone at this event, or have no current need?'),
 'problem':('¿Qué problema quieres resolver?','What problem would you like to solve?'),
 'help':('¿Qué ayuda concreta te sería útil?','What specific help would be useful?'),
 'priority':('¿Es una prioridad alta, media o baja?','Is this a high, medium or low priority?'),
 'outcome':('¿Qué resultado esperas conseguir con esa ayuda?','What outcome do you expect from that help?'),
 'offers_status':('¿Tienes algo que puedas ofrecer ahora, o prefieres no ofrecer por el momento?','Do you have something to offer now, or prefer not to offer anything at the moment?'),
 'skills':('¿Qué habilidades puedes aportar?','What skills can you contribute?'),
 'knowledge':('¿Qué conocimientos puedes compartir? Puedes omitirlo.','What knowledge can you share? You can skip this.'),
 'services':('¿Ofreces algún servicio? Puedes omitirlo.','Do you offer any services? You can skip this.'),
 'resources':('¿Qué recursos puedes aportar? Puedes omitirlo.','What resources can you contribute? You can skip this.'),
 'availability':('¿Estás disponible, tienes tiempo limitado o no estás disponible?','Are you available, have limited time, or unavailable?')}
ORDER=list(QUESTIONS)
OPTIONAL={'experience','sector','interests','knowledge','services','resources'}
NEEDS={'problem','help','priority','outcome'}
OFFERS={'skills','knowledge','services','resources'}
ENUMS={'priority':{'alta':'high','high':'high','media':'medium','medium':'medium','baja':'low','low':'low'},
 'availability':{'disponible':'available','available':'available','tiempo limitado':'limited','limitado':'limited','limited':'limited','limited time':'limited','no disponible':'unavailable','unavailable':'unavailable'},
 'needs_status':{'sí':'present','si':'present','yes':'present','present':'present','no':'none','ninguna':'none','none':'none','no necesito ayuda':'none','no necesito nada':'none'},
 'offers_status':{'sí':'present','si':'present','yes':'present','present':'present','no':'none','ninguna':'none','none':'none','no ofrezco nada':'none','nothing to offer':'none'}}

def missing(s):
    d=s['draft']; answered=set(s['answered'])
    fields=[]
    for k in ORDER:
        if k in NEEDS and d.get('needs_status')=='none': continue
        if k in OFFERS and d.get('offers_status')=='none': continue
        if (not d.get(k) and k not in answered) or (k in ENUMS and d.get(k) not in set(ENUMS[k].values())):
            fields.append(k)
    return fields

def ask(s):
    pending=missing(s)
    s['focus']=pending[0] if pending else 'review'
    s['question']=QUESTIONS[s['focus']][s['locale']=='en'] if pending else ('Tu resumen está listo. Revísalo antes de confirmar.' if s['locale']=='es' else 'Your summary is ready. Review it before confirming.')

def public(s):
    return {k:copy.deepcopy(s[k]) for k in ('id','event','locale','mode','draft','notes','question','focus','revision','status','expires')} | {'missing':missing(s),'saved':s['status']=='confirmed','review_token':s.get('review_token')}

def owned(user, iid):
    s=SESSIONS.get(iid)
    if not s or s['owner']!=user['id'] or s['expires']<time.time() or (user.get('mcp_event') and s['event']!=user['mcp_event']):
        raise Problem('Entrevista no encontrada o vencida. / Interview not found or expired.',404)
    return s

def start(user,event,payload):
    locale=payload.get('locale','es'); mode=payload.get('mode','guided')
    if locale not in ('es','en') or mode not in ('guided','openai','realtime'):
        raise Problem('Idioma o modo inválido. / Invalid locale or mode.')
    if mode in ('openai','realtime'):
        if payload.get('ai_consent') is not True:
            raise Problem('Autoriza enviar tus respuestas de entrevista al proveedor IA. / Consent to sending interview answers to the AI provider.',400)
        OpenAIInterview()  # Validate configuration before opening a session.
    existing_profile=profiles.get_profile(user,event)
    d=profiles.clean(existing_profile)
    existing=existing_profile['saved']
    if not existing:
        d['needs_status']='';d['offers_status']=''
    with LOCK:
        for iid in [i for i,v in SESSIONS.items() if v['expires']<time.time()]: SESSIONS.pop(iid,None)
        # One ephemeral draft per participant/event. Starting fresh invalidates prior draft.
        for iid in [i for i,v in SESSIONS.items() if v['owner']==user['id'] and v['event']==event]:SESSIONS.pop(iid,None)
        s={'id':secrets.token_urlsafe(24),'owner':user['id'],'event':event,'locale':locale,'mode':mode,'draft':d,'notes':{},'answered':[], 'question':'','focus':'name','revision':0,'status':'active','expires':time.time()+TTL,'busy':False}
        ask(s);SESSIONS[s['id']]=s
        return public(s)

def get(user,iid):
    with LOCK:return public(owned(user,iid))

def validate_revision(s,payload):
    if type(payload.get('revision')) is not int or payload['revision']!=s['revision']:
        raise Problem('El borrador cambió. Actualiza el resumen. / Draft changed. Refresh the summary.',409)
    if s.get('busy'):
        raise Problem('Una respuesta está en proceso. / An answer is being processed.',409)
    if s['status']=='confirmed':
        raise Problem('Entrevista ya confirmada; inicia otra para corregir. / Interview already confirmed; start another to edit.',409)

def guided(s,text):
    result=conversation.extractor.extract(text,{**s['draft'],'needs_status':s['draft'].get('needs_status') or 'present','offers_status':s['draft'].get('offers_status') or 'present'})
    changes={k:v for k,v in result['changes'].items() if k in FIELDS}
    if not changes and s['focus']!='review':
        field=s['focus']; lower=text.strip().lower().rstrip('.!?')
        if field in ENUMS:
            value=ENUMS[field].get(lower)
            if value: changes[field]=value
        elif lower in ('omitir','skip','prefiero no decir','prefer not to say'):
            if field in OPTIONAL: changes[field]=''
        elif lower not in ('no sé','no se','not sure','no estoy seguro','i don\'t know'):
            changes[field]=text.strip()
    return {'notes':[{'field':k,'value':v,'quote':text} for k,v in changes.items()], 'question':'','ask_field':''}

def validate_notes(result,text):
    if not isinstance(result,dict) or not isinstance(result.get('notes'),list) or len(result['notes'])>25:
        raise Problem('Respuesta IA inválida; no se cambió el borrador. / Invalid AI response; draft unchanged.',502)
    updates=[]
    for note in result['notes']:
        if not isinstance(note,dict) or set(note)!= {'field','value','quote'}:
            raise Problem('Nota inválida. / Invalid note.',502)
        k,v,q=note['field'],note['value'],note['quote']
        if k not in FIELDS or not isinstance(v,str) or not isinstance(q,str) or len(v)>1500 or not q or q not in text or len(q)>5000:
            raise Problem('Nota sin evidencia válida. / Note lacks valid evidence.',502)
        if k in ENUMS:
            if v not in set(ENUMS[k].values()):raise Problem('Valor no válido en nota. / Invalid note value.',502)
        elif v and v not in q:
            raise Problem('La nota no coincide con las palabras aportadas. / Note does not match supplied words.',502)
        elif not v and k not in OPTIONAL:
            raise Problem('No se puede omitir ese campo. / That field cannot be skipped.',502)
        updates.append((k,v,q))
    return updates

def turn(user,payload):
    text=payload.get('text')
    if not isinstance(text,str) or not text.strip() or len(text)>5000:
        raise Problem('Escribe o dicta una respuesta de hasta 5000 caracteres. / Enter an answer up to 5000 characters.')
    with LOCK:
        s=owned(user,payload.get('id'))
        turn_id=payload.get('turn_id')
        if turn_id is not None:
            if not isinstance(turn_id,str) or not 1<=len(turn_id)<=200: raise Problem('Invalid turn ID')
            previous=s.get('processed_turns',{}).get(turn_id)
            if previous is not None:
                if previous!=hashlib.sha256(text.encode()).hexdigest(): raise Problem('Turn ID already used',409)
                return public(s)
        validate_revision(s,payload)
        if s['status']!='active': raise Problem('Reanuda la entrevista antes de responder. / Resume before answering.',409)
        if s['revision']>=100:raise Problem('Límite de entrevista alcanzado. Revisa el resumen. / Interview limit reached. Review your summary.',409)
        s['busy']=True;snapshot=copy.deepcopy(s)
    try:
        result=OpenAIInterview().turn(snapshot['draft'],text,snapshot['question'],snapshot['focus'],snapshot['locale'],missing(snapshot)) if snapshot['mode'] in ('openai','realtime') else guided(snapshot,text)
        updates=validate_notes(result,text)
        with LOCK:
            s=owned(user,payload['id'])
            for k,v,q in updates:
                s['draft'][k]=v;s['notes'][k]={'value':v,'evidence':q,'source':s['mode']};s['answered'].append(k)
            for flag,fields in (('needs_status',NEEDS),('offers_status',OFFERS)):
                if s['draft'].get(flag)=='none':
                    for k in fields:s['draft'][k]='';s['notes'].pop(k,None)
            s['revision']+=1;s['review_token']=None;ask(s)
            if turn_id is not None:s.setdefault('processed_turns',{})[turn_id]=hashlib.sha256(text.encode()).hexdigest()
            # Permit model clarification only for an unresolved field or review.
            question=result.get('question','');focus=result.get('ask_field')
            if snapshot['mode'] in ('openai','realtime') and isinstance(question,str) and 0<len(question)<=500 and question.count('?')<=1 and (focus in missing(s) or (not missing(s) and focus=='review')):
                s['question']=question;s['focus']=focus
            if not updates and snapshot['mode']=='guided':
                s['focus']=snapshot['focus']
                s['question']=('No pude interpretar esa respuesta. ' if s['locale']=='es' else 'I could not interpret that answer. ')+snapshot['question']
            return public(s)
    finally:
        with LOCK:
            if payload.get('id') in SESSIONS:SESSIONS[payload['id']]['busy']=False

def control(user,payload):
    with LOCK:
        s=owned(user,payload.get('id'));validate_revision(s,payload)
        action=payload.get('action')
        if action=='pause':s['status']='paused'
        elif action=='resume':s['status']='active'
        elif action=='guided':s['mode']='guided';s['status']='active';ask(s)
        elif action=='discard':SESSIONS.pop(s['id']);return {'discarded':True}
        else:raise Problem('Acción inválida. / Invalid action.')
        s['revision']+=1;s['review_token']=None
        return public(s)

def edit_draft(user,payload):
    with LOCK:
        s=owned(user,payload.get('id'));validate_revision(s,payload)
        raw=payload.get('profile',{})
        d=profiles.clean(raw)
        for flag in ('needs_status','offers_status'):
            if raw.get(flag)=='':d[flag]=''
        for k in FIELDS:
            if d.get(k)!=s['draft'].get(k):
                s['notes'][k]={'value':d[k],'evidence':d[k],'source':'manual'}
                if d[k]:s['answered'].append(k)
                elif k in s['answered']:s['answered'].remove(k)
        s['draft']=d;s['revision']+=1;s['review_token']=None
        s['status']='active';ask(s)
        return public(s)


def summary(user,payload):
    with LOCK:
        s=owned(user,payload.get('id'));validate_revision(s,payload)
        if 'profile' in payload:
            d=profiles.validate_profile(payload['profile'])
            for k in FIELDS:
                if d.get(k)!=s['draft'].get(k):s['notes'][k]={'value':d[k],'evidence':d[k],'source':'manual'}
            s['draft']=d
        profiles.validate_profile(s['draft'])
        s['revision']+=1;s['status']='review';s['review_token']=secrets.token_urlsafe(24)
        return public(s)

def confirm(user,payload):
    with LOCK:
        s=owned(user,payload.get('id'));validate_revision(s,payload)
        if payload.get('confirmed') is not True or s['status']!='review' or not s.get('review_token') or not secrets.compare_digest(str(payload.get('review_token','')),s['review_token']):
            raise Problem('Revisa y confirma el resumen vigente. / Review and confirm the current summary.')
        profiles.save_profile(user,s['event'],{'profile':s['draft'],'confirmed':True})
        s['status']='confirmed';s['revision']+=1;s['notes']={};s['review_token']=None
        return public(s)


def connect_voice(user,payload):
    from backend.adapters import realtime_voice
    with LOCK:
        s=owned(user,payload.get('id'));validate_revision(s,payload)
        if s['mode']!='realtime' or s['status']!='active':
            raise Problem('Inicia o reanuda la entrevista de voz IA. / Start or resume the AI voice interview.',409)
        now=time.time()
        attempts=[t for t in s.get('voice_attempts',[]) if t>now-60]
        if len(attempts)>=3:raise Problem('Espera un minuto antes de reconectar. / Wait a minute before reconnecting.',429)
        s['voice_attempts']=attempts+[now]
        s['busy']=True;snapshot=copy.deepcopy(s)
    try:
        return realtime_voice.connect(snapshot,payload.get('sdp'))
    finally:
        with LOCK:
            if payload.get('id') in SESSIONS:SESSIONS[payload['id']]['busy']=False
