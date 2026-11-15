/** Explicit disposable simulation host. Production continues to use the MCP server. */
import express from 'express';
import fs from 'node:fs';
import path from 'node:path';
import { createServer as createViteServer } from 'vite';
import { createLocalRequestGuard, createStationProxy, createStationTokenReader } from '../server/stationProxy.ts';
import { createMediaGateway, readMediaConfig } from '../server/mediaGateway.ts';
import { createLocalRuntime } from '../server/localRuntime.ts';

if (process.env.MORPH_DEMO_MODE !== '1') throw new Error('Start this host through the explicit npm demo command.');
const port = Number(process.env.MORPH_DEMO_PORT);
const origin = new URL(process.env.MORPH_DEMO_ORIGIN ?? '');
const runtime = process.env.MORPH_DEMO_RUNTIME_DIR;
const tokenFile = process.env.MORPH_DEMO_TOKEN_FILE;
if (!Number.isSafeInteger(port) || port < 1 || port > 65535 || origin.protocol !== 'http:' ||
    origin.hostname !== '127.0.0.1' || !runtime || !tokenFile ||
    path.dirname(tokenFile) !== runtime || !fs.existsSync(path.join(runtime, 'demo-instance.json'))) {
  throw new Error('The demo requires its owned local API and disposable credential directory.');
}
const app = express();
app.disable('x-powered-by');
app.use(createLocalRequestGuard(port));
app.use(createLocalRuntime('demo'));
const mediaConfig = (() => {
  try { return process.env.MORPH_MEDIA_CONFIG_FILE ? readMediaConfig(process.env.MORPH_MEDIA_CONFIG_FILE) : null; }
  catch { throw new Error('The private demo media configuration is invalid or unavailable.'); }
})();
if (mediaConfig && (mediaConfig.sourceMode !== 'simulation' ||
    !['127.0.0.1', 'localhost', '[::1]'].includes(new URL(mediaConfig.whepUrl).hostname) ||
    (mediaConfig.statusUrl && !['127.0.0.1', 'localhost', '[::1]'].includes(new URL(mediaConfig.statusUrl).hostname)) ||
    (mediaConfig.iceServers?.length ?? 0) !== 0)) {
  throw new Error('The disposable demo accepts only explicitly configured loopback simulation media.');
}
const media = createMediaGateway({ config: mediaConfig });
app.use(media.middleware);
app.use((req, res, next) => {
  if (req.path.startsWith('/api') && req.method !== 'GET') {
    res.setHeader('Allow', 'GET');
    res.status(405).json({ detail: 'The disposable simulation demo permits GET only.' });
    return;
  }
  next();
});
app.use(createStationProxy({ upstreamOrigin: origin.origin,
  getToken: createStationTokenReader({ tokenFile }), requestTimeoutMs: 15_000 }));
const vite = await createViteServer({ envDir: runtime, cacheDir: path.join(runtime, 'vite-cache'),
  server: { middlewareMode: true, hmr: false, watch: null }, appType: 'spa' });
app.use(vite.middlewares);
const server = app.listen(port, '127.0.0.1');
server.on('error', async () => { await vite.close(); process.exitCode = 1; });
let closing = false;
async function close() {
  if (closing) return;
  closing = true;
  server.close();
  server.closeAllConnections();
  await media.close();
  await vite.close();
}
process.on('SIGINT', () => { void close(); });
process.on('SIGTERM', () => { void close(); });
