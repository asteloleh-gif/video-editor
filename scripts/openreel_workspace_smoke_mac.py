#!/usr/bin/env python3
"""Read-only MCP smoke of the installed candidate; never print its token."""
import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args):return None

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--job');args=parser.parse_args()
    descriptor=Path.home()/'.openreel/astel-voicebox-mcp-endpoint.json'
    if descriptor.is_symlink() or descriptor.stat().st_mode&0o077:raise ValueError('Private descriptor required')
    endpoint=json.loads(descriptor.read_text());u=urlsplit(endpoint['url'])
    if u.scheme!='http' or u.hostname!='127.0.0.1' or not u.port or u.path!='/mcp' or u.query or u.fragment or u.username or u.password:raise ValueError('Loopback candidate endpoint required')
    def call(method,params):
        req=Request(endpoint['url'],data=json.dumps({'jsonrpc':'2.0','id':1,'method':method,'params':params}).encode(),headers={'Authorization':'Bearer '+endpoint['token'],'Content-Type':'application/json'})
        with build_opener(ProxyHandler({}),NoRedirect()).open(req,timeout=40) as response:
            value=json.loads(response.read(3*1024*1024))
        return value['result']
    tools=call('tools/list',{})['tools'];names=[x['name'] for x in tools]
    checks={}
    for name,arguments in [('astel_workspace_style',{}),*([('astel_workspace_job_status',{'id':args.job})] if args.job else [])]:
        result=call('tools/call',{'name':name,'arguments':arguments});checks[name]=not result.get('isError',False)
    print(json.dumps({'tool_count':len(names),'workspace_tools':[n for n in names if n.startswith('astel_workspace_')],'reads':checks,'publishing_called':False}))

if __name__=='__main__':main()
