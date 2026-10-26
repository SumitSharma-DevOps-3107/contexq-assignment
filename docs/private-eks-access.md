# Private EKS evidence access

The module keeps the EKS API private. For a bounded owner-operated evidence run,
set compute enable_demo_ssm=true before applying. The existing nodes receive only
SSM registration/channel permissions. The operator separately needs StartSession
rights. No public IP, SSH port, public API or extra bastion is created.

Install AWS's official Session Manager plugin locally. Identify the system-pool
EC2 instance and confirm SSM reports Online. Start
AWS-StartPortForwardingSessionToRemoteHost through that instance, forwarding the
exact private EKS hostname port 443 to localhost port 18443. Start the bridge:

```sh
.venv/bin/python scripts/eks-tunnel-proxy.py --host "$EKS_HOST"
```

The bridge accepts only CONNECT to that exact hostname:443, listens on loopback
port 18444, and forwards bytes to the SSM tunnel. TLS terminates at EKS and the
original hostname and cluster CA remain verified; never use insecure-skip-tls-verify.
Set the platform input private_api_proxy_url=http://127.0.0.1:18444 for owner-run
Terraform. Set the same proxy-url on the dedicated kubeconfig cluster entry.
Keep the normal original server URL, not localhost, in the kubeconfig.

Use kubectl port-forward with --address 127.0.0.1 for Grafana/Ray/Prometheus,
and keep credentials in ignored files. Close forwards, bridge and SSM session
after the evidence run; remove demo nodes through normal teardown. The lease
fallback also deletes the nodes. CI runners already inside the VPC should leave
the proxy input null. Do not publish this laptop proxy into shared CI settings.

Limitations: node SSM opt-in affects the shared role for both pools. Session
Manager access is privileged operational access, not workload identity. A durable
production design should use a dedicated operator role/path with audited access,
not rely on a transient worker or this demonstration bridge.
