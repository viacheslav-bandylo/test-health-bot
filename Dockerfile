FROM python:3.12-slim AS base
WORKDIR /app

FROM base AS deps
COPY pyproject.toml ./
COPY src/ ./src/
RUN pip install --no-cache-dir .

FROM base AS production
RUN addgroup --gid 1001 app && adduser --uid 1001 --gid 1001 --disabled-password app
COPY --from=deps /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY src/ ./src/
COPY assessments/ ./assessments/
RUN mkdir -p data && chown app:app data
USER app
CMD ["python", "-m", "hea"]
