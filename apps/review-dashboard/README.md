# Syncrown Review Intelligence Dashboard — Provenance & Access Specification

## 01_REVIEW_RAW Provenance Contract (A5-A3-A2)

### Schema & Header Column Order
`01_REVIEW_RAW` Google Sheet contains 14 canonical review data columns, followed by 4 optional provenance extension columns:

1. `crawl_id` (Canonical)
2. `source_domain` (Canonical)
3. `product_id` (Canonical)
4. `product_name` (Canonical)
5. `brand` (Canonical)
6. `review_id` (Canonical)
7. `review_date` (Canonical)
8. `rating` (Canonical)
9. `review_text` (Canonical)
10. `product_option` (Canonical)
11. `helpful_count` (Canonical)
12. `photo_review` (Canonical)
13. `video_review` (Canonical)
14. `collected_at` (Canonical)
15. `import_batch_id` (Optional Provenance)
16. `import_filename` (Optional Provenance)
17. `imported_by` (Optional Provenance)
18. `imported_at` (Optional Provenance)

### Key Semantics & Rules
* **Optional Extensions**: Provenance columns are optional extensions. Existing core review queries and Python crawler exports remain valid with or without these columns.
* **Server-Authoritative Batch Metadata**:
  * `import_batch_id`: Generated on the Apps Script server (`Utilities.getUuid()`) at import execution time.
  * `imported_at`: Generated on the Apps Script server (`new Date().toISOString()`) at import execution time.
  * All rows inserted within a single import execution share identical `import_batch_id` and `imported_at` values.
* **Client-Provided Filename**: `import_filename` originates from the original uploaded XLSX file name passed upon confirmed import.
* **Crawler Data Compatibility**: Crawler-generated rows from `export_reviews_to_gsheets` leave import provenance fields blank (`""`).
* **No Provenance Backfill**: Duplicate detection checks (`source_domain` + `product_id` + `review_id`) skip already existing rows. Existing rows are not modified or backfilled with new provenance upon re-upload.
* **Deferred Features**: `source_file_hash` is explicitly deferred.

---

## Multi-User Identity & Authorization Foundation (A5-A3-A3)

### Identity vs. Authorization Separation
* **Identity != Authorization**: The existence of a valid user identity (`activeEmail` / `stableIdentity`) does not automatically grant write permissions. Identity answers *who* is requesting; Authorization evaluates *whether* that identity is permitted to write.
* **Session Identity Resolver (`resolveRequestIdentity`)**:
  * `activeEmail`: Resolved via `Session.getActiveUser().getEmail()`, trimmed and lowercased. May be empty (`""`) under certain Apps Script deployment modes or unauthenticated access.
  * `effectiveEmail`: Resolved via `Session.getEffectiveUser().getEmail()`. Represents script execution authority (deployer/owner). **MUST NOT** be interpreted as the visiting user's identity when `executeAs = USER_DEPLOYING`.
  * `temporaryUserKey`: Resolved via `Session.getTemporaryActiveUserKey()`. Represents a temporary session correlation ID. **MUST NOT** be promoted to a permanent identity or used as an authorization credential by itself.
  * `stableIdentity`: Contains `activeEmail` if non-empty, otherwise remains empty (`""`). Never substitutes `effectiveEmail` or `temporaryUserKey`.
  * `authenticated`: `true` only when `stableIdentity` is non-empty.

### Server-Side Fail-Closed Authorization (`authorizeReviewImport`)
* **Server-Authoritative `imported_by`**: `imported_by` is set exclusively on the server to `identity.stableIdentity`. Any client-submitted `imported_by` in payload is strictly ignored to prevent client forgery.
* **Fail-Closed Write Policy**: Write operations (`importReviewData`) mandate server-side authorization before acquiring script locks or mutating sheet headers/rows.
* **Allowlist Property (`REVIEW_DASHBOARD_ALLOWED_USERS`)**:
  * Storage: Apps Script `ScriptProperties` under key `REVIEW_DASHBOARD_ALLOWED_USERS`.
  * Format: Comma-separated normalized emails (e.g. `user1@syncrown.com, user2@syncrown.com`).
  * If configured: Only emails explicitly listed in `REVIEW_DASHBOARD_ALLOWED_USERS` receive `WRITE = ALLOW`. All others receive `WRITE = DENY`.
  * If unconfigured (Bootstrap Mode): Single-operator deployment (`access: MYSELF`, `executeAs: USER_DEPLOYING`) allows the deployer/operator (`stableIdentity === effectiveEmail`) to continue functioning without manual property setup. Access by any other Google user or unauthenticated session is rejected (`WRITE = DENY`).
* **Deployment & Production Safeguard**: Production deployment settings remain unchanged (`executeAs: USER_DEPLOYING`, `access: MYSELF`) in A5-A3-A3. No Apps Script manifest changes or OAuth scope additions are introduced.
