import http.client
import json
import tempfile
import threading
import unittest
from backend import db
from backend.server import Handler, ThreadingHTTPServer, LIMITS, FEATURES

class AppTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        db.DB_PATH = cls.temp.name + '/test.sqlite'
        db.initialize()
        cls.server = ThreadingHTTPServer(('127.0.0.1',0),Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start()
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.temp.cleanup()
    def setUp(self):
        LIMITS.clear()
        with db.connect() as conn:
            for table in ('encuentros','checkins','notifications','invitations','blocks','profiles','sessions','users'):
                conn.execute('DELETE FROM '+table)
        self.a=self.register('a@example.invalid'); self.b=self.register('b@example.invalid')
    def req(self,path,body=None,cookie='',headers=None):
        c=http.client.HTTPConnection('127.0.0.1',self.server.server_port)
        h={'Cookie':cookie}
        if body is not None:h.update({'Content-Type':'application/json','X-Open2Connect':'1'})
        if headers:h.update(headers)
        c.request('POST' if body is not None else 'GET','/api/'+path,json.dumps(body) if body is not None else None,h)
        r=c.getresponse(); data=json.loads(r.read()); cookie=r.getheader('Set-Cookie','').split(';')[0]; status=r.status;c.close()
        return status,data,cookie
    def register(self,email):
        status,_,cookie=self.req('register',{'email':email,'password':'test-password-2026'})
        self.assertEqual(status,200);return cookie
    def profile(self,**updates):
        p={'name':'Alex','role':'Developer','experience':'3 años','sector':'Educación','interests':'IA','languages':'Español, English','purpose':'Construir prototipo','problem':'Diseño UX','help':'Diseño UX','priority':'high','outcome':'Diseño validado','skills':'Python backend','knowledge':'APIs','services':'Backend','resources':'','availability':'available','contact':'alex@example.invalid','share_contact':True,'visible':True}
        p.update(updates);return p
    def save(self,cookie,p=None,event='medellin-2026'):
        return self.req('profile?event='+event,{'confirmed':True,'profile':p or self.profile()},cookie)
    def pair(self):
        self.assertEqual(self.save(self.a)[0],200)
        self.assertEqual(self.save(self.b,self.profile(name='Bea',help='Python',problem='Python',outcome='Python API',skills='UX design',contact='bea@example.invalid'))[0],200)
        return self.req('me',cookie=self.b)[1]['id']
    def test_auth_persistence_and_isolation(self):
        self.assertEqual(self.req('profile')[0],401)
        self.save(self.a)
        self.assertEqual(self.req('profile',cookie=self.a)[1]['name'],'Alex')
        self.assertFalse(self.req('profile',cookie=self.b)[1]['saved'])
        self.req('logout',{},self.a)
        self.assertEqual(self.req('profile',cookie=self.a)[0],401)
        status,_,cookie=self.req('login',{'email':'a@example.invalid','password':'test-password-2026'})
        self.assertEqual(status,200);self.assertTrue(self.req('profile',cookie=cookie)[1]['saved'])
    def test_confirm_required_and_invalid_fields(self):
        self.assertEqual(self.req('profile',{'profile':self.profile()},self.a)[0],400)
        self.assertFalse(self.req('profile',cookie=self.a)[1]['saved'])
        self.assertEqual(self.save(self.a,self.profile(availability='maybe'))[0],400)
        self.assertEqual(self.save(self.a,self.profile(name=''))[0],400)
        self.assertEqual(self.req('profile',{'profile':None,'confirmed':True},self.a)[0],400)
    def test_conversation_no_implicit_save(self):
        status,r,_=self.req('conversation',{'text':'Nombre: Paula; necesito: diseño UX; ofrezco: Python; disponibilidad: disponible; prioridad: alta','profile':{}},self.a)
        self.assertEqual(status,200);self.assertEqual(r['profile']['name'],'Paula');self.assertEqual(r['profile']['availability'],'available')
        self.assertIn('languages',r['missing']);self.assertFalse(r['saved'])
        self.assertFalse(self.req('profile',cookie=self.a)[1]['saved'])
        self.assertEqual(self.req('conversation',{'text':'Un texto sin etiquetas','profile':{}},self.a)[1]['changes'],{})
    def test_bilingual_evidence_and_private_contact(self):
        target=self.pair();r=self.req('recommendations',cookie=self.a)[1]['recommendations']
        self.assertEqual(r[0]['person']['id'],target)
        self.assertEqual({x['kind'] for x in r[0]['reasons']} & {'you_help','they_help'},{'you_help','they_help'})
        self.assertNotIn('contact',json.dumps(r));self.assertNotIn('email',json.dumps(r));self.assertNotIn('percent',json.dumps(r))
    def test_filters(self):
        target=self.pair()
        for update in ({'visible':False},{'availability':'unavailable'},{'languages':'Português'}):
            self.save(self.b,self.profile(**update));self.assertEqual(self.req('recommendations',cookie=self.a)[1]['recommendations'],[])
        self.pair();self.req('block',{'target':target},self.a)
        self.assertEqual(self.req('recommendations',cookie=self.a)[1]['recommendations'],[])
        self.assertEqual(self.req('recommendations',cookie=self.b)[1]['recommendations'],[])
    def test_event_isolation_and_general_reuse(self):
        self.pair()
        with db.connect() as conn:conn.execute('INSERT INTO events VALUES (?,?,?,?)',('other','Other','Other','Other'))
        profile=self.req('profile?event=other',cookie=self.a)[1]
        self.assertEqual(profile['name'],'Alex');self.assertNotIn('problem',profile)
        self.save(self.a,event='other')
        self.assertEqual(self.req('recommendations?event=other',cookie=self.a)[1]['recommendations'],[])
        self.assertEqual(self.req('profile?event=invalid',cookie=self.a)[0],404)
    def test_invitation_acceptance_and_contact_consent(self):
        target=self.pair();status,inv,_=self.req('connections/invite',{'target':target},self.a)
        self.assertEqual(status,200)
        self.assertNotIn('contact',self.req('connections',cookie=self.a)[1][0]['person'])
        self.assertEqual(self.req('connections/respond',{'id':inv['id'],'action':'accepted'},self.a)[0],404)
        self.assertEqual(self.req('connections/respond',{'id':inv['id'],'action':'accepted'},self.b)[0],200)
        self.assertEqual(self.req('connections',cookie=self.a)[1][0]['person']['contact'],'bea@example.invalid')
        self.save(self.b,self.profile(share_contact=False))
        self.assertNotIn('contact',self.req('connections',cookie=self.a)[1][0]['person'])
        self.assertEqual(self.req('connections/invite',{'target':target},self.a)[0],409)
        self.assertEqual(self.req('notifications',cookie=self.a)[1][0]['message'],'invitation_accepted')
    def test_reject_block_and_unauthorized_access(self):
        target=self.pair();inv=self.req('connections/invite',{'target':target},self.a)[1]
        third=self.register('third@example.invalid')
        self.assertEqual(self.req('connections/respond',{'id':inv['id'],'action':'accepted'},third)[0],404)
        self.assertEqual(self.req('connections',cookie=third)[1],[])
        self.req('connections/respond',{'id':inv['id'],'action':'rejected'},self.b)
        self.assertNotIn('contact',self.req('connections',cookie=self.a)[1][0]['person'])
        self.req('block',{'target':target},self.a)
        self.assertEqual(self.req('connections',cookie=self.a)[1],[])
        self.assertEqual(self.req('connections/invite',{'target':target},self.a)[0],404)
    def test_demo_idempotent_and_not_invitable(self):
        self.save(self.a)
        self.req('demo',{},self.a);self.req('demo',{},self.a)
        with db.connect() as conn:self.assertEqual(conn.execute('SELECT COUNT(*) FROM users WHERE demo=1').fetchone()[0],3)
        recs=self.req('recommendations',cookie=self.a)[1]['recommendations']
        self.assertTrue(all(r['person']['demo'] for r in recs));self.assertLessEqual(len(recs),3)
        self.assertEqual(self.req('connections/invite',{'target':'demo-ana'},self.a)[0],400)
    def test_csrf_protection(self):
        self.assertEqual(self.req('profile',{},self.a,{'X-Open2Connect':''})[0],403)
        self.assertEqual(self.req('profile',{},self.a,{'Origin':'https://evil.invalid'})[0],403)
    def test_no_useful_match(self):
        self.save(self.a,self.profile(sector='',interests='',problem='Cerámica',help='Alfarería',outcome='Vasija',skills='Arcilla',knowledge='',services=''))
        self.save(self.b,self.profile(sector='',interests='',problem='Astronomía',help='Telescopio',outcome='Observación',skills='Óptica',knowledge='',services=''))
        self.assertEqual(self.req('recommendations',cookie=self.a)[1]['reason'],'no_useful_results')
    def test_optional_connections(self):
        FEATURES['connections']=False
        try:self.assertEqual(self.req('connections',cookie=self.a)[0],404)
        finally:FEATURES['connections']=True

if __name__=='__main__':unittest.main()
