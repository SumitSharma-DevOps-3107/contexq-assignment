"""Prepare one explicit worker interruption; does not start the FIS experiment."""
import json
import os
import subprocess
import time
from pathlib import Path
import yaml
from ci_common import aws, check_budget


def kube(*args):
    return json.loads(subprocess.check_output(['kubectl','-n','ray-assignment',*args],text=True))


config=json.loads(Path('runtime/ci-environment.json').read_text())
check_budget(config)
assert aws('sts','get-caller-identity')['Account']==config['account']
assert not kube('get','rayjobs','-o','json')['items'], 'Existing RayJobs must finish first'
subprocess.run(['python3','scripts/render-aws-job.py'],check=True)
cm={'apiVersion':'v1','kind':'ConfigMap','metadata':{'name':'spot-canary','namespace':'ray-assignment'},'data':{'spot_workload.py':Path('reliability/spot_workload.py').read_text()}}
Path('runtime/spot-configmap.yaml').write_text(yaml.safe_dump(cm))
subprocess.run(['kubectl','apply','-f','runtime/spot-configmap.yaml'],check=True)
job=yaml.safe_load(Path('runtime/aws-rayjob.yaml').read_text())
job['metadata']['generateName']='spot-canary-'
job['spec'].update(entrypoint='python /canary/spot_workload.py',backoffLimit=0,activeDeadlineSeconds=900,ttlSecondsAfterFinished=300)
head=job['spec']['rayClusterSpec']['headGroupSpec']['template']['spec']
head['volumes'].append({'name':'canary','configMap':{'name':'spot-canary'}})
head['containers'][0]['volumeMounts'].append({'name':'canary','mountPath':'/canary','readOnly':True})
Path('runtime/spot-rayjob.yaml').write_text(yaml.safe_dump(job))
name=kube('create','-f','runtime/spot-rayjob.yaml','-o','json')['metadata']['name']
context={'job':name}
Path('runtime/spot-context.json').write_text(json.dumps(context))
for _ in range(36):
    pods=kube('get','pods','-l','ray.io/node-type=head','-o','json')['items']
    if pods:
        log=subprocess.run(['kubectl','-n','ray-assignment','logs','job/'+name],capture_output=True,text=True).stdout
        lines=[x.split('SPOT_CANARY_READY ',1)[1] for x in log.splitlines() if 'SPOT_CANARY_READY ' in x]
        if lines:
            worker=kube('get','pod',json.loads(lines[-1])['pod'],'-o','json')
            node=json.loads(subprocess.check_output(['kubectl','get','node',worker['spec']['nodeName'],'-o','json']))
            assert node['metadata']['labels']['assignment-pool']=='workers'
            instance=node['spec']['providerID'].split('/')[-1]
            details=aws('ec2','describe-instances','--instance-ids',instance)['Reservations'][0]['Instances'][0]
            assert details['InstanceLifecycle']=='spot' and details['State']['Name']=='running'
            assert {t['Key']:t['Value'] for t in details['Tags']}.get('eks:nodegroup-name')=='workers'
            context.update(head=pods[0]['metadata']['name'],instance=instance,spot_request=details['SpotInstanceRequestId'],original_node=node['metadata']['name'])
            break
    time.sleep(5)
else:
    raise RuntimeError('Canary did not start; delete the job recorded in runtime/spot-context.json')
arn=f"arn:aws:ec2:{config['region']}:{config['account']}:instance/{instance}"
role='ray-assignment-fis-test'
trust={'Version':'2012-10-17','Statement':[{'Effect':'Allow','Principal':{'Service':'fis.amazonaws.com'},'Action':'sts:AssumeRole','Condition':{'StringEquals':{'aws:SourceAccount':config['account']},'ArnLike':{'aws:SourceArn':f"arn:aws:fis:{config['region']}:{config['account']}:experiment/*"}}}]}
policy={'Version':'2012-10-17','Statement':[{'Effect':'Allow','Action':'ec2:SendSpotInstanceInterruptions','Resource':arn},{'Effect':'Allow','Action':'ec2:DescribeInstances','Resource':'*'}]}
Path('runtime/fis-trust.json').write_text(json.dumps(trust));Path('runtime/fis-policy.json').write_text(json.dumps(policy))
aws('iam','create-role','--role-name',role,'--assume-role-policy-document','file://runtime/fis-trust.json')
subprocess.run(['aws','iam','put-role-policy','--role-name',role,'--policy-name','one-worker','--policy-document','file://runtime/fis-policy.json'],check=True)
template={'description':'Assignment single-worker Spot recovery test','targets':{'worker':{'resourceType':'aws:ec2:spot-instance','resourceArns':[arn],'selectionMode':'ALL'}},'actions':{'interrupt':{'actionId':'aws:ec2:send-spot-instance-interruptions','parameters':{'durationBeforeInterruption':'PT2M'},'targets':{'SpotInstances':'worker'}}},'stopConditions':[{'source':'none'}],'roleArn':f"arn:aws:iam::{config['account']}:role/{role}",'tags':{'Project':'ray-assignment','Purpose':'bounded-spot-test'}}
Path('runtime/fis-template.json').write_text(json.dumps(template,indent=2))
result=aws('fis','create-experiment-template','--cli-input-json','file://runtime/fis-template.json')
context.update(template=result['experimentTemplate']['id'],role=role)
Path('runtime/spot-context.json').write_text(json.dumps(context,indent=2))
print(json.dumps({'prepared':True,'target_count':1,'pool':'workers','capacity':'spot','duration':'PT2M','job':name}))
