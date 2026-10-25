"""Restartable actor canary followed by the real idempotent data pipeline."""
import json
import os
import socket
import time
from pathlib import Path

import ray


@ray.remote(num_cpus=1, resources={'entity_resolver': 1}, max_restarts=2, max_task_retries=2)
class RecoveryCanary:
    def location(self):
        return {'pod': socket.gethostname(), 'node_id': ray.get_runtime_context().get_node_id()}

    def work(self):
        print('SPOT_CANARY_ATTEMPT_STARTED', flush=True)
        # Stateless work is intentionally long enough to overlap a real EC2 notice.
        time.sleep(300)
        return self.location()


ray.init(address=os.environ['RAY_ADDRESS'])
actor = RecoveryCanary.remote()
before = ray.get(actor.location.remote())
result = actor.work.remote()
print('SPOT_CANARY_READY ' + json.dumps(before), flush=True)
after = ray.get(result, timeout=780)
if before['node_id'] == after['node_id']:
    raise RuntimeError('Canary did not move to a replacement Ray node')
print('SPOT_CANARY_RECOVERED ' + json.dumps({'different_node': True}), flush=True)
ray.kill(actor)
ray.shutdown()
from ray_platform.pipeline import main
main()
report = json.loads(Path('/output/run.json').read_text())
if report['canonical_rows'] != 1800 or report['iceberg']['inserted'] != 0 or report['iceberg']['updated'] != 0:
    raise RuntimeError('Post-interruption pipeline did not preserve idempotent data')
print('SPOT_PIPELINE_VERIFIED ' + json.dumps({'canonical_rows': 1800, 'inserted': 0, 'updated': 0}), flush=True)
