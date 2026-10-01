# Station #9 hosted runtime evidence

The contract tests execute workflow Bash against controlled local boundaries.
They do not prove GitHub OIDC issuance, artifact upload, public transport
visibility, or GitHub's real rerun semantics. Collect the following hosted
evidence separately. Only the remote Delivery agent may modify repository
content. A local Codex helper may run tests and save local evidence, but must
not edit, commit, push, create PRs, change settings, or mutate historical tags.

## Existing canonical workflow recovery probe (before commit)

Use the authenticated `gh` account authorized for `taco3064/shoal-station`.
Run in a disposable evidence directory, outside any repository worktree.
Never place tokens in commands, files, or reports.

1. Record `main` commit and exact managed-file SHA-256 from committed bytes.
2. Dispatch `.github/workflows/reviewer-summary.yml` on `main`:
   `gh workflow run reviewer-summary.yml -R taco3064/shoal-station --ref main`.
   Identify the newly created run by time, actor, branch, and head SHA, not
   merely the first list entry. Record its run ID as `RUN_ID`.
3. Wait for success using `gh run watch "$RUN_ID" -R taco3064/shoal-station
   --exit-status`. Record successful attempt A and the attempt-specific jobs.
4. Download artifact `reviewer-summary-$RUN_ID-$ATTEMPT` into a fresh directory.
   Retrieve its transport anonymously with `curl` (no authorization header):
   `https://raw.githubusercontent.com/taco3064/shoal-station/shoal-summary-1379044983-$RUN_ID-$ATTEMPT/reviewer-summary.json`.
   Compare bytes and SHA-256. Record tag target, root transport commit/tree,
   archive artifact ID, attestation ID from attempt logs, and Summary versions.
5. Verify the archived Summary using `gh attestation verify <summary-path>
   --repo taco3064/shoal-station --signer-workflow
   taco3064/shoal-station/.github/workflows/reviewer-summary.yml --format json`.
   Inspect verified provenance for the exact source commit and run/attempt.
   Public transport alone is not acceptance evidence. Preserve the verification
   output and artifact metadata, including artifact ID and workflow-run head SHA.
6. Perform one full rerun:
   `gh api --method POST repos/taco3064/shoal-station/actions/runs/$RUN_ID/rerun`.
   Wait until `run_attempt` increases, then wait for completion. Record successful
   attempt B, distinct artifact and attestation IDs and transport locator.
   Re-read A anonymously and verify its tag target and bytes are unchanged.
7. Trigger a controlled newer failure by rerunning only B's successful
   **publish** job:
   `gh api --method POST repos/taco3064/shoal-station/actions/jobs/$PUBLISH_JOB_ID/rerun`.
   Read B's job ID from `/actions/runs/$RUN_ID/attempts/$ATTEMPT/jobs` and check
   job name is exactly `publish` before submitting. This should create attempt C
   and fail downloading the C-named artifact, because Summary did not rerun.
   Do not create a fake C artifact or modify historical transport to repair it.
   If GitHub behaves differently, report actual metadata/logs instead of forcing
   the expected result or mutating any object.
8. Verify C is completed and failed; A and B tag targets/bytes remain unchanged;
   C did not produce replacement artifact/attestation/public transport evidence.
   Record attempt-scoped jobs and artifact listing, not just latest run metadata.
9. Perform another **full** rerun with the run-level endpoint from step 6.
   Record successful attempt D, new artifact/attestation identities and locator.
   Verify A and B remain independently retrievable and unchanged.

This probe creates only execution evidence through the existing canonical
workflow. It does not establish downstream acceptance of a new workflow digest.
Do not alter compatibility entries in shoal-app or synchronize any direct fork.

## Candidate hosted probe (after independent acceptance and remote commit)

Once Delivery supplies an accepted commit/branch, dispatch that exact branch,
verify `head_sha` equals the supplied commit, and repeat the byte/provenance and
recovery sequence above. Run this before Shaper handoff. Report all failures to
remote Delivery; the local helper must not fix repository content.

Record for compatibility handoff to shoal-app#23:

- Exact station commit and workflow SHA-256 from `git show COMMIT:path` bytes.
- Official Action full SHA pinned in that workflow.
- Protocol / Summary schema versions from actual Action-produced Summary.
- Successful `workflow_run.id + run_attempt`, Repository ID 1379044983.
- Summary SHA-256, Actions artifact ID, attestation ID and verified provenance.
- Public Transport tag, commit, URL, and anonymous byte comparison.
- Older-success/newer-failure/recovery attempt metadata and unchanged old evidence.

The new digest is an explicit compatibility dependency; do not assume that
Network Root presence grants acceptance or remove approved older identities.
Neither `README.md` nor the Request Form is changed by this delivery.

## Report

Return observed commands, exit codes, exact commits, attempt-scoped URLs and
IDs, digests, verified provenance, and any deviations. Distinguish missing
access, missing credentials, or unsupported APIs from implementation failures.
Do not call a downstream rejected Summary accepted merely because the workflow
succeeded. Downstream selection remains owned by shoal-app.
