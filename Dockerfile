FROM python:3.11.17-slim-trixie@sha256:b7a9e5f6a93d6d4a31f129bbd4bdee69efccb6ded0fb230d78aafaf37af98377
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
RUN useradd --create-home --uid 1000 ray
WORKDIR /app
COPY pyproject.toml ./
RUN python -c 'import tomllib; print("\n".join(tomllib.load(open("pyproject.toml", "rb"))["project"]["dependencies"]))' > /tmp/requirements.txt \
    && pip install -r /tmp/requirements.txt
COPY src ./src
RUN pip install --no-deps . && python -m ray_platform.datasets --output /app/data \
    && mkdir /output && chown ray:ray /output
USER ray
ENV DATA_DIR=/app/data OUTPUT_DIR=/output
CMD ["python", "-m", "ray_platform.pipeline"]
