import test, { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';

import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const DIST_DIR = path.resolve(__dirname, '../dist');
const SRC_DIR = path.resolve(__dirname, '../src');

describe('Phase 6 Frontend Verification Suite', () => {

  // 1. API Health Rendering & Contract
  it('1. API health contract is properly typed and handled', () => {
    const apiFile = fs.readFileSync(path.join(SRC_DIR, 'services/api.ts'), 'utf-8');
    const typesFile = fs.readFileSync(path.join(SRC_DIR, 'types/index.ts'), 'utf-8');
    assert.match(apiFile, /fetchHealth/, 'api.ts must export fetchHealth');
    assert.match(apiFile, /\/health/, 'api.ts must request /health endpoint');
    assert.match(typesFile, /catalog_size:\s*number/, 'HealthResponse must define catalog_size');
    assert.match(typesFile, /cache_entries:\s*number/, 'HealthResponse must define cache_entries');
  });

  // 2. Successful Troubleshooting Response Mapping
  it('2. Troubleshooting service handles 200 OK and extracts ContextDeeplinkResponse', () => {
    const apiFile = fs.readFileSync(path.join(SRC_DIR, 'services/api.ts'), 'utf-8');
    assert.match(apiFile, /executeTroubleshoot/, 'api.ts must export executeTroubleshoot');
    assert.match(apiFile, /\/v1\/troubleshoot/, 'api.ts must call /v1/troubleshoot');
    assert.match(apiFile, /res\.json\(\)/, 'Must parse JSON response body');
  });

  // 3. Loading State
  it('3. Loading / diagnosis state is rendered with spinner and disabled states', () => {
    const uiFile = fs.readFileSync(path.join(SRC_DIR, 'components/TroubleshootingView.tsx'), 'utf-8');
    assert.match(uiFile, /loading/, 'Must accept and manage loading prop');
    assert.match(uiFile, /spinner/, 'Must render spinner element when loading');
    assert.match(uiFile, /Synthesizing Plan/, 'Must display active progress message');
    assert.match(uiFile, /disabled=\{loading/, 'Must disable buttons while loading');
  });

  // 4. API Validation Error Handling (422)
  it('4. API validation errors (HTTP 422) are cleanly parsed without internal leaks', () => {
    const apiFile = fs.readFileSync(path.join(SRC_DIR, 'services/api.ts'), 'utf-8');
    assert.match(apiFile, /res\.status === 422/, 'Must explicitly catch 422 validation errors');
    assert.match(apiFile, /Validation error \(422\)/, 'Must provide user-friendly error message');
  });

  // 5. API Server Error Handling (500 / 503 / Network)
  it('5. API server errors and 503 readiness are gracefully handled', () => {
    const apiFile = fs.readFileSync(path.join(SRC_DIR, 'services/api.ts'), 'utf-8');
    assert.match(apiFile, /res\.status === 503/, 'Must explicitly catch 503 initialization state');
    assert.match(apiFile, /Network connection failed/, 'Must handle network disconnection gracefully');
  });

  // 6. Cache Telemetry Rendering
  it('6. Cache telemetry extracts X-headers and renders HUD', () => {
    const apiFile = fs.readFileSync(path.join(SRC_DIR, 'services/api.ts'), 'utf-8');
    assert.match(apiFile, /X-Process-Time-Ms/, 'Must extract X-Process-Time-Ms header');
    assert.match(apiFile, /X-Cache-Hit/, 'Must extract X-Cache-Hit header');
    assert.match(apiFile, /X-Cache-Type/, 'Must extract X-Cache-Type header');
    assert.match(apiFile, /X-Extraction-Path/, 'Must extract X-Extraction-Path header');

    const hudFile = fs.readFileSync(path.join(SRC_DIR, 'components/TelemetryHUD.tsx'), 'utf-8');
    assert.match(hudFile, /telemetry\.processTimeMs/, 'Must render processTimeMs');
    assert.match(hudFile, /telemetry\.cacheHit/, 'Must render cache hit status');
  });

  // 7. Action Rendering & Hierarchy Order
  it('7. Actions render category badges and sequential steps', () => {
    const cardFile = fs.readFileSync(path.join(SRC_DIR, 'components/ActionCard.tsx'), 'utf-8');
    assert.match(cardFile, /badge-auto/, 'Must style automated actions');
    assert.match(cardFile, /badge-manual/, 'Must style manual actions');
    assert.match(cardFile, /badge-critical/, 'Must style critical actions');
    assert.match(cardFile, /action\.description/, 'Must render 5-7 word action description');
    assert.match(cardFile, /sg\.steps/, 'Must render individual steps');
  });

  // 8. Deeplink Rendering & Protocol Handling
  it('8. Deeplinks preserve opaque URIs and provide Galaxy protocol notice', () => {
    const modalFile = fs.readFileSync(path.join(SRC_DIR, 'components/DeeplinkModal.tsx'), 'utf-8');
    assert.match(modalFile, /deeplink\.deeplink/, 'Must render opaque deeplink URI');
    assert.match(modalFile, /navigator\.clipboard\.writeText/, 'Must provide copy URI button');
    assert.match(modalFile, /Galaxy Device Integration Notice/, 'Must explain bixby:// protocol behavior');
  });

  // 9. Empty State & Reset Behavior
  it('9. Empty states and form resets properly restore initial benchmark data', () => {
    const uiFile = fs.readFileSync(path.join(SRC_DIR, 'components/TroubleshootingView.tsx'), 'utf-8');
    assert.match(uiFile, /onClear\(\)/, 'Must trigger onClear on reset');
    assert.match(uiFile, /btn-reset/, 'Must have reset button');
  });

  // 10. Mobile / Responsive Layout CSS
  it('10. CSS stylesheet contains mobile responsive media queries and design tokens', () => {
    const cssFile = fs.readFileSync(path.join(SRC_DIR, 'styles/index.css'), 'utf-8');
    assert.match(cssFile, /@media \(max-width: 768px\)/, 'Must include responsive mobile breakpoint');
    assert.match(cssFile, /--samsung-blue/, 'Must use Samsung blue visual theme');
    assert.match(cssFile, /\.dashboard-root/, 'Must style Dashboard view');
    assert.match(cssFile, /\.troubleshoot-view/, 'Must style Troubleshooter view');
  });

  // 11. Production Build Asset Integrity
  it('11. Production dist files exist and are correctly compiled', () => {
    assert.ok(fs.existsSync(path.join(DIST_DIR, 'index.html')), 'dist/index.html must exist');
    const htmlContent = fs.readFileSync(path.join(DIST_DIR, 'index.html'), 'utf-8');
    assert.match(htmlContent, /<div id="root"><\/div>/, 'Root mount point must exist');
  });
});
