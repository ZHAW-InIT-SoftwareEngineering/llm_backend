# SGLang Deployment Plan

## Summary

- Run everything from one production Compose stack: `sglang`, `api`, and `caddy`.
- Public internet exposes only Caddy on `80/443`; Caddy reverse-proxies to FastAPI only.
- FastAPI calls SGLang internally through the OpenAI-compatible `/v1/chat/completions` API.
- First model default: `Qwen/Qwen3-8B`, suitable for an L4 24GB GPU with conservative token limits.
- Protect `/chat` with a bearer token before it can consume GPU inference.

References used: SGLang documents Docker launch and OpenAI-compatible `/v1/chat/completions`; Caddy documents `reverse_proxy` and automatic HTTPS.

## Key Changes

- Add a production `Dockerfile` for FastAPI:
  - Install the project with `uv`.
  - Run `uvicorn main:app --app-dir src --host 0.0.0.0 --port 8000`.
- Update `deploy/docker-compose.prod.yaml`:
  - `sglang`: use `lmsysorg/sglang:latest-runtime`, `gpus: all`, `ipc: host`, `shm_size: 32g`, HF cache mount, and healthcheck on `http://sglang:30000/health`.
  - `api`: build the FastAPI image, expose only internal port `8000`, depend on healthy `sglang`.
  - `caddy`: expose `80:80` and `443:443`, mount `Caddyfile`, proxy the public domain to `api:8000`.
  - Do not publish SGLang to the public host interface.
- Add `deploy/Caddyfile`:
  - `${PUBLIC_DOMAIN}` reverse-proxies to `api:8000`.
  - No route to SGLang.
- Add env-driven runtime config:
  - `SGLANG_BASE_URL=http://sglang:30000/v1`
  - `SGLANG_MODEL=Qwen/Qwen3-8B`
  - `SGLANG_TIMEOUT_SECONDS=120`
  - `SGLANG_MAX_TOKENS=512`
  - `SGLANG_TEMPERATURE=0.2`
  - `API_BEARER_TOKEN=<secret>`
  - `HF_TOKEN=<secret>`
  - `PUBLIC_DOMAIN=<your-domain>`

## FastAPI Behavior

- Replace the mirror stub with an SGLang client.
- Use `httpx` to POST:
  - URL: `${SGLANG_BASE_URL}/chat/completions`
  - Body: `model`, `messages=[{"role": "user", "content": user_message}]`, `temperature`, `max_tokens`, `stream=false`.
- Return `choices[0].message.content` as the existing `ChatResponse.llm_answer`.
- Keep `/chat` non-streaming now, but isolate the LLM client so streaming can later be added without changing service/router boundaries.
- Add bearer auth on `/chat`; `/healthz` remains unauthenticated.
- Map upstream failures cleanly:
  - SGLang unavailable or timeout -> `503`
  - malformed SGLang response -> `502`
  - missing/invalid bearer token -> `401`

## VM Deployment Runbook

- Prereqs on VM:
  - NVIDIA driver works: `nvidia-smi`.
  - Docker has NVIDIA Container Toolkit available.
  - DNS `PUBLIC_DOMAIN` points to the VM.
  - Ports `80` and `443` are open.
  - `.env` contains `HF_TOKEN`, `API_BEARER_TOKEN`, `PUBLIC_DOMAIN`, and optional SGLang tuning vars.
- Start:
  - `docker compose --env-file .env -f deploy/docker-compose.prod.yaml up -d --build`
- Verify:
  - `docker compose -f deploy/docker-compose.prod.yaml ps`
  - `curl http://localhost:30000/health` from inside the SGLang container or Docker network if needed.
  - `curl https://$PUBLIC_DOMAIN/healthz`
  - `curl -H "Authorization: Bearer $API_BEARER_TOKEN" -H "Content-Type: application/json" -d '{"user_message":"Say hello in one sentence"}' https://$PUBLIC_DOMAIN/chat`

## Test Plan

- Unit-test the LLM client with a mocked `httpx` response:
  - successful chat completion extracts content.
  - timeout raises service-unavailable path.
  - missing `choices[0].message.content` raises bad-gateway path.
- API tests:
  - `/healthz` works without auth.
  - `/chat` rejects missing or wrong bearer token.
  - `/chat` returns `llm_answer` when the client succeeds.
- Deployment smoke test on VM:
  - SGLang healthcheck turns healthy.
  - FastAPI `/healthz` is reachable through Caddy.
  - Authenticated `/chat` returns generated text.
  - Direct public access to SGLang port is unavailable.

## Assumptions

- The VM has one NVIDIA L4 GPU with 24GB VRAM.
- `Qwen/Qwen3-8B` is the initial model unless changed via `SGLANG_MODEL`.
- Context and output limits stay conservative for first deployment; tune upward only after observing VRAM and latency.
- Caddy owns TLS and public routing.
- No streaming API is exposed in this milestone.
