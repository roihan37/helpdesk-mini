# B7 — deferred attachment verification

Status: **NOT RUN**. Implementation and static review only; no automated tests
created/modified, tests executed, lint/typecheck/build run, or migration applied.
Dependency lock resolution was executed; it is not runtime verification.

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
