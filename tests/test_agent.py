import unittest
from unittest.mock import patch
import test_app
from backend import db
from backend.adapters.app_database import postgres_sql


class AgentTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls): test_app.AppTest.setUpClass()
    @classmethod
    def tearDownClass(cls): test_app.AppTest.tearDownClass()
    def setUp(self):
        self.h=test_app.AppTest();self.h.setUp()
    def test_identity_and_consent(self):
        target=self.h.pair()
        self.assertEqual(self.h.req('agent/buscar',{})[0],401)
        self.assertEqual(self.h.req('agent/confirmar',{'id':target,'cambios':{'rol':'Injected'},'confirmed':True},self.h.a)[0],403)
        self.assertEqual(self.h.req('agent/confirmar',{'cambios':{'rol':'Engineer'}},self.h.a)[0],400)
        self.assertEqual(self.h.req('agent/confirmar',{'cambios':{'rol':'Engineer'},'confirmed':True},self.h.a)[0],200)
        self.assertEqual(self.h.req('profile',cookie=self.h.a)[1]['role'],'Engineer')
        self.assertEqual(self.h.req('agent/token',{},self.h.a)[0],400)
        self.assertEqual(self.h.req('agent/apariencia',{'imagen':'fake'},self.h.a)[0],400)
        results=self.h.req('agent/buscar',{'nombre':'Bea'},self.h.a)[1]['resultados']
        self.assertEqual(len(results),1);self.assertNotEqual(results[0]['id'],target)
    def test_arrival_encounter_and_block(self):
        target=self.h.pair();own=self.h.req('me',cookie=self.h.a)[1]['id']
        for cookie in (self.h.a,self.h.b):
            self.assertEqual(self.h.req('agent/checkin',{'sena':'Camisa azul','confirmed':True},cookie)[0],200)
        self.assertEqual(self.h.req('yo/estado?id='+own,cookie=self.h.b)[0],403)
        result=self.h.req('agent/recomendar',{},self.h.a)[1]
        self.assertEqual(result['recomendaciones'][0]['id'],target)
        self.assertNotIn('contact',str(result))
        for _ in range(2):self.assertEqual(self.h.req('yo/confirmar',{'otro':target},self.h.a)[0],200)
        with db.connect() as conn:self.assertEqual(len(conn.execute('SELECT * FROM encuentros').fetchall()),1)
        self.h.req('block',{'target':target},self.h.a)
        self.assertEqual(self.h.req('yo/estado',cookie=self.h.a)[1]['matches'],[])
        self.assertEqual(self.h.req('yo/confirmar',{'otro':target},self.h.a)[0],404)
    def test_database_dialect(self):
        self.assertEqual(postgres_sql('INSERT OR IGNORE INTO blocks VALUES (?,?)'),'INSERT INTO blocks VALUES (%s,%s) ON CONFLICT DO NOTHING')
        self.assertEqual(postgres_sql("SELECT '?' WHERE id=?"),"SELECT '?' WHERE id=%s")
        self.assertIn('LOCK TABLE',postgres_sql('BEGIN IMMEDIATE'))
