import json,subprocess,pathlib,datetime,hashlib
import argparse
parser=argparse.ArgumentParser()
parser.add_argument('--root',type=pathlib.Path,required=True)
root=parser.parse_args().root
def cmd(*args):
 return subprocess.run(args,capture_output=True,text=True,check=True).stdout.strip()
cpu={}
for n in (0,1,2,3,4,5,6,7,8,9,10,11):
 p=pathlib.Path('/sys/devices/system/cpu')/f'cpu{n}'
 cpu[str(n)]={name:(p/rel).read_text().strip() for name,rel in [('siblings','topology/thread_siblings_list'),('governor','cpufreq/scaling_governor'),('epp','cpufreq/energy_performance_preference')]}
images=json.loads(cmd('docker','image','inspect','routeevo-sandbox:d055c99c833a','routeevo-ale-ahc024:440437e8b148','routeevo-ale-ahc026:c4cb5eec9f62'))
result={'recorded_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'uname':cmd('uname','-a'),'cpu':cmd('lscpu'),'cpu_topology':cmd('lscpu','-e=CPU,CORE,SOCKET,ONLINE'),'cpu_policy':cpu,'memory':cmd('free','-b'),'disk':cmd('df','-B1','/home'),'docker':cmd('docker','version','--format','{{.Server.Version}} {{.Server.Os}}/{{.Server.Arch}}'),'images':[{k:x.get(k) for k in ('Id','RepoTags','RepoDigests','Architecture','Os','Size')} for x in images],'preflight_sha256':hashlib.sha256((root/'preflight.py').read_bytes()).hexdigest(),'uv_lock_sha256':hashlib.sha256((root/'repo/backend/uv.lock').read_bytes()).hexdigest()}
(root/'evidence/host.json').write_text(json.dumps(result,indent=2)+'\n')
