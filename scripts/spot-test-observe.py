"""Observe an already-started experiment, save sanitized evidence, remove test resources."""
import json
import subprocess
import time
from pathlib import Path
from ci_common import aws

c=json.loads(Path('runtime/spot-context.json').read_text())
started=time.monotonic()
try:
    while time.monotonic()-started < 900:
        exp=aws('fis','get-experiment','--id',c['experiment'])['experiment']
        Path('runtime/spot-experiment-private.json').write_text(json.dumps(exp,indent=2))
        state=exp['state']['status']
        if time.monotonic()-started>480 and state in ('initiating','running'):
            aws('fis','stop-experiment','--id',c['experiment'])
            raise RuntimeError('FIS exceeded the eight-minute action budget')
        if state in ('failed','cancelled','stopped'):
            raise RuntimeError('FIS did not complete; inspect private experiment evidence')
        job=json.loads(subprocess.check_output(['kubectl','-n','ray-assignment','get','rayjob',c['job'],'-o','json']))
        logs=subprocess.run(['kubectl','-n','ray-assignment','logs','job/'+c['job']],capture_output=True,text=True).stdout
        Path('runtime/spot-job-private.log').write_text(logs)
        status=job.get('status',{}).get('jobStatus')
        print(json.dumps({'fis':state,'job':status,'actor_recovered':'SPOT_CANARY_RECOVERED' in logs}),flush=True)
        if status in ('FAILED','STOPPED'):
            raise RuntimeError('Recovery workload failed; inspect private logs')
        if status=='SUCCEEDED' and state=='completed':
            req=aws('ec2','describe-spot-instance-requests','--spot-instance-request-ids',c['spot_request'])['SpotInstanceRequests'][0]
            evidence={'fis_state':state,'spot_request_status':req['Status']['Code'],'actor_recovered_on_different_node':'SPOT_CANARY_RECOVERED' in logs,'pipeline_idempotence_verified':'SPOT_PIPELINE_VERIFIED' in logs,'rayjob_status':status,'target_count':1,'target_pool':'workers','duration_before_interruption':'PT2M','elapsed_seconds':round(time.monotonic()-started)}
            assert evidence['actor_recovered_on_different_node'] and evidence['pipeline_idempotence_verified']
            assert evidence['spot_request_status']=='instance-terminated-by-experiment'
            Path('docs/evidence/spot-recovery.json').write_text(json.dumps(evidence,indent=2)+'\n')
            print(json.dumps(evidence),flush=True)
            break
        time.sleep(20)
    else: raise TimeoutError('Recovery did not finish within fifteen minutes')
finally:
    exp=aws('fis','get-experiment','--id',c['experiment'])['experiment']
    if exp['state']['status'] in ('initiating','running'):
        aws('fis','stop-experiment','--id',c['experiment'])
    subprocess.run(['kubectl','-n','ray-assignment','delete','rayjob',c['job'],'--ignore-not-found=true','--wait=true','--timeout=60s'],check=True)
    subprocess.run(['kubectl','-n','ray-assignment','delete','configmap','spot-canary','--ignore-not-found=true'],check=True)
    aws('fis','delete-experiment-template','--id',c['template'])
    subprocess.run(['aws','iam','delete-role-policy','--role-name',c['role'],'--policy-name','one-worker'],check=True)
    subprocess.run(['aws','iam','delete-role','--role-name',c['role']],check=True)
