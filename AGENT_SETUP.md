# AutoBasket Agent — Setup & Run Notes

## What this is

LangGraph-style ReAct agent (app/agent/orchestrator.py) wrapping 10 pantry tools (app/agent/tools.py), exposed via /agent/chat (app/routes/agent.py).
Order placement above ₹50 requires an explicit user confirmation before stock is replenished (the guardrail).

## Run it

```bash
# 1. Start Ollama with the agent model
ollama serve
ollama pull lfm2.5:8b-toolfix   # or set OLLAMA_MODEL to lfm2.5:8b
export OLLAMA_MODEL=lfm2.5:8b-toolfix

# 2. Start the API
uvicorn app.main:app --reload

# 3. Log in (dev mode echoes the code) and hit the endpoint
curl -X POST localhost:8000/auth/request-otp -H "Content-Type: application/json" -d '{"email":"you@example.com"}'
# -> {"dev_code":"123456"}
curl -X POST localhost:8000/auth/verify-otp -H "Content-Type: application/json" -d '{"email":"you@example.com","code":"123456"}'
# -> {"access_token":"...", ...}
curl -X POST localhost:8000/seed/dev -H "Authorization: Bearer <access_token>"
curl -X POST localhost:8000/agent/chat \
  -H "Content-Type: application/json" -H "Authorization: Bearer <access_token>" \
  -d '{"message": "order rice from Local Kirana", "session_id": "demo"}'
```

Chat memory is keyed per household, so two households never share a conversation even with the same `session_id`.

If Ollama is not reachable, the agent falls back to regex-based heuristic routing (run_heuristic_agent) — same tools, same guardrail, weaker language understanding. This is sufficient for demos and tests.

## Guardrail behavior

- Orders above the ₹50 auto-approve threshold create a pending confirmation instead of replenishing stock immediately.
- A follow-up confirmation message completes the order and replenishes stock.
- A cancellation message drops the pending order and leaves stock untouched.

## Testing

```bash
pytest backend/tests/test_agent_guardrail.py backend/tests/test_agent_smoke.py -v
```

## Notes

- The smoke test mounts only the agent router (app/routes/agent.py) so it stays fast and independent of the other routes.
