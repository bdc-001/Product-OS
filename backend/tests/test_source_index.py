from io import BytesIO
from app.services import source_index as source, codebase

def test_source_index_incremental_and_secret_exclusion(tmp_path,monkeypatch):
    monkeypatch.setattr(source,'INDEX_PATH',tmp_path/'index.sqlite3')
    monkeypatch.setattr(codebase,'codebase_root',lambda:tmp_path)
    current={'sha':'a'*40,'blob':'b'*40,'body':'\n'.join(['package activate']+['// context']*180+['func CampaignWorkflowHandler() {}'])}
    monkeypatch.setattr(codebase,'resolve_branch_ref',lambda root,branch:(branch,branch,current['sha']))
    def output(args,**kwargs):
        if 'rev-parse' in args:return current['sha']+'\n'
        return (f"100644 blob {current['blob']} {len(current['body'].encode())}\tconvin-activate/workflow.go\0"+f"100644 blob {'c'*40} 10\tconvin-activate/.env\0").encode()
    monkeypatch.setattr(source.subprocess,'check_output',output)
    class Process:
        def __init__(self,*a,**k):
            body=current['body'].encode();self.stdin=BytesIO();self.stdout=BytesIO(f"{current['blob']} blob {len(body)}\n".encode()+body+b'\n')
        def wait(self,**kwargs):return 0
    monkeypatch.setattr(source.subprocess,'Popen',Process)
    built=source.build('feature')
    assert built['file_count']==1 and built['skipped_files']==1
    hits=source.search('feature','CampaignWorkflowHandler')['hits']
    assert hits and hits[0]['line']>100 and 'CampaignWorkflowHandler' in hits[0]['text']
    assert source.build('feature')['cached']
    current.update(sha='d'*40,blob='e'*40,body='package activate\nfunc ReplacementHandler() {}')
    assert source.build('feature')['updated_files']==1
    assert not source.search('feature','CampaignWorkflowHandler')['hits']
    assert source.search('feature','ReplacementHandler')['hits']
    assert not source.allowed('../.env') and not source.allowed('secrets/token.json')
