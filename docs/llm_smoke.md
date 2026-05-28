# Live LLM Smoke Commands

These commands use `.env` as the only config source for provider URL, key, model, timeout, retry, and concurrency.

## Required env keys

- `SHOPAIKEY_BASE_URL`
- `SHOPAIKEY_API_KEY`
- `SHOPAIKEY_MODEL`
- `LLM_TEMPERATURE`
- `LLM_MAX_TOKENS`
- `LLM_TIMEOUT_SECONDS`
- `LLM_MAX_RETRIES`
- `LLM_RETRY_BASE_DELAY_SECONDS`
- `LLM_RETRY_MAX_DELAY_SECONDS`
- `LLM_MAX_CONCURRENCY`

## Sync smoke

```bash
python scripts/smoke_test_llm_connectivity.py --dotenv .env
```

## Async smoke

```bash
python scripts/smoke_test_llm_api_throughput.py --dotenv .env --count 3
```

## Reporting rule

- If credentials/provider are unavailable, report smoke as `BLOCKED`.
- Do not print raw secrets in logs or reports.
- Keep prompts runtime-safe and tiny.

