/** Local dashboard host. Intel owns records; MCP carries reads and explicit review/analysis requests. */
import dotenv from "dotenv";
import express from "express";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createLocalRequestGuard, createStationProxy } from "./server/stationProxy.ts";
import { mediaGatewayFromEnvironment } from "./server/mediaGateway.ts";
import { createLocalRuntime } from "./server/localRuntime.ts";

import { createMcpStationFetch, createMcpToolClient, MCP_LOCAL_TRANSPORT_MARKER, MCP_PROXY_ORIGIN } from "./server/mcpStationTransport.ts";

if (process.env.MORPH_SKIP_DOTENV !== '1') dotenv.config({ quiet: true });
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PORT = Number(process.env.PORT ?? 3000);
if (!Number.isSafeInteger(PORT) || PORT < 1 || PORT > 65535) throw new Error("PORT must be between 1 and 65535.");
const app = express();
app.disable("x-powered-by");
app.use(createLocalRequestGuard(PORT));
const stationId = process.env.MORPH_STATION_ID ?? "intel-main";
app.use(createLocalRuntime('station', stationId));
const media = mediaGatewayFromEnvironment();
app.use(media.middleware);
const pairingDir = process.env.MORPH_CONTEXT_PAIRING_DIR;
const callTool = pairingDir ? createMcpToolClient(path.resolve(pairingDir)) : async () => {
  throw new Error("Configure the server-only Morph MCP pairing directory.");
};
app.use(createStationProxy({
  upstreamOrigin: MCP_PROXY_ORIGIN,
  getToken: () => MCP_LOCAL_TRANSPORT_MARKER,
  fetch: createMcpStationFetch({ callTool, stationId }),
  requestTimeoutMs: 40_000,
  eventIdleTimeoutMs: 45_000,
}));
async function startServer() {
  let closeVite = async () => {};
  const distPath = path.resolve(__dirname, "dist");
  const isProd = process.env.NODE_ENV === "production";
  if (isProd && !fs.existsSync(path.join(distPath, "index.html"))) throw new Error("Build the dashboard before starting production mode.");
  if (!isProd) {
    const { createServer: createViteServer } = await import("vite");
    const runtimeDir = process.env.MORPH_DASHBOARD_RUNTIME_DIR;
    if (runtimeDir) {
      const info = fs.lstatSync(runtimeDir);
      if (!path.isAbsolute(runtimeDir) || !info.isDirectory() || info.isSymbolicLink() ||
          (info.mode & 0o077) !== 0 || (typeof process.getuid === 'function' && info.uid !== process.getuid())) {
        throw new Error('The dashboard runtime directory must be private and owned by this user.');
      }
    }
    const vite = await createViteServer({
      ...(runtimeDir ? { envDir: runtimeDir, cacheDir: path.join(runtimeDir, 'vite-cache') } : {}),
      server: { middlewareMode: true }, appType: "spa" });
    closeVite = () => vite.close();
    app.use(vite.middlewares);
  } else {
    app.use(express.static(distPath));
    app.get("*", (_req, res) => res.sendFile(path.join(distPath, "index.html")));
  }
  const server = app.listen(PORT, "127.0.0.1", () => console.log(`Morph dashboard is available at http://127.0.0.1:${PORT}`));
  let closing = false;
  async function close() {
    if (closing) return;
    closing = true;
    server.close();
    // An event stream can remain active indefinitely; abort local HTTP clients
    // before draining tracked media operations and the development websocket.
    server.closeAllConnections();
    await media.close(); await closeVite();
    process.exitCode = 0;
  }
  process.on('SIGINT', () => { void close(); });
  process.on('SIGTERM', () => { void close(); });
}
startServer().catch(() => { console.error("The local Morph dashboard could not start. Check server configuration."); process.exitCode = 1; });
