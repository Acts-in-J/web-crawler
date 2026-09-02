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
17. `imported_by` (Optional Provenance — Reserved)
18. `imported_at` (Optional Provenance)

### Key Semantics & Rules
* **Optional Extensions**: Provenance columns are optional extensions. Existing core review queries and Python crawler exports remain valid with or without these columns.
* **Server-Authoritative Batch Metadata**:
  * `import_batch_id`: Generated on the Apps Script server (`Utilities.getUuid()`) at import execution time.
  * `imported_at`: Generated on the Apps Script server (`new Date().toISOString()`) at import execution time.
  * All rows inserted within a single import execution share identical `import_batch_id` and `imported_at` values.
* **Client-Provided Filename**: `import_filename` originates from the original uploaded XLSX file name passed upon confirmed import.
* **Reserved Field**: `imported_by` is reserved until A5-A3-A3 (Multi-User Identity & Authorization Foundation) and remains blank (`""`) in A5-A3-A2.
* **Crawler Data Compatibility**: Crawler-generated rows from `export_reviews_to_gsheets` leave import provenance fields blank (`""`).
* **No Provenance Backfill**: Duplicate detection checks (`source_domain` + `product_id` + `review_id`) skip already existing rows. Existing rows are not modified or backfilled with new provenance upon re-upload.
* **Deferred Features**: `source_file_hash` is explicitly deferred.
