# product-reviews-analysis

Product review analysis using a small open-source language model that runs locally.

## What it does

Upload a CSV of customer reviews for one product and get a breakdown of how customers feel about each part of it.

1. **Upload** a CSV with a `text` column (up to 100 reviews, 2 MB).
2. **Extract**: the model reads a sample of reviews plus frequent phrases (n-grams) and suggests the product name and the aspects people talk about, such as "battery life" or "price".
3. **Review**: edit or confirm the product name and aspects.
4. **Analyze**: each review is scored from 1 to 5 on every aspect it mentions.
5. **Results**: see per-aspect scores in charts and export them as CSV.

Sessions expire automatically after a few hours.

## Tech stack

- **Model**: Qwen3.5-2B (GGUF, Q4_K_M) served by [llama.cpp](https://github.com/ggml-org/llama.cpp) on CPU through its OpenAI-compatible API
- **Backend**: Python 3.14, FastAPI, SQLAlchemy + SQLite, Alembic, Pydantic, OpenAI SDK (structured outputs), SlowAPI (rate limiting), Langfuse (optional tracing)
- **Frontend**: React 19, TypeScript, Vite, Recharts, served by nginx
- **Deployment**: Docker Compose, with Caddy for HTTPS in production

## Run it

```bash
cp .env.example .env
docker compose up -d --build
```

Open <http://localhost>. On the first start, llama.cpp downloads the model, which takes a few minutes.

For production behind Caddy:

```bash
cp Caddyfile.example Caddyfile   # set your domain
docker compose -f compose.yml -f compose.prod.yml up -d --build
```

## License

See [LICENSE](LICENSE).
