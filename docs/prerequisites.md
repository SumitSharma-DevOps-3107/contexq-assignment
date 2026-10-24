# Prerequisites inspected on 2026-10-24

| Component | Observed |
|---|---|
| Architecture | Apple Silicon / ARM64 |
| Physical memory | 16 GiB |
| Logical CPUs | 10 |
| Available disk | Approximately 317 GiB |
| Docker engine | Initially 29.4.0; 29.9.2 after Desktop startup/restart |
| Docker allocation | 6 CPUs, approximately 7.75 GiB |
| Docker Buildx | 0.33.0-desktop.1 |
| kubectl | Initially 1.34.1; bundled version became 1.36.1; project pins 1.34.3 |
| kind | 0.31.0 |
| Helm | 4.1.4 |
| Terraform | 1.15.8 |
| AWS CLI | 2.34.37 |
| Python | Homebrew Python 3.11 used in project venv |

macOS system Python is 3.9.6 and is not used. Existing application files in the
parent CodexLab project were not modified. The assignment has its own Git repo.
No AWS resources or billing plan changes are part of this local setup.

The local cluster is disposable. Outputs are persisted separately in the ignored
runtime directory. Downloaded container images and Python packages consume disk
space and can be reused for subsequent runs.
