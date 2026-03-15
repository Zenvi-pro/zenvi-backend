'use strict';

/**
 * Zenvi — Full Remotion Rendering Service
 * Port: 4500  (set via PORT env var)
 *
 * API:
 *   GET  /api/v1/health
 *   POST /api/v1/render          → { job_id }
 *   GET  /api/v1/status/:job_id  → { status, progress?, error? }
 *   GET  /api/v1/download/:job_id → streams the rendered MP4
 */

const express = require('express');
const path = require('path');
const fs = require('fs');
const { v4: uuidv4 } = require('uuid');
const { bundle } = require('@remotion/bundler');
const { renderMedia, selectComposition } = require('@remotion/renderer');

const PORT = parseInt(process.env.PORT || '4500', 10);
const RENDERS_DIR = path.join(__dirname, 'renders');
const ENTRY_POINT = path.join(__dirname, 'src', 'index.ts');

// Ensure renders directory exists
fs.mkdirSync(RENDERS_DIR, { recursive: true });

// ---------------------------------------------------------------------------
// In-memory job store
// ---------------------------------------------------------------------------

/** @type {Map<string, { status: string, progress: number, outputPath: string|null, error: string|null, createdAt: Date }>} */
const jobs = new Map();

// Lazily cached bundle URL — rebuilding on every request is too slow
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

/** Map a style string to input props consumed by the compositions. */
function styleToTheme(style) {
  const themes = {
    modern: { bg: '#0f0f1a', accent: '#4f8ef7', text: '#ffffff', sub: '#a0aec0' },
    minimal: { bg: '#ffffff', accent: '#1a1a2e', text: '#1a1a2e', sub: '#718096' },
    bold: { bg: '#0a0a0a', accent: '#00ff88', text: '#ffffff', sub: '#cccccc' },
  };
  return themes[style] || themes.modern;
}

/** Kick off a render in the background. Updates the job store as it progresses. */
async function startRender(jobId, compositionId, inputProps, durationInFrames, fps) {
  const outputPath = path.join(RENDERS_DIR, `${jobId}.mp4`);

  jobs.set(jobId, {
    status: 'processing',
    progress: 0,
    outputPath: null,
    error: null,
    createdAt: new Date(),
  });

  try {
    const serveUrl = await getBundle();

    const composition = await selectComposition({
      serveUrl,
      id: compositionId,
      inputProps,
    });

    await renderMedia({
      composition: {
        ...composition,
        durationInFrames: Math.max(1, durationInFrames),
        fps,
      },
      serveUrl,
      codec: 'h264',
      outputLocation: outputPath,
      inputProps,
      onProgress: ({ progress }) => {
        const job = jobs.get(jobId);
        if (job) job.progress = Math.round(progress * 100);
      },
    });

    const job = jobs.get(jobId);
    if (job) {
      job.status = 'completed';
      job.progress = 100;
      job.outputPath = outputPath;
    }
    console.log(`[render] Job ${jobId} completed → ${outputPath}`);
  } catch (err) {
    const job = jobs.get(jobId);
    if (job) {
      job.status = 'failed';
      job.error = err.message || String(err);
    }
    console.error(`[render] Job ${jobId} failed:`, err);
  }
}

// ---------------------------------------------------------------------------
// Express app
// ---------------------------------------------------------------------------

const app = express();
app.use(express.json({ limit: '10mb' }));

// GET /api/v1/health
app.get('/api/v1/health', (_req, res) => {
  res.json({ status: 'ok', service: 'zenvi-remotion-full-service', jobs: jobs.size });
});

// POST /api/v1/render
app.post('/api/v1/render', (req, res) => {
  const { type, style = 'modern', duration = 30, resolution = '1080p', repo_url, repo_data, research_data } = req.body;

  if (!type || !['repo', 'sonar'].includes(type)) {
    return res.status(400).json({ error: 'type must be "repo" or "sonar"' });
  }

  const fps = 30;
  const durationInFrames = duration * fps;
  const theme = styleToTheme(style);

  const jobId = uuidv4();

  let compositionId;
  let inputProps;

  if (type === 'repo') {
    compositionId = 'RepoVideo';
    inputProps = {
      repoUrl: repo_url || '',
      repoData: repo_data || {},
      theme,
      durationInFrames,
    };
  } else {
    compositionId = 'SonarVideo';
    inputProps = {
      researchData: research_data || {},
      theme,
      durationInFrames,
    };
  }

  // Fire-and-forget — client polls /status/:job_id
  startRender(jobId, compositionId, inputProps, durationInFrames, fps).catch(() => {});

  res.json({ job_id: jobId });
});

// GET /api/v1/status/:job_id
app.get('/api/v1/status/:jobId', (req, res) => {
  const job = jobs.get(req.params.jobId);
  if (!job) {
    return res.status(404).json({ error: 'Job not found' });
  }
  res.json({
    status: job.status,
    progress: job.progress,
    error: job.error || undefined,
  });
});

// GET /api/v1/download/:job_id
app.get('/api/v1/download/:jobId', (req, res) => {
  const job = jobs.get(req.params.jobId);
  if (!job) {
    return res.status(404).json({ error: 'Job not found' });
  }
  if (job.status !== 'completed' || !job.outputPath) {
    return res.status(409).json({ error: `Job is not complete (status: ${job.status})` });
  }
  if (!fs.existsSync(job.outputPath)) {
    return res.status(404).json({ error: 'Rendered file not found on disk' });
  }

  const filename = `zenvi-render-${req.params.jobId}.mp4`;
  res.setHeader('Content-Type', 'video/mp4');
  res.setHeader('Content-Disposition', `attachment; filename="${filename}"`);
  fs.createReadStream(job.outputPath).pipe(res);
});

// ---------------------------------------------------------------------------
// Periodic cleanup — remove completed jobs older than 1 hour
// ---------------------------------------------------------------------------
setInterval(() => {
  const cutoff = Date.now() - 60 * 60 * 1000;
  for (const [id, job] of jobs.entries()) {
    if (job.createdAt.getTime() < cutoff && ['completed', 'failed'].includes(job.status)) {
      if (job.outputPath && fs.existsSync(job.outputPath)) {
        fs.unlink(job.outputPath, () => {});
      }
      jobs.delete(id);
    }
  }
}, 15 * 60 * 1000);

// ---------------------------------------------------------------------------
// Start
// ---------------------------------------------------------------------------
app.listen(PORT, () => {
  console.log(`[zenvi-remotion-full-service] Listening on http://0.0.0.0:${PORT}`);
});
