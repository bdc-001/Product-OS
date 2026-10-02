from io import BytesIO
from app.services import source_index as source, codebase

def test_source_index_incremental_and_secret_exclusion(tmp_path,monkeypatch):
    monkeypatch.setattr(source,'index_path',lambda:tmp_path/'index.sqlite3')
    monkeypatch.setattr(codebase,'codebase_root',lambda:tmp_path)
    current={'sha':'a'*40,'blob':'b'*40,'body':'\n'.join(['package billing']+['// context']*180+['func CampaignWorkflowHandler() {}'])}
    monkeypatch.setattr(codebase,'resolve_branch_ref',lambda root,branch:(branch,branch,current['sha']))
    def output(args,**kwargs):
        if 'rev-parse' in args:return current['sha']+'\n'
        return (f"100644 blob {current['blob']} {len(current['body'].encode())}\tbilling-service/workflow.go\0"+f"100644 blob {'c'*40} 10\tbilling-service/.env\0").encode()
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
    current.update(sha='d'*40,blob='e'*40,body='package billing\nfunc ReplacementHandler() {}')
    assert source.build('feature')['updated_files']==1
    assert not source.search('feature','CampaignWorkflowHandler')['hits']
    assert source.search('feature','ReplacementHandler')['hits']
    assert not source.allowed('../.env') and not source.allowed('secrets/token.json')


def test_index_lives_under_its_repository_and_evicts_outside_keep_window(tmp_path, monkeypatch):
    from app.config import settings
    from app.database import SessionLocal
    from app.models import Repository
    from app.services import repos

    db = SessionLocal()
    repo = Repository(name='index-keep-test', mode='local', default_branch='main', product_branch='main', indexed_branches=[])
    db.add(repo)
    db.commit()
    try:
        monkeypatch.setattr(settings, 'repository_id', repo.id)
        assert source.index_path() == repos.workspace_path('repos', str(repo.id), 'source.sqlite3')
        assert repos.mark_indexed(db, repo, 'main', keep=2) == []
        assert repos.mark_indexed(db, repo, 'feature/a', keep=2) == []
        assert repos.mark_indexed(db, repo, 'feature/b', keep=2) == []
        assert repo.indexed_branches == ['feature/b', 'feature/a', 'main']
        assert repos.mark_indexed(db, repo, 'feature/c', keep=2) == ['feature/a']
        assert repo.indexed_branches == ['feature/c', 'feature/b', 'main']

        monkeypatch.setattr(source, 'index_path', lambda: tmp_path / 'keep.sqlite3')
        with source.connect() as conn:
            for name in ('main', 'feature/a', 'feature/b', 'feature/c'):
                conn.execute('INSERT INTO branches VALUES(?,?,?)', (name, 'f' * 40, '{}'))
                conn.execute('INSERT INTO files VALUES(?,?,?)', (name, 'a.go', 'b' * 40))
        assert source.evict() == {'evicted': ['feature/a']}
        with source.connect() as conn:
            assert sorted(row['branch'] for row in conn.execute('SELECT branch FROM branches')) == ['feature/b', 'feature/c', 'main']
            assert conn.execute("SELECT count(*) FROM files WHERE branch='feature/a'").fetchone()[0] == 0
    finally:
        db.delete(repo)
        db.commit()
        db.close()
