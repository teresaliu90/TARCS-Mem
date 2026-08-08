# Synthetic Confluence connector contract fixtures

These fixtures define the minimum safe behavior expected from a TARCS-Mem knowledge-source
connector. Every page, ID, path, date and fact is fictional. The payloads contain no captured
customer text, site origin, account, credential or authorization header.

## Covered scenarios

| Fixture or simulated response | Contract |
| --- | --- |
| `initial-page-1.json` followed by `initial-page-2.json` | Follow a same-origin v2 cursor and ingest each page once. The repeated `91001` delivery is deduplicated. |
| Replay of both initial payloads | Stable page/hash/chunk identities produce no duplicate memories or audit ingestion events. |
| HTTP `429` followed by the initial payloads | Honor bounded retry/backoff, then produce the same records as a clean delivery. |
| `same-version-content-change.json` | A content-hash change creates a new projection even if an upstream version number is unexpectedly reused; the prior projection is expired with history retained. |
| `no-visible-pages.json` without confirmation | Report missing IDs and retain them in the checkpoint. A permission loss must not be treated as deletion. |
| `no-visible-pages.json` with `expire_missing=True` | Explicitly expire current projections, append an audit reason and then remove the page from the checkpoint. No memory or audit row is deleted. |
| Ingest failure between deterministic chunks | Do not advance the checkpoint. A retry fills only missing chunks and converges without duplicates. |

The executable contract is in `tests/test_confluence_contract.py`. Run it with:

```bash
pytest -q tests/test_confluence_contract.py
```

## ACL and classification boundary

Confluence list responses do not provide a complete, portable end-user authorization policy.
The connector account's ability to read a page is therefore **not** mapped to permission for every
TARCS-Mem user. The synchronization job must supply a tenant, classification and optional role
allow-list. The fixtures verify that these values reach every chunk.

Imports default to `meeting_note`, authority `0.70`, classification `internal` and human review.
Only a space with an organization-approved publication workflow should be configured as
`official_policy` with authority `1.0`. A real identity gateway must still derive the request
tenant and roles from verified claims.

## Secret, API and source-term boundary

- Keep the site origin, account and API token in runtime configuration or a secret manager. The
  checkpoint and fixture files must never contain them.
- Use a least-privilege read-only connector account and rotate its token independently of the
  checkpoint.
- Use the documented Confluence Cloud API rather than scraping pages. Respect rate limits,
  organization retention rules and the terms that apply to the source content.
- Do not contribute captured responses, customer page text, internal URLs, personal data or paid
  content. Reproduce failures by reducing them to synthetic payloads like these.
