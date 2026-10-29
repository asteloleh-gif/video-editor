"""Bounded control envelope for Desktop MCP. No shell, raw paths or publishing."""
from .media_workspace import identifier

def execute(service,request):
    if not isinstance(request,dict) or set(request)!={'action','args'} or not isinstance(request['args'],dict):raise ValueError('Invalid workspace action')
    action,args=request['action'],request['args']
    if action=='list' and args=={}:return service.listing()
    if action=='status' and set(args)=={'id'}:return service.status(identifier(args['id']))
    if action=='submit' and set(args)=={'id','kind','payload'} and args['kind'] in {'search','batch','acquire','story','plan'}:return service.submit(args)
    if action in {'cancel','resume'} and set(args)=={'id'}:return getattr(service,action)(identifier(args['id']))
    if action=='watch':
        from .workspace_discovery import save
        return save(service,args)
    if action=='ranked' and not set(args)-{'limit','search_id'}:
        from .workspace_discovery import ranked
        return ranked(service,**args)
    if action=='correction':
        from .workspace_style import correction
        return correction(service,args)
    if action=='style_propose':
        from .workspace_style import propose
        return propose(service,args)
    if action=='style' and args=={}:
        from .workspace_style import listing
        return listing(service)
    raise ValueError('Workspace action denied')

def editable(service,story_id):
    from .story_workspace import story_video
    story_video(service,story_id);story=service.story(story_id)
    for scene in story['scenes']:service.file_receipt(scene['asset_id'])
    narration(service,story_id)
    return story

def narration(service,story_id):
    from .story_jobs import digest
    story=service.story(identifier(story_id));source=service.folder(story_id)/'public/narration.wav'
    if source.is_symlink() or not source.resolve().is_relative_to(service.folder(story_id)) or digest(source)!=story['audio_sha256'] or source.stat().st_size>100*1024*1024:raise ValueError('Narration bytes changed')
    return {'path':str(source),'sha256':story['audio_sha256'],'kind':'audio','name':'Astel-narration-'+story_id+'.wav'}
