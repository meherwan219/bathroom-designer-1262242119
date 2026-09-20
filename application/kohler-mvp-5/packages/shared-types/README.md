# shared-types

Optional TS types generated from the FastAPI OpenAPI schema.

Once the API is running:

```
npx openapi-typescript http://localhost:8000/api/v1/openapi.json -o index.ts
```

Not wired into the web app in Phase 0 — `lib/api.ts` uses `unknown`/inline
types for now to avoid a build-order dependency during the hackathon.
