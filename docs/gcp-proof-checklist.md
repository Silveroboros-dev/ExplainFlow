# ExplainFlow GCP Proof Checklist

Use this checklist to capture a short proof clip (or screenshots) showing that ExplainFlow is deployed and running on Google Cloud.

## Goal

Provide clear evidence for judges that:
1. The backend is deployed on Google Cloud.
2. The app executes real generation requests.
3. Generated artifacts are stored on Google Cloud.

## Recommended Proof Format

- 60 to 120 second recording.
- One continuous take preferred.
- Keep project ID, service name, and timestamps visible where possible.

## Pre-Recording Setup

1. Sign in to the correct Google Cloud project.
2. Open these tabs in advance:
   - Cloud Run service page
   - Cloud Run logs
   - Cloud Storage bucket
   - ExplainFlow UI or API client
3. Prepare one stable test input and expected output flow.
4. Clear old logs filter so new entries are easy to spot.

## Proof Steps (In Order)

### 1) Show Cloud Run Service

On screen:
- Cloud Run service name (ExplainFlow API).
- Region.
- URL.
- Latest revision and status.

Narration hint:
- "This is the deployed ExplainFlow backend on Cloud Run."

### 2) Trigger a Real Request

On screen:
- Run a real generation request from UI (or API call).
- Show request started timestamp.

Narration hint:
- "I am triggering a live generate flow now."

### 3) Show Cloud Run Logs

On screen:
- Fresh log lines from the same request:
  - request received
  - extraction/planning started
  - streaming events emitted
  - request completed

Narration hint:
- "These logs confirm the run executed on Cloud Run."

### 4) Show Cloud Storage Artifacts

On screen:
- Bucket path for run output.
- New files for scene assets (images/audio) and optional manifest.
- Updated timestamps matching request window.

Narration hint:
- "Generated media assets are persisted to Cloud Storage."

### 5) Optional: Show Final Bundle Endpoint

On screen:
- `GET /final-bundle/{run_id}` response in UI or API output.

Narration hint:
- "Final output bundle is retrievable via API."

## Minimum Evidence Checklist

Mark complete when all are captured:

- [ ] Cloud Run service page with active deployment.
- [ ] Real request execution shown.
- [ ] Matching Cloud Run logs for that request.
- [ ] Cloud Storage artifacts from the same run.
- [ ] Consistent project/service identity across all views.

## Nice-to-Have Evidence

- [ ] Show SSE stream events arriving in UI.
- [ ] Show scene-level regenerate request + logs.
- [ ] Show one traceability panel (`claim_refs` to scene output).

## Common Failure Points To Avoid

1. Showing only local app screens without Cloud Console proof.
2. Showing old logs not linked to current run.
3. Missing timestamps or run IDs that connect screens.
4. Cutting too quickly before artifacts appear in Storage.
5. Using different projects accidentally across tabs.

## Fast Backup Plan (If Live Run Fails)

1. Show latest successful Cloud Run logs from a recent run.
2. Show matching assets in Cloud Storage.
3. State clearly that this is a previously executed successful run.

## Submission Note Template

Use a short line in README or submission form:

"ExplainFlow backend is deployed on Google Cloud Run, and generated scene assets are stored in Google Cloud Storage. Proof recording included."
