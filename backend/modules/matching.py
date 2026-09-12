import json
import re
import unicodedata
from backend.db import connect
from backend.modules.auth import Problem
from backend.modules.profiles import get_profile

# Small, inspectable bilingual vocabulary. Unknown terms still match literally.
CONCEPTS = {
 'python': ['python'], 'javascript': ['javascript', 'js', 'frontend', 'front-end'],
 'design': ['design', 'diseno', 'ux', 'ui'], 'marketing': ['marketing', 'mercadeo'],
 'sales': ['sales', 'ventas', 'comercial'], 'finance': ['finance', 'finanzas', 'financiero', 'financial'],
 'health': ['health', 'salud', 'healthcare'], 'education': ['education', 'educacion', 'edtech'],
 'ai': ['ai', 'ia', 'artificial intelligence', 'inteligencia artificial', 'machine learning'],
 'backend': ['backend', 'back-end', 'api', 'apis'], 'data': ['data', 'datos', 'analytics', 'analitica'],
 'mentoring': ['mentoring', 'mentoria', 'mentor'], 'funding': ['funding', 'financiacion', 'inversion', 'investment'],
 'prototype': ['prototype', 'prototipo', 'prototipado'], 'research': ['research', 'investigacion'],
 'business': ['business', 'negocio', 'negocios'], 'mobile': ['mobile', 'movil'],
 'sustainability': ['sustainability', 'sostenibilidad'], 'agriculture': ['agriculture', 'agricultura', 'agrotech']}
STOP = set('a an and the i we my our to for with need help want looking de del la el los las un una en por para con y o que mi mis me necesito busco ayuda quiero puedo tengo soy equipo team project proyecto solution solucion solve resolver problema problem ofrecer offer skills habilidades knowledge conocimiento experiencia experience construir build crear create desarrollo development persona personas none ninguno ninguna nada no sin not'.split())

def normalized(text):
    return ''.join(c for c in unicodedata.normalize('NFD', text.lower()) if unicodedata.category(c) != 'Mn')

def terms(text):
    text = normalized(text)
    # Do not turn explicit negatives into affirmative expertise or needs.
    text = re.sub(r'\b(?:no|not|sin|without)\b[^,;.]*', '', text)
    for concept, aliases in CONCEPTS.items():
        for alias in sorted(aliases, key=len, reverse=True):
            text = re.sub(r'\b' + re.escape(alias) + r'\b', concept, text)
    return {x for x in re.findall(r'[a-z0-9+#]+', text) if (len(x) > 2 or x in ('ai', 'ux', 'ui')) and x not in STOP}

def languages(text):
    value = normalized(text)
    found = set()
    for key, aliases in {'es': ['es', 'espanol', 'spanish'], 'en': ['en', 'ingles', 'english'], 'pt': ['pt', 'portugues', 'portuguese'], 'fr': ['fr', 'frances', 'french']}.items():
        if any(re.search(r'\b' + a + r'\b', value) for a in aliases):
            found.add(key)
    return found

def available(profile):
    return profile.get('availability') in ('available', 'limited')

def public_profile(row):
    p = {**json.loads(row['profile']), **json.loads(row['data'])}
    p.pop('contact', None)
    p.pop('share_contact', None)
    return {'id': row['id'], 'demo': bool(row['demo']), **p}

def recommendations(user, event):
    own = get_profile(user, event)
    if not own['saved']:
        raise Problem('Confirma tu perfil primero. / Confirm your profile first.')
    if not available(own):
        return {'recommendations': [], 'reason': 'unavailable'}
    from backend.adapters.profile_store import store
    rows = store().participants(event)
    with connect() as db:
        blocked = {r['target'] if r['user_id'] == user['id'] else r['user_id'] for r in db.execute('SELECT user_id,target FROM blocks WHERE user_id=? OR target=?', (user['id'],user['id']))}
    rows = [r for r in rows if r['visible'] and r['id'] != user['id'] and r['id'] not in blocked]
    def group(p, keys):
        if keys == need_keys and p.get('needs_status') == 'none': return ''
        if keys == offer_keys and p.get('offers_status') == 'none': return ''
        return ' · '.join(p.get(k, '') for k in keys if p.get(k))
    need_keys = ['problem', 'help', 'outcome']
    offer_keys = ['skills', 'knowledge', 'services', 'resources']
    affinity_keys = ['sector', 'interests']
    candidates = []
    for row in rows:
        p = public_profile(row)
        shared_lang = languages(own.get('languages', '')) & languages(p.get('languages', ''))
        if not available(p) or not shared_lang:
            continue
        reasons, score = [], 0
        for kind, left_keys, right_keys, weight in [
          ('they_help', need_keys, offer_keys, 4), ('you_help', offer_keys, need_keys, 4),
          ('shared_need', need_keys, need_keys, 2), ('affinity', affinity_keys, affinity_keys, 1)]:
            left, right = group(own, left_keys), group(p, right_keys)
            overlap = sorted(terms(left) & terms(right))
            if overlap:
                score += weight * min(len(overlap), 3)
                reasons.append({'kind': kind, 'terms': overlap, 'you': left, 'them': right})
        if reasons:
            candidates.append({'person': p, 'reasons': reasons, 'shared_languages': sorted(shared_lang), '_rank': score})
    candidates.sort(key=lambda c: (-c['_rank'], c['person'].get('name', ''), c['person']['id']))
    for c in candidates:
        c.pop('_rank')
    return {'recommendations': candidates[:3], 'reason': 'ok' if candidates else 'no_useful_results'}
