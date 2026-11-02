# syntax=docker/dockerfile:1
FROM python:3.12-slim AS build
WORKDIR /src
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir build && python -m build --wheel --outdir /dist

FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    SIMULACRUM_HOST=0.0.0.0 \
    SIMULACRUM_PORT=8000
COPY --from=build /dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && rm -f /tmp/*.whl \
    && useradd --system --uid 10001 --no-create-home simulacrum
USER simulacrum
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=4s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import os,urllib.request as u; u.urlopen('http://127.0.0.1:%s/healthz' % os.environ['SIMULACRUM_PORT'], timeout=3)"]
# One process only: sessions live in memory (see docs/operations.md).
ENTRYPOINT ["simulacrum"]
CMD ["serve"]
