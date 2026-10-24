# Singapore cost plan (2026-10-24)

Total assignment spending ceiling: **USD 30 of credits**, not USD 30 after credits.
Account API reported an ACTIVE Free plan before deployment.
EC2 subsequently rejected both node groups as not Free Tier eligible. With the
user's prior authorization, the account was upgraded to ACTIVE Paid.
The assignment ceiling remains USD 30 regardless of available credits.
All figures below are estimates until AWS posts usage. No free-tier discount or
Spot saving is assumed in the conservative compute estimate.

AWS Price List API, region ap-southeast-1, returned these rates:

| Resource | Planning rate |
|---|---:|
| One m6g.large Linux On-Demand system node | $0.096/hour |
| m7g.large On-Demand ceiling used for each of up to two Spot workers | $0.102/hour each |
| EKS standard-support control plane | $0.10/hour |
| One NAT gateway | $0.059/hour plus $0.059/GB |
| One public IPv4 address for NAT | Allow $0.005/hour |

Maximum steady-state compute/network allowance: **$0.464/hour**, or **$3.72 for
eight hours** before storage, log ingestion, data transfer and requests. Budget
**$8 for the initial demo window** to leave room for these charges and cleanup
latency. Keep the remaining $22 for fixes and a later walkthrough; check cumulative
spending before every new deployment window.
The cold-start test observed a temporary third Spot instance during AWS
availability-zone balancing despite desired/max capacity of two. At the planning
rate this adds roughly $0.102/hour while overlapping; the $8 window allowance
includes room for it. Do not interpret the desired-node maximum as a hard cap on
instantaneous EC2 count.

Controls: one fixed system node, worker max two, no GPU, no load balancer, no
paid LLM API, private nodes with one NAT, S3 gateway endpoint, 20 GiB encrypted
gp3 boot volumes, three-day CloudWatch retention, and an eight-hour compute lease.
Cluster upgrade policy is STANDARD, preventing accidental extended-support fees.
Budget thresholds are $10/$20/$25 when a notification email is configured; without
an email the budget is visible in the console but does not send notifications.
All three email subscriptions were verified through AWS Budgets on October 24.
The address is kept in ignored local settings, not this repository.

The lease guard begins cleanup on its first 15-minute tick after expiry. It is
not an enforceable dollar cap: provisioning delays, deletion failures, price
changes, unexpected traffic and billing lag can affect actual spend. Normal
teardown immediately after capturing evidence remains the primary cost control.
Persistent S3/Glue/ECR/state incur small residual costs until explicitly cleaned.

Sources: AWS Price List API results retrieved for the instance types and NAT in
Singapore; EKS standard support: https://aws.amazon.com/eks/pricing/ ; IPv4:
https://aws.amazon.com/vpc/pricing/ .
