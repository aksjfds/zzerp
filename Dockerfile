FROM python:3.14.6

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        git \
    && curl -fsSL https://deb.nodesource.com/setup_24.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && corepack enable pnpm \
    && python --version \
    && node --version \
    && pnpm --version \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

CMD ["/bin/bash"]