"""Replaceable extraction adapter. No external AI, inferred facts, or silent persistence."""
import re
from backend.modules.profiles import GENERAL, EVENT, REQUIRED, clean
from backend.modules.auth import Problem

LABELS = {
 'name': ['nombre', 'name', 'me llamo', 'my name is'],
 'role': ['rol', 'role', 'soy', 'i am'],
 'experience': ['experiencia', 'experience'], 'sector': ['sector', 'industria', 'industry'],
 'interests': ['intereses', 'interests'], 'languages': ['idiomas', 'languages', 'hablo', 'i speak'],
 'purpose': ['propósito', 'proposito', 'purpose'], 'problem': ['problema', 'problem'],
 'help': ['necesito', 'ayuda', 'need', 'i need'], 'priority': ['prioridad', 'priority'],
 'outcome': ['resultado', 'outcome'], 'skills': ['habilidades', 'skills', 'ofrezco', 'i offer'],
 'knowledge': ['conocimiento', 'knowledge'], 'services': ['servicios', 'services'],
 'resources': ['recursos', 'resources'], 'availability': ['disponibilidad', 'availability'],
 'contact': ['contacto', 'contact']}

class RulesExtractor:
    name = 'rules-v1'
    def extract(self, text, profile):
        result = clean(profile)
        changes = {}
        # Explicit labels preserve user's exact words. Semicolons/newlines delimit facts.
        aliases = {alias: key for key, values in LABELS.items() for alias in values}
        pattern = r'(?:^|[;\n]|[.!?]\s+)\s*(' + '|'.join(re.escape(a) for a in sorted(aliases, key=len, reverse=True)) + r')\s*(?::|=|\s)\s*(.*?)(?=(?:[;\n]|[.!?]\s+)\s*(?:' + '|'.join(re.escape(a) for a in sorted(aliases, key=len, reverse=True)) + r')\b|$)'
        for match in re.finditer(pattern, text, flags=re.I | re.S):
            key = aliases[match.group(1).lower()]
            value = match.group(2).strip(' ;\n.')
            if value:
                if key in ('availability', 'priority'):
                    choices = {'disponible':'available', 'available':'available', 'tiempo limitado':'limited', 'limitado':'limited', 'limited':'limited', 'no disponible':'unavailable', 'unavailable':'unavailable', 'alta':'high', 'high':'high', 'media':'medium', 'medium':'medium', 'baja':'low', 'low':'low'}
                    value = choices.get(value.lower(), value)
                result[key] = value[:1500]
                changes[key] = result[key]
        return {'profile': result, 'changes': changes, 'missing': [k for k in REQUIRED if not result[k]], 'adapter': self.name, 'saved': False}

extractor = RulesExtractor()

def converse(payload):
    text = payload.get('text', '')
    if not isinstance(text, str) or not text.strip() or len(text) > 10000:
        raise Problem('Escribe o dicta hasta 10.000 caracteres. / Enter up to 10,000 characters.')
    return extractor.extract(text, payload.get('profile', {}))
