import json
import os
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import test_app
from backend.modules import interviews
from backend.modules.auth import Problem
from backend.adapters import realtime_voice

class RealtimeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls): test_app.AppTest.setUpClass()
    @classmethod
    def tearDownClass(cls): test_app.AppTest.tearDownClass()
    def setUp(self):
        self.h=test_app.AppTest();self.h.setUp();interviews.SESSIONS.clear()
    def start(self):
        with patch('backend.modules.interviews.OpenAIInterview'):
            status,s,_=self.h.req('interviews/start',{'mode':'realtime','ai_consent':True},self.h.a)
        self.assertEqual(status,200);return s
    def test_consent_and_missing_config(self):
        with patch.dict(os.environ,{'OPENAI_API_KEY':'','OPENAI_MODEL':''}):
            self.assertEqual(self.h.req('interviews/start',{'mode':'realtime'},self.h.a)[0],400)
            self.assertEqual(self.h.req('interviews/start',{'mode':'realtime','ai_consent':True},self.h.a)[0],503)
    def test_retired_web_voice_route_is_unavailable(self):
        self.assertEqual(self.h.req('interviews/voice',{'id':'retired'},self.h.a)[0],404)
    def test_transcript_retry_idempotence_and_grounding(self):
        s=self.start();p={'id':s['id'],'revision':0,'text':'Soy Alex','turn_id':'audio-1'}
        result={'notes':[{'field':'name','value':'Alex','quote':'Soy Alex'}],'question':'¿Qué haces?','ask_field':'role'}
        with patch('backend.modules.interviews.OpenAIInterview') as model:
            model.return_value.turn.return_value=result
            status,first,_=self.h.req('interviews/turn',p,self.h.a)
            self.assertEqual(status,200);self.assertEqual(first['draft']['name'],'Alex')
            status,again,_=self.h.req('interviews/turn',p,self.h.a)
            self.assertEqual(status,200);self.assertEqual(again['revision'],1)
            self.assertEqual(model.return_value.turn.call_count,1)
            self.assertEqual(self.h.req('interviews/turn',{**p,'text':'Otra persona'},self.h.a)[0],409)
            model.return_value.turn.return_value={'notes':[{'field':'role','value':'Inventado','quote':'No sé'}]}
            self.assertEqual(self.h.req('interviews/turn',{**p,'revision':1,'turn_id':'audio-2','text':'No sé'},self.h.a)[0],502)
        self.assertFalse(self.h.req('profile',cookie=self.h.a)[1]['saved'])
    def test_mcp_cannot_create_voice_connection(self):
        s=self.start();token=self.h.req('mcp/token',{},self.h.a)[1]['token']
        self.assertEqual(self.h.req('interviews/voice',{'id':s['id'],'revision':0,'sdp':'v=0'},headers={'Authorization':'Bearer '+token})[0],403)

class RealtimeAdapterTest(unittest.TestCase):
    def test_official_sdp_contract_and_private_context(self):
        response=SimpleNamespace(text='v=0\r\nanswer',raise_for_status=lambda:None)
        calls=[]
        client=SimpleNamespace(post=lambda *a,**kw:(calls.append((a,kw)) or response))
        s={'owner':'private-user','locale':'es','question':'¿Qué haces?','draft':{'name':'Alex','contact':'secret@example.invalid'}}
        with patch.dict(os.environ,{'OPENAI_API_KEY':'test-only-secret','OPENAI_MODEL':'test-extractor'}):
            self.assertEqual(realtime_voice.connect(s,'v=0\r\noffer',client),{'sdp':response.text})
        args,kw=calls[0];self.assertEqual(args[0],'https://api.openai.com/v1/realtime/calls')
        config=json.loads(kw['files']['session'][1])
        self.assertEqual(config['audio']['input']['turn_detection']['type'],'semantic_vad')
        self.assertFalse(config['audio']['input']['turn_detection']['create_response'])
        self.assertNotIn('secret@example.invalid',config['instructions'])
        self.assertNotIn('private-user',config['instructions'])
        self.assertNotEqual(kw['headers']['OpenAI-Safety-Identifier'],'private-user')
    def test_provider_failure_is_redacted(self):
        def fail(*a,**kw): raise RuntimeError('test-only-secret')
        with patch.dict(os.environ,{'OPENAI_API_KEY':'test-only-secret','OPENAI_MODEL':'test-extractor'}):
            with self.assertRaises(Problem) as raised:
                realtime_voice.connect({'owner':'u','locale':'en','question':'Name?','draft':{}},'v=0',SimpleNamespace(post=fail))
            self.assertEqual(raised.exception.status,502)
            self.assertNotIn('test-only-secret',raised.exception.message)
