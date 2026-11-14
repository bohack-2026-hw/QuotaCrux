import json,pathlib,sqlite3,hashlib,fcntl,subprocess,datetime
import argparse
parser=argparse.ArgumentParser()
parser.add_argument('--root',type=pathlib.Path,required=True)
root=parser.parse_args().root
from quotacrux import config
models=config.default_model_configs()
result={'recorded_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source_sha':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'model':models['small'].public_dict(),'dotenv_mode':oct((root/'repo/backend/.env').stat().st_mode & 0o777),'workers':{}}
for name in ('a','b'):
 var=root/f'var-worker-{name}'
 conn=sqlite3.connect(f'file:{var}/routeevo.sqlite3?mode=ro',uri=True)
 conn.row_factory=sqlite3.Row
 record=json.loads((root/'evidence'/f'worker-{name}.json').read_text())
 row=conn.execute('SELECT * FROM tasks WHERE task_id=?',(record['task_id'],)).fetchone()
 manifest=json.loads(row['manifest_json'])
 manifest_sha=hashlib.sha256(json.dumps(manifest,sort_keys=True).encode()).hexdigest()
 assert manifest_sha==row['manifest_sha256']==record['manifest_sha256']
 files={}
 for key,meta in manifest['files'].items():
  actual=hashlib.sha256((var/'tasks'/record['task_id']/meta['file']).read_bytes()).hexdigest()
  assert actual==meta['sha256']
  files[key]=actual
 counts={table:conn.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0] for table in ('tasks','runs','model_calls','evaluations')}
 counts['final_evaluations']=conn.execute("SELECT COUNT(*) FROM evaluations WHERE dataset='final'").fetchone()[0]
 assert counts['model_calls']==counts['runs']==counts['final_evaluations']==0
 assert counts['evaluations']==18
 assert conn.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
 assert not conn.execute('PRAGMA foreign_key_check').fetchall()
 unlocked={}
 for filename in ('run.lock','compare.lock'):
  with (var/filename).open('a') as f:
   fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
   unlocked[filename]=True
 result['workers'][name]={'counts':counts,'manifest_sha256':manifest_sha,'file_hashes_verified':files,'locks_released':unlocked,'integrity_check':'ok','evaluation_status_counts':[dict(x) for x in conn.execute('SELECT dataset,status,COUNT(*) AS count FROM evaluations GROUP BY dataset,status')]}
 conn.close()
result['running_routeevo_containers']=subprocess.check_output(['docker','ps','--filter','name=routeevo-','--format','{{.Names}}'],text=True).splitlines()
(root/'evidence/ledger-audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'source_sha':result['source_sha'],'model':result['model']['model'],'workers':{k:v['counts'] for k,v in result['workers'].items()},'running_routeevo_containers':result['running_routeevo_containers']}))
