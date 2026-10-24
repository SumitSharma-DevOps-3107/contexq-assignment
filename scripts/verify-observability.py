"""Bounded owner-run smoke test; retain the cluster briefly, always delete the RayJob."""
import json
import os
import subprocess
import signal
import time
from pathlib import Path
from urllib.parse import urlencode

import yaml

from ci_common import check_budget


def run(*args):
    return subprocess.check_output(args, text=True, timeout=60)


def kube(*args):
    return json.loads(run('kubectl', '-n', 'ray-assignment', *args))


def main():
    def cancelled(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, cancelled)
    config = json.loads(Path('runtime/ci-environment.json').read_text())
    check_budget(config)
    if json.loads(run('aws', 'sts', 'get-caller-identity'))['Account'] != config['account']:
        raise SystemExit('Unexpected AWS account')
    if kube('get', 'rayjobs', '-o', 'json')['items']:
        raise SystemExit('Remove completed jobs or wait for the existing run first')
    subprocess.run(['python3', 'scripts/render-aws-job.py'], check=True)
    job = yaml.safe_load(Path('runtime/aws-rayjob.yaml').read_text())
    job['spec']['shutdownAfterJobFinishes'] = True
    job['spec']['ttlSecondsAfterFinished'] = 300
    job['spec']['backoffLimit'] = 0
    job['spec']['activeDeadlineSeconds'] = 600
    Path('runtime/observability-job.yaml').write_text(yaml.safe_dump(job))
    started = int(time.time() * 1000)
    name = kube('create', '-f', 'runtime/observability-job.yaml', '-o', 'json')['metadata']['name']
    evidence = {'job_succeeded': False, 'scraped_node_types': [], 'metric_families': [],
                'dashboard_unauthenticated_status': None, 'log_container_types': []}
    try:
        deadline = time.monotonic() + 600
        while time.monotonic() < deadline:
            state = kube('get', 'rayjob', name, '-o', 'json').get('status', {})
            if state.get('jobStatus') in ('FAILED', 'STOPPED') or state.get('jobDeploymentStatus') in ('Failed', 'ValidationFailed'):
                raise RuntimeError('RayJob failed; inspect private logs')
            evidence['job_succeeded'] = state.get('jobStatus') == 'SUCCEEDED'
            base = '/api/v1/namespaces/ray-assignment/services/ray-prometheus:9090/proxy/api/v1/'
            targets = json.loads(run('kubectl', 'get', '--raw', base + 'targets'))['data']['activeTargets']
            evidence['scraped_node_types'] = sorted({t['labels'].get('ray_node_type') for t in targets if t['labels'].get('job') == 'ray' and t['health'] == 'up'})
            query = '{__name__=~"ray_tasks|ray_node_cpu_utilization|ray_cluster_active_nodes",job="ray"}'
            metrics = json.loads(run('kubectl', 'get', '--raw', base + 'query?' + urlencode({'query': query})))['data']['result']
            evidence['metric_families'] = sorted({m['metric']['__name__'] for m in metrics})
            pods = kube('get', 'pods', '-l', 'ray.io/node-type=head', '-o', 'json')['items']
            if pods and pods[0]['status'].get('phase') == 'Running':
                code = 'import urllib.request,urllib.error\ntry:\n r=urllib.request.urlopen("http://localhost:8265/api/jobs/",timeout=3);print(r.status)\nexcept urllib.error.HTTPError as e:print(e.code)\nexcept urllib.error.URLError:print(0)'
                try:
                    evidence['dashboard_unauthenticated_status'] = int(run('kubectl', '-n', 'ray-assignment', 'exec', pods[0]['metadata']['name'], '-c', 'ray-head', '--', 'python', '-c', code).strip())
                except subprocess.CalledProcessError:
                    pass
            logs = json.loads(run('aws', 'logs', 'filter-log-events', '--log-group-name', '/ray-assignment/pods', '--start-time', str(started), '--limit', '1000', '--output', 'json'))
            Path('runtime/observability-private-logs.json').write_text(json.dumps(logs))
            evidence['log_container_types'] = sorted({kind for kind in ('ray-head', 'ray-worker') if any('_'+kind+'-' in e['logStreamName'] for e in logs.get('events', []))})
            print(json.dumps(evidence), flush=True)
            if (evidence['job_succeeded'] and evidence['scraped_node_types'] == ['head', 'worker']
                and len(evidence['metric_families']) == 3 and evidence['dashboard_unauthenticated_status'] in (401, 403)
                and evidence['log_container_types'] == ['ray-head', 'ray-worker']):
                Path('docs/evidence/observability-validation.json').write_text(json.dumps(evidence, indent=2) + '\n')
                return
            time.sleep(15)
        raise TimeoutError('Observability checks did not all pass within ten minutes')
    finally:
        subprocess.run(['kubectl', '-n', 'ray-assignment', 'delete', 'rayjob', name, '--wait=true', '--timeout=60s', '--ignore-not-found=true'], check=True)


if __name__ == '__main__':
    main()
