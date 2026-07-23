# Contributing

Thank you for helping improve AutoBasket 2.0.

## Development workflow

1. Fork the repository and create a feature branch.
2. Install dependencies for the backend and frontend.
3. Make focused changes and add or update tests where appropriate.
4. Run the relevant test suite and build checks.
5. Open a pull request with a concise summary of the change.

## Code style

- Keep Python code readable and follow existing project patterns.
- Prefer small, well-scoped changes.
- Include test coverage for behavior changes when possible.

## Testing

```bash
pytest backend/tests -q
cd frontend && npm run build
```
