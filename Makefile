export PATH := $(CURDIR)/.tools:$(PATH)
.PHONY: preflight setup test data run image image-offline local-up submit status local-down
preflight:
	bash scripts/preflight.sh
setup:
	python3.11 -m venv .venv
	.venv/bin/pip install -e '.[test]'
test:
	.venv/bin/python -m pytest -q
data:
	.venv/bin/python -m ray_platform.datasets
run: data
	OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 .venv/bin/python -m ray_platform.pipeline
image:
	docker build -t ray-assignment:local .
image-offline:
	bash scripts/download-wheels.sh
	docker build -f Dockerfile.offline -t ray-assignment:local .
local-up:
	bash scripts/local-up.sh
submit:
	bash scripts/submit.sh
status:
	kubectl --context kind-ray-assignment -n ray-assignment get rayjobs,pods
local-down:
	kind delete cluster --name ray-assignment
