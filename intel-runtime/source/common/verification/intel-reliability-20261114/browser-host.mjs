/** Test-owned host for the separately built UI and the actual station proxy. */
import express from '../../morph-station/node_modules/express/index.js';
import fs from 'node:fs';
import path from 'node:path';
import { createLocalRequestGuard, createStationProxy, createStationTokenReader } from '../../morph-station/server/stationProxy.ts';
const config = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const port = Number(new URL(config.uiOrigin).port);
const app = express();
app.disable('x-powered-by');
app.use(createLocalRequestGuard(port));
app.use(createStationProxy({ upstreamOrigin: config.apiOrigin, getToken: createStationTokenReader({ tokenFile: path.join(config.dataDirectory, 'api-token') }) }));
app.use(express.static(config.distDirectory));
app.get('*', (_req, res) => res.sendFile(path.join(config.distDirectory, 'index.html')));
app.listen(port, '127.0.0.1', () => console.log('Owned Gemma verification dashboard ready.'));
