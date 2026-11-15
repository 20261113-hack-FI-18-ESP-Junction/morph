/** Local host configuration only; it does not attest remote service or hardware readiness. */
import type { RequestHandler } from 'express';

export function createLocalRuntime(runtimeMode: 'station' | 'demo', stationId: string | null = null): RequestHandler {
  if (runtimeMode === 'station' && (!stationId || !/^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$/.test(stationId))) {
    throw new TypeError('Choose a valid configured station identifier.');
  }
  const metadata = Object.freeze({ version: 1, runtimeMode,
    recordsTransport: runtimeMode === 'station' ? 'mac-mcp' : 'local-simulation',
    stationId: runtimeMode === 'station' ? stationId : null,
    controlHost: 'jose', motionRoutes: false });
  return (req, res, next) => {
    if (req.path !== '/api/local/v1/runtime') { next(); return; }
    res.setHeader('Cache-Control', 'no-store');
    res.setHeader('X-Content-Type-Options', 'nosniff');
    if (req.method !== 'GET') {
      res.setHeader('Allow', 'GET');
      res.status(405).json({ detail: 'Local runtime metadata permits GET only.' });
      return;
    }
    res.json(metadata);
  };
}
