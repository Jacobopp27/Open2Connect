import asyncio
import json
import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch
import test_app
from backend.modules import interviews
from backend.modules.auth import Problem
from backend.adapters.interview_ai import OpenAIInterview
from backend.adapters.profile_store import SupabaseProfiles

class InterviewTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls): test_app.AppTest.setUpClass()
    @classmethod
    def tearDownClass(cls): test_app.AppTest.tearDownClass()
    def setUp(self):
        self.h=test_app.AppTest();self.h.setUp();interviews.SESSIONS.clear()
    def start(self,cookie=None,**extra):
        status,s,_=self.h.req('interviews/start',{'mode':'guided','locale':'es',**extra},cookie or self.h.a)
        self.assertEqual(status,200);return s
    def turn(self,s,text,cookie=None):
        return self.h.req('interviews/turn',{'id':s['id'],'revision':s['revision'],'text':text},cookie or self.h.a)
    def test_one_question_corrections_and_no_implicit_save(self):
        s=self.start();self.assertEqual(s['focus'],'name')
        _,s,_=self.turn(s,'Alex');self.assertEqual(s['focus'],'role');self.assertEqual(s['draft']['name'],'Alex')
        _,s,_=self.turn(s,'Nombre: Bea');self.assertEqual(s['draft']['name'],'Bea');self.assertEqual(s['notes']['name']['evidence'],'Nombre: Bea')
        self.assertFalse(self.h.req('profile',cookie=self.h.a)[1]['saved'])
    def test_ambiguous_enum_keeps_question(self):
        s=self.start()
        iid=s['id'];interviews.SESSIONS[iid]['focus']='priority'
        status,next_s,_=self.turn(s,'no sé')
        self.assertEqual(status,200);self.assertNotIn('priority',next_s['notes'])
    def test_revision_pause_resume_and_ownership(self):
        s=self.start()
        self.assertEqual(self.turn(s,'Alex',self.h.b)[0],404)
        self.assertEqual(self.h.req('interviews/draft?id='+s['id'],cookie=self.h.b)[0],404)
        _,next_s,_=self.turn(s,'Alex');self.assertEqual(self.turn(s,'Bea')[0],409)
        _,paused,_=self.h.req('interviews/control',{'id':s['id'],'revision':next_s['revision'],'action':'pause'},self.h.a)
        self.assertEqual(self.turn(paused,'Developer')[0],409)
        _,resumed,_=self.h.req('interviews/control',{'id':s['id'],'revision':paused['revision'],'action':'resume'},self.h.a)
        self.assertEqual(self.turn(resumed,'Developer')[0],200)
    def test_explicit_absence_and_review_confirmation(self):
        s=self.start()
        p=self.h.profile(needs_status='none',offers_status='none',skills='',problem='',help='',priority='',outcome='')
        status,review,_=self.h.req('interviews/summary',{'id':s['id'],'revision':0,'profile':p},self.h.a)
        self.assertEqual(status,200);self.assertFalse(self.h.req('profile',cookie=self.h.a)[1]['saved'])
        body={'id':s['id'],'revision':review['revision'],'review_token':review['review_token'],'confirmed':False}
        self.assertEqual(self.h.req('interviews/confirm',body,self.h.a)[0],400)
        body['confirmed']=True
        self.assertEqual(self.h.req('interviews/confirm',body,self.h.b)[0],404)
        status,saved,_=self.h.req('interviews/confirm',body,self.h.a)
        self.assertEqual(status,200);self.assertTrue(saved['saved']);self.assertEqual(saved['notes'],{})
        p=self.h.req('profile',cookie=self.h.a)[1]
        self.assertEqual(p['needs_status'],'none');self.assertEqual(p['skills'],'');self.assertEqual(p['problem'],'')
        self.assertEqual(self.h.req('interviews/confirm',body,self.h.a)[0],409)
    def test_stale_review_token_cannot_save_changed_draft(self):
        s=self.start();p=self.h.profile()
        _,review,_=self.h.req('interviews/summary',{'id':s['id'],'revision':0,'profile':p},self.h.a)
        _,resumed,_=self.h.req('interviews/control',{'id':s['id'],'revision':review['revision'],'action':'resume'},self.h.a)
        self.assertEqual(self.h.req('interviews/confirm',{'id':s['id'],'revision':resumed['revision'],'review_token':review['review_token'],'confirmed':True},self.h.a)[0],400)
    def test_partial_manual_correction_survives_next_turn(self):
        s=self.start()
        _,s,_=self.turn(s,'Alex')
        p={**s['draft'],'name':'Alex corrected','role':'Developer'}
        status,s,_=self.h.req('interviews/edit',{'id':s['id'],'revision':s['revision'],'profile':p},self.h.a)
        self.assertEqual(status,200);self.assertEqual(s['draft']['name'],'Alex corrected')
        _,s,_=self.turn(s,'omitir')
        self.assertEqual(s['draft']['name'],'Alex corrected')
        self.assertFalse(self.h.req('profile',cookie=self.h.a)[1]['saved'])

    def test_ai_not_configured_and_requires_consent(self):
        with patch.dict(os.environ,{'OPENAI_API_KEY':'','OPENAI_MODEL':''}):
            self.assertEqual(self.h.req('interviews/start',{'mode':'openai','ai_consent':True},self.h.a)[0],503)
            self.assertEqual(self.h.req('interviews/start',{'mode':'openai','ai_consent':False},self.h.a)[0],400)
    def test_model_notes_grounding_failure_keeps_state(self):
        s=self.start();interviews.SESSIONS[s['id']]['mode']='openai'
        bad={'notes':[{'field':'name','value':'Invented','quote':'My name is Alex'}],'question':'What is your role?','ask_field':'role'}
        with patch('backend.modules.interviews.OpenAIInterview') as adapter:
            adapter.return_value.turn.return_value=bad
            self.assertEqual(self.turn(s,'My name is Alex')[0],502)
        current=self.h.req('interviews/draft?id='+s['id'],cookie=self.h.a)[1]
        self.assertEqual(current['revision'],0);self.assertEqual(current['draft']['name'],'')
    def test_model_backed_turn_contract_with_test_double(self):
        s=self.start();interviews.SESSIONS[s['id']]['mode']='openai'
        good={'notes':[{'field':'name','value':'Alex','quote':'My name is Alex'}],'question':'What is your role?','ask_field':'role'}
        with patch('backend.modules.interviews.OpenAIInterview') as adapter:
            adapter.return_value.turn.return_value=good
            status,s,_=self.turn(s,'My name is Alex')
        self.assertEqual(status,200);self.assertEqual(s['draft']['name'],'Alex');self.assertEqual(s['question'],'What is your role?')
    def test_mcp_token_scope_revocation_and_logout(self):
        _,minted,_=self.h.req('mcp/token',{},self.h.a);headers={'Authorization':'Bearer '+minted['token']}
        status,s,_=self.h.req('interviews/start',{'mode':'guided'},headers=headers)
        self.assertEqual(status,200)
        self.assertEqual(self.h.req('recommendations',headers=headers)[0],403)
        self.assertEqual(self.h.req('profile',{'confirmed':True,'profile':self.h.profile()},headers=headers)[0],403)
        self.assertEqual(self.h.req('profile?event=other',headers=headers)[0],403)
        other=self.start(self.h.b)
        self.assertEqual(self.h.req('interviews/draft?id='+other['id'],headers=headers)[0],404)
        self.h.req('mcp/revoke',{},self.h.a)
        self.assertEqual(self.h.req('profile',headers=headers)[0],401)
        _,minted,_=self.h.req('mcp/token',{},self.h.a)
        self.h.req('logout',{},self.h.a)
        self.assertEqual(self.h.req('profile',headers={'Authorization':'Bearer '+minted['token']})[0],401)
    def test_mcp_sdk_protocol_real_backend(self):
        try:
            from mcp import Client
            from backend.mcp_server import AppBridge,create_server
        except ImportError:self.skipTest('Install integrations to test real MCP protocol')
        _,minted,_=self.h.req('mcp/token',{},self.h.a)
        bridge=AppBridge('http://127.0.0.1:'+str(self.h.server.server_port),minted['token'])
        async def run():
            async with Client(create_server(bridge)) as client:
                result=await client.call_tool('start_interview',{'locale':'en','mode':'guided'})
                self.assertFalse(result.is_error)
                data=result.structured_content or json.loads(result.content[0].text)
                if 'result' in data:data=data['result']
                self.assertEqual(data['focus'],'name')
                result=await client.call_tool('process_interview_turn',{'interview_id':data['id'],'revision':data['revision'],'text':'MCP Alex'})
                self.assertFalse(result.is_error)
                data=result.structured_content or json.loads(result.content[0].text)
                if 'result' in data:data=data['result']
                self.assertEqual(data['draft']['name'],'MCP Alex')
                result=await client.call_tool('confirm_interview_profile',{'interview_id':data['id'],'revision':data['revision'],'review_token':'invalid','confirmed':True})
                self.assertTrue(result.is_error)
        asyncio.run(run())

class AdapterTest(unittest.TestCase):
    def test_real_openai_request_schema_with_fake_transport(self):
        calls=[]
        def create(**kwargs):
            calls.append(kwargs)
            return SimpleNamespace(status='completed',output_text=json.dumps({'notes':[],'question':'What is your name?','ask_field':'name'}))
        adapter=OpenAIInterview(SimpleNamespace(responses=SimpleNamespace(create=create)))
        adapter.turn({'contact':'PRIVATE','name':''},'Hello','Name?','name','en',['name'])
        req=calls[0]
        self.assertFalse(req['store']);self.assertNotIn('PRIVATE',req['input']);self.assertTrue(req['text']['format']['strict'])
    def test_supabase_missing_config_fails_closed(self):
        with patch.dict(os.environ,{'SUPABASE_URL':'','SUPABASE_SECRET_KEY':'','SUPABASE_SERVICE_ROLE_KEY':''}):
            with self.assertRaises(Problem):SupabaseProfiles()
    def test_supabase_read_scopes_owner_and_event(self):
        calls=[]
        class Client:
            def table(self,name):calls.append(('table',name));self.name=name;return self
            def select(self,value):calls.append(('select',value));return self
            def eq(self,key,value):calls.append(('eq',key,value));return self
            def limit(self,n):return self
            def execute(self):return SimpleNamespace(data=[{'data':{'name':'Owner'}}] if self.name=='o2c_general_profiles' else [{'data':{'skills':'Python'},'visible':True}])
        result=SupabaseProfiles(Client()).get('owner-a','event-b')
        self.assertTrue(result['saved']);self.assertEqual(result['name'],'Owner')
        self.assertEqual(calls.count(('eq','owner_id','owner-a')),2)
        self.assertIn(('eq','event_id','event-b'),calls)

    def test_supabase_atomic_save_scoped_rpc_and_error_redaction(self):
        calls=[]
        class Client:
            def rpc(self,name,payload):calls.append((name,payload));return self
            def execute(self):return SimpleNamespace(data=None)
        store=SupabaseProfiles(Client());store.save('owner-a','event-a',{'name':'Alex'},{'skills':'Python'},True)
        self.assertEqual(calls[0][0],'o2c_save_profile');self.assertEqual(calls[0][1]['p_owner'],'owner-a')
        class Bad:
            def execute(self):raise ValueError('secret-key-and-private-data')
        with self.assertRaises(Problem) as error:store.execute(Bad())
        self.assertNotIn('secret-key',error.exception.message)
