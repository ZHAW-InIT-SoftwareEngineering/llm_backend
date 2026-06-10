# Three-Repo Deployment Audit

This document audits the current deployment split across:

1. `/home/gabc/00_projects/demo_edge`
2. `/home/gabc/00_projects/llm_backend`
3. `/home/gabc/00_projects/DemoObject`

It focuses on the shared Caddy edge setup, Docker Compose wiring, GitHub Actions deployment wiring, public domains, image variables, container names, and health checks.

## Target Architecture

The intended architecture is:

```text
internet
  -> VM security group: 80/tcp and 443/tcp
  -> demo_edge Caddy container
  -> shared external Docker network: edge
  -> public-facing app containers
```

The ownership split is:

1. `demo_edge` owns public ingress.
2. `DemoObject` owns only DemoObject app containers.
3. `llm_backend` owns only the LLM backend app containers.

Only `demo_edge` should publish host ports `80` and `443`.

## What Is Done

### Shared Edge Repo

Repository: `/home/gabc/00_projects/demo_edge`

The Caddyfile currently routes:

```caddyfile
demo.init.zhaw.ch {
    reverse_proxy demoobject-frontend:80
}

llm-backend.cloudlab.zhaw.ch {
    reverse_proxy llm-backend-api:8000
}
```

This is aligned with the app container names:

1. `demoobject-frontend`
2. `llm-backend-api`

The edge Compose file is structurally correct:

```yaml
services:
  caddy:
    image: caddy:2.11.2-alpine
    container_name: demo-edge-caddy
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
      - "443:443/udp"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy_data:/data
      - caddy_config:/config
    networks:
      - edge

volumes:
  caddy_data:
  caddy_config:

networks:
  edge:
    external: true
```

This means:

1. Caddy is the only public entrypoint.
2. Caddy stores certificates in persistent Docker volumes.
3. Caddy joins the shared external `edge` network.
4. Caddy can reach app containers by Docker DNS name.

### DemoObject Repo

Repository: `/home/gabc/00_projects/DemoObject`

DemoObject no longer owns Caddy. The old Caddy files have been removed from the working tree:

1. `caddy/Caddyfile`
2. `caddy/Dockerfile`

The production Compose file now defines only:

1. `mongo`
2. `api`
3. `frontend`

The frontend service is correctly attached to both:

1. the default Compose network, so it can reach `api`
2. the external `edge` network, so Caddy can reach it as `demoobject-frontend`

Current frontend shape:

```yaml
frontend:
  image: ${DEMOOBJECT_FRONTEND_IMAGE}:${IMAGE_TAG}
  container_name: demoobject-frontend
  restart: unless-stopped
  expose:
    - "80"
  networks:
    - default
    - edge
```

This is correct for the shared-edge architecture because `frontend` does not publish host ports.

The DemoObject deploy workflow now:

1. builds only the backend and frontend images
2. no longer builds a Caddy image
3. exports `DEMOOBJECT_BACKEND_IMAGE`
4. exports `DEMOOBJECT_FRONTEND_IMAGE`
5. ensures the `edge` network exists before `docker compose up`
6. deploys only `mongo`, `api`, and `frontend`
7. waits for `demoobject-api` and `demoobject-frontend` to become healthy
8. validates public reachability through `https://demo.init.zhaw.ch`

The DemoObject image variable names are now aligned:

```yaml
image: ${DEMOOBJECT_BACKEND_IMAGE}:${IMAGE_TAG}
image: ${DEMOOBJECT_FRONTEND_IMAGE}:${IMAGE_TAG}
```

and the workflow exports the same names:

```bash
DEMOOBJECT_BACKEND_IMAGE=...
DEMOOBJECT_FRONTEND_IMAGE=...
```

### LLM Backend Repo

Repository: `/home/gabc/00_projects/llm_backend`

The deploy workflow is now in the GitHub Actions-discoverable path:

```text
.github/workflows/deploy.yaml
```

The workflow builds the root Dockerfile:

```yaml
context: .
file: ./Dockerfile
```

The workflow and Compose file use the same image variable:

```bash
LLM_BACKEND_IMAGE=ghcr.io/<owner>/llm-backend
```

```yaml
image: ${LLM_BACKEND_IMAGE}:${IMAGE_TAG}
```

The API container is named:

```yaml
container_name: llm-backend-api
```

This matches the `demo_edge` Caddy upstream:

```caddyfile
reverse_proxy llm-backend-api:8000
```

The API service is attached to the shared external network:

```yaml
networks:
  - edge
```

The API service does not publish host port `8000`; it only exposes port `8000` to Docker networking:

```yaml
expose:
  - "8000"
```

The LLM deploy workflow validates the same domain that Caddy routes:

```text
llm-backend.cloudlab.zhaw.ch
```

The Dockerfile starts FastAPI on all interfaces:

```dockerfile
CMD ["uv", "run", "fastapi", "run", "src/main.py", "--host", "0.0.0.0", "--port", "8000"]
```

This is required because Caddy reaches the API container over Docker networking.

## Validation Done

The following validations passed:

```bash
docker compose -f /home/gabc/00_projects/demo_edge/docker-compose.yaml config
docker compose -f /home/gabc/00_projects/llm_backend/deploy/docker-compose.prod.yaml config
docker compose -f /home/gabc/00_projects/DemoObject/deploy/docker-compose.prod.yaml config
```

The GitHub workflow YAML files also parse successfully:

```bash
python3 -c 'import yaml; ...'
```

Compose emitted expected local warnings for unset environment variables during validation. Those warnings are expected when running `docker compose config` outside the GitHub Actions deployment environment.

## What Is Missing

### 1. `llm_backend` Does Not Export `HF_TOKEN` Into The Remote Deploy Shell

The LLM workflow defines and validates:

```yaml
HF_TOKEN: ${{ secrets.HF_TOKEN }}
```

and includes `HF_TOKEN` in `required_secrets`.

However, inside the remote SSH deployment script, it does not assign or export `HF_TOKEN`.

Current remote script exports:

```bash
export LLM_BACKEND_IMAGE
export IMAGE_TAG
```

But the Compose file needs:

```yaml
environment:
  - HF_TOKEN=${HF_TOKEN}
```

Without exporting `HF_TOKEN` in the remote shell, the `sglang` container will receive an empty `HF_TOKEN` value during deployment.

Required fix:

```bash
HF_TOKEN=$(printf '%q' "${HF_TOKEN}")
```

and then:

```bash
export HF_TOKEN
```

This should be added in `/home/gabc/00_projects/llm_backend/.github/workflows/deploy.yaml` inside the SSH deployment heredoc before `docker compose pull` and `docker compose up`.

### 2. `demo_edge` Has No GitHub Actions Deployment Workflow

The edge repo currently has:

1. `Caddyfile`
2. `docker-compose.yaml`
3. `README.md`

That is enough for manual deployment, but not for independent automated deployment.

If the desired model is that all three repos deploy independently through GitHub Actions, then `demo_edge` still needs a workflow that:

1. validates required VM SSH configuration
2. uploads `docker-compose.yaml`
3. uploads `Caddyfile`
4. ensures the external `edge` network exists
5. runs `docker compose up -d`
6. validates that `demo-edge-caddy` is running
7. validates public reachability for:
   - `https://demo.init.zhaw.ch`
   - `https://llm-backend.cloudlab.zhaw.ch/healthz`

If manual edge deployment is acceptable, this is not a blocker.

### 3. `demo_edge` Files Are Not Yet Tracked By Git

The current `demo_edge` status shows:

```text
?? .dockerignore
?? Caddyfile
?? docker-compose.yaml
```

These files need to be added before committing the edge repo:

```bash
git add .dockerignore Caddyfile docker-compose.yaml README.md
```

### 4. `llm_backend` Workflow Move Needs To Be Recorded

The workflow was moved from:

```text
.github/workflow/deploy.yaml
```

to:

```text
.github/workflows/deploy.yaml
```

The plural `workflows` directory is the correct GitHub Actions path.

Current Git status represents this as a deletion plus a new untracked directory. This needs to be recorded with:

```bash
git add -A .github
```

### 5. `llm_backend` Dockerfile And Docker Ignore Move Need To Be Recorded

The current `llm_backend` status shows:

```text
D src/.dockerignore
D src/Dockerfile
?? .dockerignore
?? Dockerfile
```

This appears to be an intentional move from `src/` to the repo root so the GitHub Actions Docker build can use:

```yaml
context: .
file: ./Dockerfile
```

That is consistent with the current workflow.

The move still needs to be recorded:

```bash
git add -A src/.dockerignore src/Dockerfile .dockerignore Dockerfile
```

## Current Overall Status

The three-repo architecture is mostly aligned:

1. `demo_edge` owns the public Caddy proxy.
2. `DemoObject` no longer owns Caddy.
3. `DemoObject` exposes `demoobject-frontend` only on Docker networking.
4. `llm_backend` exposes `llm-backend-api` only on Docker networking.
5. Caddy routes match the current app container names.
6. The LLM public domain is consistent between edge and the LLM deploy workflow.
7. The DemoObject image variable names are consistent between workflow and compose.

The main functional item still missing is exporting `HF_TOKEN` into the remote `llm_backend` deployment shell.

The remaining items are repository hygiene or deployment completeness:

1. add/commit untracked and moved files
2. optionally add an automated deploy workflow for `demo_edge`
