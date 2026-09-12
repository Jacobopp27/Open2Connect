import json
from backend.db import connect

def events():
    with connect() as db:
        return [dict(r) for r in db.execute('SELECT * FROM events')]

def seed_demo():
    examples = [
      ('demo-ana', {'name':'Ana · DEMO','role':'Diseñadora de producto','experience':'5 años','sector':'Educación','interests':'IA, educación','languages':'Español, English'}, {'purpose':'Crear un prototipo educativo','problem':'Integrar un backend Python','help':'Python y APIs','priority':'high','outcome':'Prototipo funcional','skills':'UX, diseño, investigación','knowledge':'Educación','services':'Diseño de interfaces','resources':'Kit de diseño','availability':'available'}),
      ('demo-sam', {'name':'Sam · DEMO','role':'Backend engineer','experience':'4 years','sector':'Education','interests':'Artificial intelligence, education','languages':'English, Spanish'}, {'purpose':'Build an education prototype','problem':'Improve product design','help':'UX design','priority':'medium','outcome':'Test a prototype','skills':'Python, backend, APIs','knowledge':'Data, AI','services':'API development','resources':'Open source tools','availability':'limited'}),
      ('demo-lina', {'name':'Lina · DEMO','role':'Estratega comercial','experience':'6 años','sector':'Salud','interests':'Negocios, salud','languages':'Español'}, {'purpose':'Validar una idea','problem':'Analizar datos de clientes','help':'Datos y analítica','priority':'medium','outcome':'Validación comercial','skills':'Ventas, marketing','knowledge':'Negocios','services':'Mentoría','resources':'Guía de entrevistas','availability':'available'})]
    with connect() as db:
        for uid, general, event in examples:
            db.execute('INSERT OR IGNORE INTO users VALUES (?,?,?,?,1)', (uid,uid+'@example.invalid','disabled',json.dumps(general)))
            event.update(contact='',share_contact=False)
            db.execute('INSERT OR IGNORE INTO profiles VALUES (?,?,?,1)', (uid,'medellin-2026',json.dumps(event)))
    return {'created': True, 'demo': True}
