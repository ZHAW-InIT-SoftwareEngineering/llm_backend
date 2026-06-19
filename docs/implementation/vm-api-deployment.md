# VM API Deployment

Goal: move from a locally working Dockerized FastAPI app to a reachable API on a VM.

## 1. Direct Smoke Test

Use this first to prove the container works on the VM:

```bash
docker build -f src/Dockerfile -t llm_backend .
docker run -d --name llm_backend --restart unless-stopped -p 8000:8000 llm_backend
```

Make sure the VM firewall or cloud security group allows inbound TCP `8000`.

Verify from outside the VM:

```bash
curl http://<vm-public-ip>:8000/healthz
```

The app inside the container must bind to `0.0.0.0`, not only `127.0.0.1`:

```dockerfile
CMD ["uv", "run", "fastapi", "run", "src/main.py", "--host", "0.0.0.0", "--port", "8000"]
```

## 2. Public Production Shape

Do not keep port `8000` publicly exposed long term.

Use a reverse proxy such as Caddy or Nginx:

```text
internet -> VM:443 -> reverse proxy -> API container:8000
```

Run the API bound only to the VM localhost interface:

```bash
docker run -d \
  --name llm_backend \
  --restart unless-stopped \
  -p 127.0.0.1:8000:8000 \
  llm_backend
```

Then configure the reverse proxy:

```text
https://api.example.com -> http://127.0.0.1:8000
```

Only ports `80` and `443` should be open to the public internet.

## Notes

- `Dockerfile` can document the container port with `EXPOSE 8000`, but it does not publish the port.
- Port publishing belongs to `docker run -p ...` or Compose `ports:`.
- `8000:8000` means `host_port:container_port`; the two numbers are the same only by convention.
