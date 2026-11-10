# Threat model

Assets: stock accuracy, order integrity, customer IDs, database credentials, image supply chain.
Trust boundaries: Internet → API; API/worker → Postgres; CI → registry; Git → cluster (Argo CD).

| # | Threat | Category | Impact | Mitigation |
|---|---|---|---|---|
| T1 | Overselling via concurrent requests (race) | Tampering / integrity | Negative or phantom stock | Conditional `UPDATE ... WHERE available >= q`, CHECK constraint, race tests |
| T2 | Replay or duplicate submission creates duplicate orders | Repudiation / integrity | Double charge, double stock use | Idempotency key PK + `ON CONFLICT`, payload hash comparison |
| T3 | SQL injection via sku/customer_id/key | Injection | Data theft or corruption | Parameterized queries only, strict validation (types, lengths, ASCII), no string-built SQL |
| T4 | Oversized or malformed body (DoS) | Denial of service | API unavailable | 16 KiB body limit, max 10 items, quantity 1–20, safe 4xx codes |
| T5 | Information leak via errors or logs | Information disclosure | Stack traces, SQL, credentials exposed | Uniform `{"error":{code,message}}` with safe messages; no secrets in logs |
| T6 | High-cardinality or PII labels in metrics/logs | Information disclosure / DoS | Customer IDs and keys leaked, Prometheus overload | Labels limited to route/method/status; no customer_id or key |
| T7 | Worker crash or duplicate delivery causes double completion | Integrity | Order completed twice | Lease recovery + guarded `WHERE status <> 'completed'` in same tx as job state |
| T8 | Poison job loops forever | DoS | Worker starvation | `max_attempts`, backoff, dead-letter state |
| T9 | Test reset script run against real data | Tampering | Production stock wiped | Refuses without explicit test flag and a test database name |
| T10 | Secrets committed to Git; vulnerable or tampered images | Supply chain | Credential or code compromise | `.env.example` only, K8s Secret references, CI scan with blocking policy, SBOM, pinned actions and base images |
| T11 | Manual cluster change bypasses review (drift) | Tampering | Unreviewed config in production | Argo CD detects drift and self-heals; humans approve risky changes |

Residual risks (accepted for this coursework): no authentication or rate limiting on the API, a single
Postgres instance with no replication or backup, TLS not terminated locally.