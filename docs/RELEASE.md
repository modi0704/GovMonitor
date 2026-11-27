# Release checklist

For the person who publishes a GovMonitor version. Every step is required.

## Before the first release only

1. Create the vendor licence-signing key on an offline machine and keep it there:
   `python tools/licence.py keygen --out vendor-licence.key`.
2. Put the printed public key in `backend/apps/tenancy/licence_public_key.txt` (replacing the
   placeholder and its comment) and commit it. `make release` and the release workflow refuse to run
   while the placeholder is there (D41).

## Every release

1. All green on the release commit: CI jobs `check`, `smoke`, `image` (backup/restore, cloud
   compose, offline bundle, offline install), and `make audit`. Review any new advisory in
   `docs/SECURITY.md` §12.
2. Set the version in `VERSION` and `frontend/package.json` (semantic versioning; see
   `CHANGELOG.md`), and add the changelog entry, including any manual update step.
3. Re-generate the API reference if routes changed: `cd backend && .venv/bin/python ../tools/api_docs.py`
   (the test suite fails otherwise).
4. Check `docs/THIRD_PARTY.md` against the lockfiles (licence rule, MASTERPLAN 5.2).
5. If `docs/USER_GUIDE.md` or `docs/USER_GUIDE_WITH_SAMPLE_DATA.md` changed, rebuild the PDFs with
   `tools/user_guide_pdf.sh` (needs pandoc and the frontend's Playwright Chromium) and commit
   `docs/user-guide/*.pdf`. If the screens or the scoring changed, redo the practice run in the
   sample-data guide and check that its expected results still match.
6. Commit, then tag and push the tag: `git tag -a v1.0.0 -m "GovMonitor 1.0.0"` and
   `git push origin v1.0.0`. The **release** workflow builds the image `govmonitor:<version>` and
   the offline bundle `govmonitor-offline-<version>.tar.gz` and attaches both to the run.
   (Locally: `make release`.)
7. Smoke-test the bundle on a clean machine: `install.sh`, sign in, one export (ADMIN_GUIDE §3, §5).
8. Update a copy of the previous version with `update.sh` and confirm the dashboard figures are
   unchanged.
9. Publish the bundle and its SHA-256 to customers with the changelog entry and the ADMIN_GUIDE.

## Hotfixes

Branch from the release tag, fix, bump the patch number, and follow steps 1–9.
