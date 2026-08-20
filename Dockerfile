# AI Software Engineering Factory — production image
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# install deps first (better layer caching)
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --upgrade pip && pip install -e .

# tests + source
COPY tests ./tests
COPY .env.example ./.env.example

# run as non-root
RUN useradd -m -u 1000 factory && chown -R factory:factory /app
USER factory

ENTRYPOINT ["python", "-m", "factory"]
CMD ["--help"]
