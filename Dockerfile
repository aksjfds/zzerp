FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        git \
    && curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && corepack enable pnpm \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt backend/requirements-dev.txt /tmp/zzerp-requirements/

RUN python -m pip install --no-cache-dir \
        -r /tmp/zzerp-requirements/requirements-dev.txt \
    && python --version \
    && node --version \
    && pnpm --version \
    && uvicorn --version

CMD ["/bin/bash"]
