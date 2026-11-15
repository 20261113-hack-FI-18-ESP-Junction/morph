/** Local dashboard host. Intel owns records; MCP carries reads and explicit review/analysis requests. */
import dotenv from "dotenv";
import express from "express";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createLocalRequestGuard, createStationProxy } from "./server/stationProxy.ts";

import { createMcpStationFetch, createMcpToolClient, MCP_LOCAL_TRANSPORT_MARKER, MCP_PROXY_ORIGIN } from "./server/mcpStationTransport.ts";

dotenv.config({ quiet: true });
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PORT = Number(process.env.PORT ?? 3000);
if (!Number.isSafeInteger(PORT) || PORT < 1 || PORT > 65535) throw new Error("PORT must be between 1 and 65535.");
const app = express();
app.disable("x-powered-by");
app.use(createLocalRequestGuard(PORT));
const pairingDir = process.env.MORPH_CONTEXT_PAIRING_DIR;
const callTool = pairingDir ? createMcpToolClient(path.resolve(pairingDir)) : async () => {
  throw new Error("Configure the server-only Morph MCP pairing directory.");
};
app.use(createStationProxy({
  upstreamOrigin: MCP_PROXY_ORIGIN,
  getToken: () => MCP_LOCAL_TRANSPORT_MARKER,
  fetch: createMcpStationFetch({ callTool, stationId: process.env.MORPH_STATION_ID ?? "intel-main" }),
  requestTimeoutMs: 40_000,
  eventIdleTimeoutMs: 45_000,
}));
async function startServer() {
  const distPath = path.resolve(__dirname, "dist");
  const isProd = process.env.NODE_ENV === "production";
  if (isProd && !fs.existsSync(path.join(distPath, "index.html"))) throw new Error("Build the dashboard before starting production mode.");
  if (!isProd) {
    const { createServer: createViteServer } = await import("vite");
    const vite = await createViteServer({ server: { middlewareMode: true }, appType: "spa" });
    app.use(vite.middlewares);
  } else {
    app.use(express.static(distPath));
    app.get("*", (_req, res) => res.sendFile(path.join(distPath, "index.html")));
  }
  app.listen(PORT, "127.0.0.1", () => console.log(`Morph dashboard is available at http://127.0.0.1:${PORT}`));
}
startServer().catch(() => { console.error("The local Morph dashboard could not start. Check server configuration."); process.exitCode = 1; });
