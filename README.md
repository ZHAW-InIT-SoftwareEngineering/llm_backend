# llm_backend
This is the code for the backend of the LLM.


run dev with: 
uv run fastapi dev src/main.py

---

if with Docker: 
docker build -f src/Dockerfile -t llm_backend . && docker run --rm -p 8000:8000 llm_backend