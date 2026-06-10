# uv install
FROM python:3.14-slim-trixie
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# ----
COPY . /llm_backend

# Disable development dependencies
ENV UV_NO_DEV=1

# Sync the project into a new environment, asserting the lockfile is up to date
WORKDIR /llm_backend
RUN uv sync --locked

# start the fastpi
CMD ["uv", "run", "fastapi", "run", "src/main.py", "--host", "0.0.0.0", "--port", "8000"]

# and something additionally:
# for all the AI haters: I (!!) wrote the comments NOT AI ;) - may I still use comments? 
