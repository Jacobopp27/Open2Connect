"""Authenticated local stdio MCP bridge; no DB/admin credentials or arbitrary SQL.

Each process is bound to one short-lived token issued by the running app.
Every tool call is authorized again by the HTTP backend, including ownership,
event scope, session expiry and review-token confirmation.
"""
import json
import os
from typing import Literal
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, build_opener, HTTPRedirectHandler
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        return None

class AppBridge:
    def __init__(self, base_url=None, token=None):
        self.base=(base_url or os.getenv('OPEN2CONNECT_APP_URL','http://127.0.0.1:8000')).rstrip('/')
        p=urlparse(self.base)
        if (p.scheme!='https' and not (p.scheme=='http' and p.hostname in ('localhost','127.0.0.1','::1'))) or p.username or p.password or p.query or p.fragment or p.path:
            raise ValueError('App URL must be an HTTPS origin or loopback HTTP origin')
        self.token=token or os.getenv('OPEN2CONNECT_MCP_TOKEN','')
        self.opener=build_opener(NoRedirect())
    def request(self,path,body=None):
        if not self.token: raise ToolError('Configure OPEN2CONNECT_MCP_TOKEN from the app; do not paste it into a prompt.')
        headers={'Authorization':'Bearer '+self.token}
        if body is not None: headers.update({'Content-Type':'application/json','X-Open2Connect':'1'})
        req=Request(self.base+'/api/'+path,data=json.dumps(body).encode() if body is not None else None,headers=headers)
        try:
            with self.opener.open(req,timeout=35) as response:
                return json.loads(response.read(1000000))
        except HTTPError as e:
            status=e.code
            e.close()
            raise ToolError(f'App rejected operation (HTTP {status}). Check token scope, draft revision and confirmation; refresh current draft.') from None
        except (URLError,TimeoutError):
            raise ToolError('App unavailable; start the backend and check its origin.') from None

def create_server(bridge=None):
    bridge=bridge or AppBridge()
    mcp=MCPServer('Open2Connect interview')
    @mcp.tool()
    def start_interview(locale:Literal['es','en']='es',mode:Literal['guided','openai']='guided',ai_consent:bool=False)->dict:
        """Start own event interview. Obtain user consent before sending answers to OpenAI. Replaces own ephemeral draft for this event."""
        return bridge.request('interviews/start',{'locale':locale,'mode':mode,'ai_consent':ai_consent})
    @mcp.tool()
    def process_interview_turn(interview_id:str,revision:int,text:str)->dict:
        """Process participant's exact answer into own draft. Never send invented facts or private credentials. Does not save profile."""
        return bridge.request('interviews/turn',{'id':interview_id,'revision':revision,'text':text})
    @mcp.tool()
    def get_own_interview(interview_id:str)->dict:
        """Read own current interview draft, notes and revision; cannot read another participant or event."""
        return bridge.request('interviews/draft?'+urlencode({'id':interview_id}))
    @mcp.tool()
    def prepare_interview_summary(interview_id:str,revision:int)->dict:
        """Prepare the current factual profile for user review. Show the full summary and privacy settings before asking for confirmation."""
        return bridge.request('interviews/summary',{'id':interview_id,'revision':revision})
    @mcp.tool()
    def confirm_interview_profile(interview_id:str,revision:int,review_token:str,confirmed:bool=False)->dict:
        """Save ONLY after the user explicitly confirms the displayed current summary. Requires exact review token/revision; never infer confirmation."""
        return bridge.request('interviews/confirm',{'id':interview_id,'revision':revision,'review_token':review_token,'confirmed':confirmed})
    @mcp.tool()
    def control_interview(interview_id:str,revision:int,action:Literal['pause','resume','guided','discard'])->dict:
        """Pause/resume own interview, switch to local guide or discard ephemeral notes. No confirmed-profile deletion."""
        return bridge.request('interviews/control',{'id':interview_id,'revision':revision,'action':action})
    @mcp.tool()
    def get_own_profile()->dict:
        """Read only the authenticated participant's confirmed profile for the token's event."""
        return bridge.request('profile')
    return mcp

if __name__=='__main__':
    create_server().run(transport='stdio')
