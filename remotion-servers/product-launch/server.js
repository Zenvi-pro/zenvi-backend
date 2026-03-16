'use strict';

/**
 * Zenvi — Product Launch Remotion Rendering Service
 * Port: 3100  (set via PORT env var)
 *
 * Renders a promotional video for a GitHub repository, uploads it to the
 * Supabase "product_demo" storage bucket, and returns the public URL.
 * File size is capped at 50 MB before upload.
 *
 * API:
 *   GET  /api/health
 *   POST /api/render   body: { repo_data, style?, duration? }
 *                      response: { status: "completed", supabase_url, supabase_path }
 *                             or { status: "failed", error }
 */

require('dotenv').config();

const express = require('express');
const path = require('path');
const fs = require('fs');
const { createClient } = require('@supabase/supabase-js');
const { bundle } = require('@remotion/bundler');
const { renderMedia, selectComposition } = require('@remotion/renderer');

const PORT = parseInt(process.env.PORT || '3100', 10);
const RENDERS_DIR = path.join(__dirname, 'renders');
const ENTRY_POINT = path.join(__dirname, 'src', 'index.ts');
const BUCKET = 'product_demo';
const MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024; // 50 MB

fs.mkdirSync(RENDERS_DIR, { recursive: true });

// ---------------------------------------------------------------------------
// Supabase client — requires SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY in .env
// ---------------------------------------------------------------------------

function getSupabase() {
  const url = process.env.SUPABASE_URL;
  const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!url || !key) {
    throw new Error('SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set in .env');
  }
  return createClient(url, key);
}

// ---------------------------------------------------------------------------
// Lazily cached Remotion bundle
// ---------------------------------------------------------------------------

/** @type {string|null} */
let bundleUrl = null;

async function getBundle() {
  if (!bundleUrl) {
    console.log('[bundle] Building Remotion bundle…');
    bundleUrl = await bundle({
      entryPoint: ENTRY_POINT,
      onProgress: (p) => process.stdout.write(`\r[bundle] ${p}%`),
    });
    console.log('\n[bundle] Done →', bundleUrl);
  }
  return bundleUrl;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function styleToTheme(style) {
  const themes = {
    modern:  { bg: '#0f0f1a', accent: '#4f8ef7', text: '#ffffff', sub: '#a0aec0' },
    minimal: { bg: '#ffffff', accent: '#1a1a2e', text: '#1a1a2e', sub: '#718096' },
    bold:    { bg: '#0a0a0a', accent: '#00ff88', text: '#ffffff', sub: '#cccccc' },
  };
  return themes[style] || themes.modern;
}

function sanitize(str) {
  return (str || 'unknown').replace(/[^a-z0-9_-]/gi, '_').slice(0, 40);
}

// ---------------------------------------------------------------------------
// Express app
// ---------------------------------------------------------------------------

const app = express();
app.use(express.json({ limit: '10mb' }));

// GET /api/health
app.get('/api/health', (_req, res) => {
  res.json({ status: 'ok', service: 'zenvi-remotion-product-launch' });
});

// POST /api/render
app.post('/api/render', async (req, res) => {
  const { repo_data = {}, style = 'modern', duration = 30 } = req.body;

  const fps = 30;
  const durationInFrames = Math.max(fps, duration * fps);
  const theme = styleToTheme(style);

  const owner = repo_data?.owner || repo_data?.repo_info?.owner?.login || 'unknown';
  const repo  = repo_data?.repo  || repo_data?.repo_info?.name          || 'project';
  const ts    = Date.now();
  const filename     = `${sanitize(owner)}_${sanitize(repo)}_${ts}.mp4`;
  const outputPath   = path.join(RENDERS_DIR, filename);
  const supabasePath = `${sanitize(owner)}/${sanitize(repo)}/${ts}.mp4`;

  const inputProps = {
    repoData: {
      owner,
      repo,
      name:        repo_data?.name        || repo_data?.repo_info?.name        || repo,
      description: repo_data?.description || repo_data?.repo_info?.description || '',
      stars:       repo_data?.stars       ?? repo_data?.repo_info?.stargazers_count ?? 0,
      forks:       repo_data?.forks       ?? repo_data?.repo_info?.forks_count      ?? 0,
      language:    repo_data?.language    || repo_data?.repo_info?.language    || '',
      topics:      repo_data?.topics      || repo_data?.repo_info?.topics      || [],
      homepage:    repo_data?.homepage    || repo_data?.repo_info?.homepage    || '',
      readme:      repo_data?.readme      || '',
    },
    theme,
    durationInFrames,
  };

  try {
    // ---- 1. Render --------------------------------------------------------
    const serveUrl = await getBundle();

    const composition = await selectComposition({
      serveUrl,
      id: 'ProductLaunchVideo',
      inputProps,
    });

    console.log(`[render] Rendering product launch for ${owner}/${repo}…`);

    await renderMedia({
      composition: { ...composition, durationInFrames, fps },
      serveUrl,
      codec: 'h264',
      outputLocation: outputPath,
      inputProps,
      onProgress: ({ progress }) => process.stdout.write(`\r[render] ${Math.round(progress * 100)}%`),
    });

    console.log(`\n[render] Done → ${outputPath}`);

    // ---- 2. File-size guard (50 MB cap) -----------------------------------
    const fileSize = fs.statSync(outputPath).size;
    if (fileSize > MAX_FILE_SIZE_BYTES) {
      fs.unlink(outputPath, () => {});
      const sizeMB = (fileSize / 1024 / 1024).toFixed(1);
      return res.status(413).json({
        status: 'failed',
        error: `Rendered video (${sizeMB} MB) exceeds the 50 MB upload limit. Try a shorter duration or a lower-complexity composition.`,
      });
    }

    // ---- 3. Upload to Supabase --------------------------------------------
    console.log(`[supabase] Uploading to bucket "${BUCKET}" → ${supabasePath}…`);

    const supabase    = getSupabase();
    const fileBuffer  = fs.readFileSync(outputPath);

    const { error: uploadError } = await supabase.storage
      .from(BUCKET)
      .upload(supabasePath, fileBuffer, {
        contentType: 'video/mp4',
        upsert: true,
      });

    if (uploadError) {
      throw new Error(`Supabase upload failed: ${uploadError.message}`);
    }

    const { data: urlData } = supabase.storage
      .from(BUCKET)
      .getPublicUrl(supabasePath);

    const supabaseUrl = urlData?.publicUrl;
    if (!supabaseUrl) {
      throw new Error('Could not obtain public URL from Supabase after upload.');
    }

    console.log(`[supabase] Uploaded → ${supabaseUrl}`);

    // Clean up local render file after successful upload
    fs.unlink(outputPath, () => {});

    res.json({
      status: 'completed',
      supabase_url: supabaseUrl,
      supabase_path: supabasePath,
    });

  } catch (err) {
    console.error('[render/upload] Failed:', err);
    // Clean up partial file if it exists
    if (fs.existsSync(outputPath)) fs.unlink(outputPath, () => {});
    res.status(500).json({ status: 'failed', error: err.message || String(err) });
  }
});

// DELETE /api/cleanup  — delete a rendered file from Supabase after the client imports it
app.delete('/api/cleanup', async (req, res) => {
  const { supabase_path } = req.body || {};
  if (!supabase_path) {
    return res.status(400).json({ error: 'supabase_path is required' });
  }
  try {
    const supabase = getSupabase();
    const { error } = await supabase.storage.from(BUCKET).remove([supabase_path]);
    if (error) throw new Error(error.message);
    console.log(`[supabase] Deleted "${supabase_path}" from bucket "${BUCKET}"`);
    res.json({ status: 'deleted', path: supabase_path });
  } catch (err) {
    console.error('[cleanup] Failed to delete from Supabase:', err);
    res.status(500).json({ error: err.message || String(err) });
  }
});

// ---------------------------------------------------------------------------
// Start
// ---------------------------------------------------------------------------
app.listen(PORT, () => {
  console.log(`[zenvi-remotion-product-launch] Listening on http://0.0.0.0:${PORT}`);
});
