# Actual Spot interruption validation

On 2026-10-24, AWS FIS injected `aws:ec2:send-spot-instance-interruptions` into exactly
one tagged Spot worker with a two-minute interruption notice. The On-Demand
system/head node was excluded. An actor doing a 300-second task restarted on a
different worker and completed; the application rerun verified 1,800 canonical
rows with zero inserts and updates. EC2 reported `instance-terminated-by-experiment`.
See `evidence/spot-recovery.json` for sanitized evidence. FIS template, temporary
role, ConfigMap and RayJob were deleted after the test.

The workload proves bounded actor recomputation and persistent/idempotent data
recovery after a real Spot interruption. It does not prove checkpointed distributed
training, head-node HA, graceful draining, or recovery during prolonged capacity
shortage. Those remain production work.

`scripts/spot-test-prepare.py` prepares a scoped experiment and prints its private
context; it does not start FIS. `scripts/spot-test-observe.py` observes a started
experiment and cleans up resources. The first live run needed manual orchestration;
the corrected preparation helper has not been rerun end-to-end. These are operator
test helpers, not a fully unattended chaos platform. Inspect the exact target and
budget before explicitly starting an experiment; never target all instances.

The old lease has expired and compute is gone. Repeating the test requires a new
explicitly budgeted demo window. FIS action charges, EC2 replacement overlap and
normal EKS/NAT costs must all fit the remaining $30 gross budget.
