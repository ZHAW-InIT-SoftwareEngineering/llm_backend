# LLM Backend

Small FastAPI backend that exposes a chat endpoint backed by an OpenAI-compatible
SGLang server.

The API has two routes:

- `GET /healthz` returns a basic service health response.
- `POST /chat` forwards a user message to the configured LLM and returns the
  assistant answer.

## Requirements

- Python 3.14
- [uv](https://docs.astral.sh/uv/) for dependency management
- Optional: Docker
- An OpenAI-compatible LLM server reachable at:

```text
http://host.docker.internal:30000/v1/chat/completions
```

The current client is configured in `src/clients/llm/llm_client.py` with:

- Model: `Qwen/Qwen2.5-1.5B-Instruct`
- Endpoint: `http://host.docker.internal:30000/v1/chat/completions`
- Timeout: 60 seconds

## Project Layout

```text
.
|-- Dockerfile
|-- deploy/
|   `-- docker-compose.prod.yaml
|-- pyproject.toml
|-- src/
|   |-- main.py
|   |-- api/
|   |   |-- routers/
|   |   `-- schemas/
|   |-- clients/
|   |   `-- llm/
|   `-- services/
|       `-- chat/
`-- uv.lock
```

## Run Locally

Install dependencies:

```bash
uv sync
```

Start the development server:

```bash
uv run fastapi dev src/main.py
```

The API is available at `http://127.0.0.1:8000`.

Interactive FastAPI documentation is available at:

- `http://127.0.0.1:8000/docs`
- `http://127.0.0.1:8000/redoc`

## Run With Docker

Build the image from the repository root:

```bash
docker build -t llm_backend .
```

Run the API:

```bash
docker run --rm \
  --add-host=host.docker.internal:host-gateway \
  -p 8000:8000 \
  llm_backend
```

The `--add-host` flag is needed on Linux so the container can resolve
`host.docker.internal` and reach the SGLang server running on the host.

## Production Compose

`deploy/docker-compose.prod.yaml` defines two services:

- `sglang`: starts `Qwen/Qwen2.5-1.5B-Instruct` on port `30000`
- `api`: starts this FastAPI backend on port `8000` inside an external `edge`
  Docker network

The compose file expects these environment variables:

```bash
HF_TOKEN=...
LLM_BACKEND_IMAGE=...
IMAGE_TAG=...
```

It also expects the external Docker network to exist:

```bash
docker network create edge
```

Start it with:

```bash
docker compose -f deploy/docker-compose.prod.yaml up -d
```

## Manual Model Switch On The VM

The model must match in both places:

- `deploy/docker-compose.prod.yaml`, in the `sglang` `--model-path` command
- `src/config/llm.py`, in the `MODEL` constant

After changing the model and redeploying, SGLang downloads model files into the
VM user's Hugging Face cache:

```text
~/.cache/huggingface
```

If a larger model runs the VM out of disk space, stop `sglang` and remove the
failed or old model cache before retrying:

```bash
export LLM_BACKEND_IMAGE=dummy
export IMAGE_TAG=dummy
export HF_TOKEN=dummy

docker compose -f "$HOME/llm_backend/docker-compose.prod.yaml" stop sglang

rm -rf "$HOME/.cache/huggingface/hub/models--Qwen--Qwen3-8B"
rm -rf "$HOME/.cache/huggingface/hub/.locks/models--Qwen--Qwen3-8B"

df -h /
du -sh "$HOME/.cache/huggingface" 2>/dev/null || true
```

Recommended fallback order for the current L4 VM:

```text
Qwen/Qwen3-8B
Qwen/Qwen2.5-7B-Instruct
Qwen/Qwen2.5-3B-Instruct
```

`Qwen/Qwen3-8B` is the preferred larger trial. If it fails because there is no
space left on the VM, use `Qwen/Qwen2.5-7B-Instruct`. If that also does not fit,
use `Qwen/Qwen2.5-3B-Instruct`.

Useful checks while retrying:

```bash
df -h /
du -sh "$HOME/.cache/huggingface" 2>/dev/null || true
docker logs -f sglang
nvidia-smi
```

If the VM needs NVIDIA drivers installed or repaired manually, use Ubuntu's
server documentation:

- [Install NVIDIA drivers on Ubuntu Server](https://ubuntu.com/server/docs/how-to/graphics/install-nvidia-drivers/)

## Deployment Path And Takedown

The GitHub Actions deploy workflow supports a `DEPLOY_PATH` repository variable,
but we currently do not set that variable on GitHub. Because of that, the
workflow deploys to its default path:

```text
./llm_backend
```

This path is relative to the SSH user's login directory on the VM. For example,
if the deploy user logs in to `/home/deploy`, the compose file is written to:

```text
/home/deploy/llm_backend/docker-compose.prod.yaml
```

The stack currently has no authentication or rate limiting in front of GPU use.
For now, the safest operating model is to deploy shortly before the event and
take the stack down again afterwards.

To stop and remove both the GPU model server and API containers on the VM:

```bash
export LLM_BACKEND_IMAGE=dummy
export IMAGE_TAG=dummy
export HF_TOKEN=dummy

docker compose -f ./llm_backend/docker-compose.prod.yaml down
```

This removes the running containers, so the `restart: always` and
`restart: unless-stopped` policies do not bring them back. It does not delete
pulled images or the Hugging Face model cache.

If you only want to free the GPU while leaving the API container running, stop
and remove only `sglang`:

```bash
export LLM_BACKEND_IMAGE=dummy
export IMAGE_TAG=dummy
export HF_TOKEN=dummy

docker compose -f ./llm_backend/docker-compose.prod.yaml stop sglang
docker compose -f ./llm_backend/docker-compose.prod.yaml rm -f sglang
```

## API Examples

Check service health:

```bash
curl http://127.0.0.1:8000/healthz
```

Expected response:

```json
{
  "status": "ok"
}
```

Send a chat message:

```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"userMessage":"Explain FastAPI in one sentence."}'
```

Response shape:

```json
{
  "llm_answer": "..."
}
```

## Development Notes

There is no test suite in the repository yet. For a quick smoke test, start the
API and call `/healthz`. To test `/chat`, make sure the SGLang server is running
and reachable at port `30000`.

If `/chat` fails with a connection error, verify:

- SGLang is running.
- The SGLang server is listening on port `30000`.
- Docker containers can resolve `host.docker.internal`.
- The model name configured in `src/clients/llm/llm_client.py` matches the model
  served by SGLang.
