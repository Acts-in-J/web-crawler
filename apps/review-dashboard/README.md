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

## Multi-User Identity & Authorization Foundation (A5-A3-A3 / FIX1)

### Identity vs. Authorization Separation
* **Identity != Authorization**: The existence of a valid user identity (`activeEmail` / `stableIdentity`) does not automatically grant write permissions. Identity answers *who* is requesting; Authorization evaluates *whether* that identity is permitted to write.
* **Session Identity Resolver (`resolveRequestIdentity`)**:
  * `activeEmail`: Resolved via `Session.getActiveUser().getEmail()`, trimmed and lowercased. May be empty (`""`) under certain Apps Script deployment modes or unauthenticated access.
  * `effectiveEmail`: Resolved via `Session.getEffectiveUser().getEmail()`. Represents script execution authority (deployer/owner). **MUST NOT** be interpreted as the visiting user's identity when `executeAs = USER_DEPLOYING`.
  * `temporaryUserKey`: Resolved via `Session.getTemporaryActiveUserKey()`. Represents a temporary session correlation ID. **MUST NOT** be promoted to a permanent identity or used as an authorization credential by itself.
  * `stableIdentity`: Contains `activeEmail` if non-empty, otherwise remains empty (`""`). Never substitutes `effectiveEmail` or `temporaryUserKey`.
  * `authenticated`: `true` only when `stableIdentity` is non-empty.

### Strict Fail-Closed Authorization (`authorizeReviewImport`)
* **Mandatory Allowlist**: `REVIEW_DASHBOARD_ALLOWED_USERS` ScriptProperty is mandatory for write authorization. If missing, null, blank, or if property lookup fails, all write requests fail closed (`WRITE = DENY`).
* **No Implicit Deployer Bootstrap**: `effectiveEmail` and equality check (`activeEmail === effectiveEmail`) are **NEVER** used as implicit authorization credentials. There is no implicit owner/deployer bypass.
* **Server-Authoritative `imported_by`**: `imported_by` is set exclusively on the server to `identity.stableIdentity`. Any client-submitted `imported_by` in payload is strictly ignored to prevent client forgery.
* **Fail-Closed Write Policy**: Write operations (`importReviewData`) mandate server-side authorization before acquiring script locks or mutating sheet headers/rows.

### Spreadsheet Boundary Hardening (FIX2)
* **Server-Controlled Target**: Browser-facing public functions (`getReviewDashboardData()` and `importReviewData(rawItems, importFilename)`) do **NOT** accept arbitrary `spreadsheetIdOverride` parameters. Target selection is strictly controlled on the server via `DEFAULT_SPREADSHEET_ID`.
* **Private Server Helpers**: Internal implementations (`getReviewDashboardData_` and `importReviewData_`) use the `_` suffix convention in Apps Script to prevent client invocation via `google.script.run`.
* **Production Deployment**: Production Version 3 remains unchanged. Production deployment settings remain `executeAs: USER_DEPLOYING` and `access: MYSELF`.

---

## Multi-User Concurrency & Runtime Access Verification Model (A5-A3-A4 / FIX1)

### Candidate Runtime Binding Gate (Mandatory Prerequisite)
Before any multi-user runtime testing begins, the candidate runtime binding MUST be explicitly verified:
1. **Candidate Git Commit**: Identify the exact candidate Git commit being tested.
2. **Apps Script Source Binding**: Confirm the Apps Script source code matching that exact candidate commit.
3. **Target Deployment & Version**: Confirm the exact deployment ID and version serving the candidate code.
4. **Non-Production Isolation**: Verify that the target candidate deployment is NOT the Production deployment (`AKfycbxtwQefoMI0C_rsOD_F5XPncnuv8Og2epL37zF1OA63bn51UmEBuHF7FhegDhsoRjxQ`).
5. **Production Safeguard**: Production Deployment remains Version 3 untouched.
6. **Execution/Access Record**: Record the exact `executeAs` / `access` configuration used for the test deployment.
7. **Gate Requirement**: Multi-user testing MUST NOT begin until candidate-code ↔ deployment binding is proven. If candidate runtime binding cannot be proven: **STATUS: HOLD**.

*Important Safeguards*:
* Existing Temp `@3` MUST NOT be assumed to contain A5-A3-A3 authorization code merely because it is labeled as the Temp Runtime Deployment.
* If Temp `@3` is stale, the next Runtime Slice must prepare a separate candidate runtime deployment/version or another explicitly verified target.
* Production Version 3 MUST remain untouched.
* `@HEAD` deployment may only be used if its candidate-code identity and required access/execute-as semantics are explicitly verified first.
* Do NOT infer runtime identity behavior from deployment labels alone.

### 1. Deterministic Runtime Identity & Authorization Matrix

| Case | ActiveUser Email | EffectiveUser Email | Allowlist State | Expected Authorization | Reason / Policy Rule |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **A** | Available (`userA@co.com`) | Available | `userA@co.com` included | `WRITE = ALLOW` | User explicitly allowlisted |
| **B** | Available (`userC@co.com`) | Available | `userA@co.com` (not userC) | `WRITE = DENY` | User absent from allowlist |
| **C** | Empty (`""`) | Available | Any | `WRITE = DENY` | No stable identity (TempKey ignored) |
| **D** | Empty (`""`) | Empty (`""`) | Any | `WRITE = DENY` | Unauthenticated session |
| **E** | Available (`userA@co.com`) | Available | Missing (Unconfigured) | `WRITE = DENY` | Fail-closed: allowlist property missing |
| **F** | Available (`userA@co.com`) | Available | Blank (`""`) | `WRITE = DENY` | Fail-closed: allowlist property blank |
| **G** | Available (`userA@co.com`) | Available | Exception / Property error | `WRITE = DENY` | Fail-closed: ScriptProperty read failure |
| **H** | ActiveUser == EffectiveUser | Same | Missing / Unconfigured | `WRITE = DENY` | Deployer bootstrap removed; allowlist required |

### 2. Multi-User Concurrency Scenarios

* **Scenario 1: Concurrent Non-Overlapping Imports (User A & User B)**
  * *Execution*: Executed sequentially via `LockService.getScriptLock().tryLock(10000)`.
  * *Verification*: Both batches complete cleanly. `import_batch_id` is unique per batch UUID. `imported_by` accurately reflects User A for Batch A rows and User B for Batch B rows. `imported_at` records server execution timestamps.
* **Scenario 2: Concurrent Overlapping Imports (User A & User B)**
  * *Execution*: LockService sequences the requests. User A inserts Batch A. User B's execution re-reads updated sheet data, computes existing collision-safe dedup keys (`makeReviewDedupKey`), skips duplicate reviews, and appends only new unique reviews.
  * *Verification*: Zero duplicate rows inserted. Dedup is strictly deterministic across concurrent executions.
* **Scenario 3: Concurrent Authorized & Unauthorized Requests**
  * *Execution*: Unauthorized request calls `authorizeReviewImport()` BEFORE `LockService.getScriptLock()`. Immediately fails closed with error status. Does not acquire lock, open sheet, or mutate data.
  * *Verification*: Authorized request proceeds unaffected. Unauthorized request causes 0 side effects.
* **Scenario 4: Concurrent Dashboard Read/Preview during Active Import**
  * *Execution*: Read requests (`getReviewDashboardData_`) operate independently of the script write lock.
  * *Verification*: Dashboard read remains accessible and consistent; client preview modal is non-writing and unaffected by concurrent server lock holding.

### 3. LockService & Security Boundary Inspection Findings
* **Authorization Before Lock**: `authorizeReviewImport(identity)` is evaluated BEFORE `LockService.getScriptLock()`. Unauthorized requests are rejected fast without lock acquisition overhead.
* **Lock Scope**: The script lock covers sheet reading, header migration, collision-safe key set construction, and batch row appending.
* **Lock Timeout**: 10,000 ms (10 seconds) timeout.
* **Spreadsheet Control**: Public entry points (`getReviewDashboardData`, `importReviewData`) take no `spreadsheetIdOverride` from the browser, enforcing server-controlled canonical targets.

### 4. Temp Runtime Verification Procedure (Pre-Production Rollout Gate)
Runtime verification MUST follow this exact precondition order:

0. **Candidate Runtime Binding Verification**: Prove candidate Git commit ↔ Apps Script source ↔ candidate deployment binding. If unproven -> **HOLD**.
1. **Verify Candidate Deployment Access Model**: Verify execute-as / access configuration on candidate deployment.
2. **Configure Test Allowlist**: Set `REVIEW_DASHBOARD_ALLOWED_USERS` on candidate deployment script properties (e.g., `userA@domain.com, userB@domain.com`).
3. **Establish Isolated User Sessions**: Open User A in Profile 1, User B in Profile 2/Incognito, and User C in an unauthenticated/unallowlisted session.
4. **Verify Observed Identity Signals**: Confirm `stableIdentity` resolution for active sessions.
5. **Execute Non-Overlapping Concurrency Test**: Trigger simultaneous imports from User A and User B with distinct review sets.
6. **Execute Overlapping Concurrency/Dedup Test**: Trigger simultaneous imports with overlapping review IDs and verify deterministic dedup.
7. **Verify Unauthorized Concurrent Request Isolation**: Verify User C request receives fast-fail error and appends 0 rows.
8. **Verify Provenance**: Inspect `01_REVIEW_RAW` to confirm `import_batch_id`, `import_filename`, `imported_by`, and `imported_at`.
9. **Cleanup Test Rows**: Remove test rows from `01_REVIEW_RAW`.
10. **Return Evidence**: Output exact PASS/HOLD report with observed evidence.

### 5. Production Promotion Gate
Production access (`executeAs: USER_DEPLOYING`, `access: MYSELF`, Version 3) MUST NOT be modified during this Slice. Any future reconsideration requires complete PASS of the Candidate Runtime Binding Gate and the 10-step Temp Runtime Verification procedure.
