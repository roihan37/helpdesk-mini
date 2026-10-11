# B7 — Attachment Verification

Status (2026-10-12): **automated local/API and mocked-S3 verification PASS;
browser, Docker, and real AWS verification NOT RUN**.
The previous implementation-only deferral is superseded by this audit.

## Executed evidence

- `backend/tests/test_chat_bonuses.py`: actual FastAPI JPEG/PNG/WebP upload and protected download,
  persistent message/attachment associations and WebSocket metadata, private temporary local
  files, Admin/closed/cross-business/cross-customer denial, invalid/expired/refresh JWT rejection,
  malformed/SVG/MIME mismatch/oversized rejection with no persisted message or object.
- `backend/tests/test_attachment_storage.py` (**28 tests**): canonical image validation,
  trailing-data removal, private local permissions/exclusive writes/path and symlink protection,
  bounded mocked-S3 retrieval and stream cleanup, private conditional writes, storage failure,
  definite failed-commit cleanup, and ambiguous-commit object retention. AWS clients are mocked;
  no real AWS service or credential was used.
- Stale-role delivery regressions cover attachment events and shared authenticated room cleanup.
  Shared targeted suite: **84 PASS, 0 FAIL**; full backend: **285 PASS, 0 FAIL**.
- Fresh Alembic head upgrade on `helpdesk_bonuses_test`: PASS. Frontend tests **26 PASS, 0 FAIL**;
  typecheck, ESLint, production build: PASS. Domain deduplication coverage includes attachments,
  but actual chooser/preview/download rendering is not browser-tested here.
- Redacted tracked-file scan: no tracked actual `.env`, upload/generated files, recognizable AWS
  key/private-key/JWT candidates. Template DB/JWT values reviewed as local placeholders; AWS
  credential fields empty. This limited current-tree scan is not a complete history/secret audit.
- Exact commands and environment are recorded in the active M7 plan, section 13.

## Still NOT RUN / supplementary checklist

Docker test execution was attempted but the daemon was unavailable. Real browser uploads,
visibility-based read acknowledgement, deployment IAM/private-bucket validation, populated
migration/backfill and downgrade/re-upgrade, large-image/load measurements, and full historical
secret scanning remain unverified. The checklist below is supplementary, not fully executed.

## Preconditions

Use a disposable PostgreSQL database, isolated local upload directory/private S3
prefix, and two businesses with Admin, Agent, and multiple Customers. Never reset
valuable data or use production AWS credentials/buckets. Preserve existing seed
data. Apply the migration only in the approved verification phase. Inspect existing
repository scripts before choosing test commands; do not invent unavailable scripts.

## Required backend and migration scenarios

- Apply the new migration on a fresh disposable database, inspect foreign key,
  unique key/message constraints, MIME/provider/size/dimension checks, downgrade
  and re-upgrade only that disposable database; verify historical text messages.
- Accept JPEG/PNG/WebP with optional/empty caption; confirm canonical metadata,
  UUID keys, hashed/authenticated user identity, and message/attachment relationships.
- Reject zero-byte, malformed, animated, unsupported, MIME-spoofed, over-5-MiB,
  oversized-dimension/pixel, traversal filename, and canonical-output overflow
  cases. Confirm EXIF/other metadata and appended content are removed.
- Reject unauthenticated, expired, refresh-token, cross-business, and other-Customer
  uploads/downloads. Reject Admin uploads and closed-ticket uploads, including
  concurrent closure; permit authorized Admin viewing. Reject attachment ID/ticket
  mismatches without revealing storage identifiers or private bytes.
- Confirm atomic message/metadata persistence, latest activity, unread counts,
  sender-excluded counts, read receipts, history, pagination/search/filter behavior.
- Exercise local write/read/delete failures and S3 denied permissions/timeouts;
  assert generic errors, no sensitive logging, cleanup on definite rollback and
  retention/reconciliation on ambiguous commit. No false success events.
- Check single-worker room/list events only after commits, per-ticket/tenant
  isolation, authentication revalidation, and unchanged text/typing/status events.
- Verify S3 objects remain private, IAM/credential-chain access, safe configured
  prefix, provider-specific historical reads, bounded retrieval, and no public URL.

## Required browser and Docker scenarios

- Two independent authorized sessions: choose image, preview/remove, caption,
  upload loading/progress, receive without refresh, and reload persistent history.
  HTTP/event races must render one message. Own uploads must not increment own unread.
- Test invalid-file feedback, network/storage errors, retries, duplicate-send
  prevention, aborted/ambiguous upload recovery via history, expired-token refresh,
  reconnect, navigation, logout, and changing users without leaked Blob/image cache.
- Confirm mark-read only after successful visible image loading; hidden tabs,
  failed/slow images, scrolling, read receipts, and concurrent uploads/read cursors.
- Review keyboard file chooser/remove/enlarge/close, dialog focus/Escape, image alt,
  accessible progress/errors, long filenames, large aspect ratios, mobile/tablet
  composer and conversation bounds, and no layout clipping.
- On an isolated Docker demo, run the existing one-command startup in the approved
  phase; confirm migrations, local upload persistence after restart/recreation,
  unchanged 2-business/8-user seed, API/CORS/cookies/chat, and optional test-profile
  database isolation. Do not delete existing Docker volumes.
- Confirm `.uploads` excluded from Git/Docker contexts; no real AWS keys or tokens
  in tracked files, responses, browser storage, URLs, or logs.

## Final quality/regression evidence to record

Record exact executed commands and PASS/FAIL/NOT RUN separately for backend import,
attachment/security tests, existing auth/ticket/WebSocket/unread/presence regressions,
frontend tests/typecheck/lint/build, migration, real browser E2E, Docker, and S3.
Mock-only checks cannot prove private S3 or browser integration. Record defects,
fixes, reruns, and any remaining release blockers; do not mark B7 verified before
this evidence exists.

## Known limitations to validate/document

Single-process best-effort broadcast; no distributed DB/object transaction or
automatic orphan GC; no upload quotas/malware scanner/upstream body limit; no upload
idempotency key; conservative read tracking when images fail; unpaginated image
history memory usage; local root/S3 bucket changes require object migration.
