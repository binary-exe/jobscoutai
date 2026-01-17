// #region agent log
/**
 * Minimal diagnostic script for debug-mode runtime evidence.
 * Writes NDJSON logs via the local ingest server (Cursor-provided).
 *
 * Run:
 *   node frontend/scripts/debug_diag.js
 */
const ENDPOINT =
  'http://127.0.0.1:7242/ingest/de514c6d-c2f9-42e3-8e05-845dd72b3ef2';

function send(hypothesisId, location, message, data) {
  // Never throw; diagnostics only.
  return fetch(ENDPOINT, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      sessionId: 'debug-session',
      runId: 'pre-fix',
      hypothesisId,
      location,
      message,
      data,
      timestamp: Date.now(),
    }),
  }).catch(() => {});
}

async function main() {
  const fs = require('fs');
  const path = require('path');

  await send('H_FRONTEND_ENV', 'frontend/scripts/debug_diag.js:main', 'start', {
    node: process.version,
    cwd: process.cwd(),
  });

  // Check eslint config presence (hypothesis: lint prompt due to missing config/deps)
  const eslintrc = path.join(process.cwd(), 'frontend', '.eslintrc.json');
  await send(
    'H_FRONTEND_LINT_PROMPT',
    'frontend/scripts/debug_diag.js:main',
    'eslintrc_exists',
    { eslintrc, exists: fs.existsSync(eslintrc) }
  );

  // Check whether layout.tsx contains metadataBase (hypothesis: build warning persists)
  const layout = path.join(process.cwd(), 'frontend', 'app', 'layout.tsx');
  let layoutHasMetadataBase = null;
  try {
    const txt = fs.readFileSync(layout, 'utf8');
    layoutHasMetadataBase = txt.includes('metadataBase');
  } catch (e) {
    layoutHasMetadataBase = null;
  }
  await send(
    'H_FRONTEND_METADATA_BASE',
    'frontend/scripts/debug_diag.js:main',
    'layout_metadataBase_present',
    { layout, present: layoutHasMetadataBase, nextPublicSiteUrl: process.env.NEXT_PUBLIC_SITE_URL ?? null }
  );

  // Quick check if eslint is installed in frontend/node_modules
  const eslintPkg = path.join(process.cwd(), 'frontend', 'node_modules', 'eslint', 'package.json');
  let eslintVersion = null;
  try {
    eslintVersion = JSON.parse(fs.readFileSync(eslintPkg, 'utf8')).version ?? null;
  } catch (e) {
    eslintVersion = null;
  }
  await send(
    'H_FRONTEND_LINT_PROMPT',
    'frontend/scripts/debug_diag.js:main',
    'eslint_installed',
    { eslintPkg, version: eslintVersion }
  );

  await send('H_FRONTEND_ENV', 'frontend/scripts/debug_diag.js:main', 'end', {});
}

main().catch(() => {});
// #endregion

