/** Local records bridge with explicit review and isolated evidence-analysis requests; no robot dispatch. */
import type { IncomingMessage, ServerResponse } from "node:http";
import { open } from "node:fs/promises";
import { constants } from "node:fs";

type Middleware = (req: IncomingMessage & { originalUrl?: string }, res: ServerResponse, next: () => void) => void;
export interface StationProxyOptions {
  upstreamOrigin: string; getToken: () => string | Promise<string>; fetch?: typeof fetch;
  requestTimeoutMs?: number; eventIdleTimeoutMs?: number;
}
function fail(res: ServerResponse, status: number, detail: string): void {
  if (res.destroyed) return;
  if (res.headersSent) { res.destroy(); return; }
  res.statusCode = status;
  res.setHeader("Content-Type", "application/json; charset=utf-8");
  res.setHeader("Cache-Control", "no-store"); res.setHeader("X-Content-Type-Options", "nosniff");
  res.end(JSON.stringify({ detail }));
}
/** Restrict local Host values against DNS rebinding and reject cross-origin callers. */
export function createLocalRequestGuard(port: number): Middleware {
  if (!Number.isSafeInteger(port) || port < 1 || port > 65535) throw new TypeError("Invalid dashboard port.");
  const hosts = new Set([`127.0.0.1:${port}`, `localhost:${port}`, `[::1]:${port}`]);
  if (port === 80) { hosts.add("127.0.0.1"); hosts.add("localhost"); hosts.add("[::1]"); }
  return (req, res, next) => {
    const host = req.headers.host?.toLowerCase(); let count = 0;
    for (let i = 0; i < req.rawHeaders.length; i += 2) if (req.rawHeaders[i]?.toLowerCase() === "host") count++;
    if (!host || count !== 1 || !hosts.has(host)) { fail(res, 403, "Only local dashboard requests are allowed."); return; }
    const origin = req.headers.origin, site = req.headers["sec-fetch-site"];
    if ((origin !== undefined && origin !== `http://${host}`) ||
      (site !== undefined && site !== "same-origin" && site !== "none")) {
      fail(res, 403, "Cross-origin dashboard requests are not allowed."); return;
    }
    next();
  };
}
/** Reload existing credentials per request. Never generates a token or returns it to the browser. */
export function createStationTokenReader(options: { tokenFile: string; getEnvironmentToken?: () => string | undefined }): () => Promise<string> {
  return async () => {
    let token = options.getEnvironmentToken?.();
    if (token === undefined) {
      const file = await open(options.tokenFile, constants.O_RDONLY | constants.O_NOFOLLOW);
      try {
        const info = await file.stat();
        if (!info.isFile() || info.size > 4096 || (info.mode & 0o077) !== 0 ||
          (typeof process.getuid === "function" && info.uid !== process.getuid())) throw new Error("Invalid station token file.");
        token = (await file.readFile("utf8")).trim();
      } finally { await file.close(); }
    }
    if (token.length < 32 || token.length > 4096 || !/^[!-~]+$/.test(token)) throw new Error("Invalid station token.");
    return token;
  };
}
interface Route { path: string; query: URLSearchParams; kind: "json" | "events" | "evidence" | "export"; intent?: "record-review" | "evidence-analysis" }
function routeFor(raw: string, write = false): Route | null {
  if (raw.length > 8192 || !raw.startsWith("/") || raw.startsWith("//") || raw.includes("#")) return null;
  const url = new URL(raw, "http://local.invalid"); let path = url.pathname;
  let allowed: string[] = [], kind: Route["kind"] = "json";
  if (write) {
    if (path === "/api/v1/analysis/reports" && !url.search)
      return { path, query: url.searchParams, kind, intent: "evidence-analysis" };
    const match = /^\/api\/v1\/cycles\/([^/]+)\/review$/.exec(path);
    if (!match || url.search) return null;
    let id: string; try { id = decodeURIComponent(match[1]!); } catch { return null; }
    if (!/^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$/.test(id)) return null;
    return { path: `/api/v1/cycles/${encodeURIComponent(id)}/review`, query: url.searchParams, kind, intent: "record-review" };
  }
  if (path === "/api/v1/station/snapshot") allowed = ["sessionId"];
  else if (path === "/api/v1/dashboard") allowed = ["sessionId", "sourceMode", "limit", "cycleId"];
  else if (path === "/api/v1/metrics") allowed = ["includeSimulation"];
  else if (["/api/v1/sessions", "/api/v1/schema", "/api/v1/cameras"].includes(path)) allowed = [];
  else if (path === "/api/v1/cycles") allowed = ["sessionId", "objectId", "outcome", "sourceMode", "includeSimulation", "hasRetry", "errorCode", "modelId", "referenceStatus", "startedAfter", "startedBefore", "offset", "limit"];
  else if (path === "/api/v1/events") { allowed = ["after", "once", "limit"]; kind = "events"; }
  else if (path === "/api/v1/analysis/context") allowed = ["kind", "sessionIds", "cycleId", "sourceMode", "comparisonSpecId", "baselineSessionId", "adaptiveSessionId"];
  else if (path === "/api/v1/analysis/reports") allowed = ["sessionId", "cycleId", "limit"];
  else if (/^\/api\/v1\/analysis\/reports\/[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$/.test(path)) allowed = [];
  else {
    const match = /^\/api\/v1\/(sessions|cycles|evidence)\/([^/]+)(?:\/(metrics|export))?$/.exec(path);
    if (!match) return null;
    let id: string; try { id = decodeURIComponent(match[2]!); } catch { return null; }
    if (!/^[A-Za-z0-9][A-Za-z0-9_.:-]{0,119}$/.test(id)) return null;
    const collection = match[1], suffix = match[3];
    if (collection === "sessions" && suffix === "metrics") allowed = ["includeSimulation"];
    else if (collection === "sessions" && suffix === "export") { allowed = ["format"]; kind = "export"; }
    else if (collection === "cycles" && !suffix) allowed = [];
    else if (collection === "evidence" && !suffix) { allowed = []; kind = "evidence"; }
    else return null;
    path = `/api/v1/${collection}/${encodeURIComponent(id)}${suffix ? `/${suffix}` : ""}`;
  }
  const seen = new Map<string, number>();
  for (const [key, value] of url.searchParams) {
    const maximum = path === "/api/v1/analysis/context" && key === "sessionIds" ? 2 : 1;
    const count = (seen.get(key) ?? 0) + 1;
    if (!allowed.includes(key) || count > maximum || value.length > 4000) return null;
    seen.set(key, count);
  }
  return { path, query: url.searchParams, kind };
}
function observeAbort<T>(operation: Promise<T>, signal: AbortSignal): Promise<T> {
  if (signal.aborted) { void operation.catch(() => {}); return Promise.reject(signal.reason); }
  let onAbort: () => void;
  const stopped = new Promise<never>((_, reject) => {
    onAbort = () => reject(signal.reason); signal.addEventListener("abort", onAbort, { once: true });
  });
  return Promise.race([operation, stopped]).finally(() => signal.removeEventListener("abort", onAbort!));
}
/** Fixed upstream and exact write intents; browser credentials are never forwarded. */
export function createStationProxy(options: StationProxyOptions): Middleware {
  const origin = new URL(options.upstreamOrigin);
  if (!["http:", "https:"].includes(origin.protocol) || origin.username || origin.password || origin.pathname !== "/" || origin.search || origin.hash)
    throw new TypeError("Station origin must be an HTTP(S) origin.");
  const fetcher = options.fetch ?? globalThis.fetch;
  const requestTimeout = options.requestTimeoutMs ?? 15_000, eventIdle = options.eventIdleTimeoutMs ?? 45_000;
  if (![requestTimeout, eventIdle].every(n => Number.isSafeInteger(n) && n > 0)) throw new TypeError("Invalid proxy timeout.");
  return (req, res, next) => {
    const raw = req.originalUrl ?? req.url ?? "";
    if (!(raw === "/api" || raw.startsWith("/api/") || raw.startsWith("/api?"))) { next(); return; }
    const write = req.method === "POST" && routeFor(raw, true) !== null;
    if (req.method !== "GET" && !write) { res.setHeader("Allow", "GET"); fail(res, 405, "Only reads, audited reviews and explicit evidence analysis are available."); return; }
    const route = routeFor(raw, write);
    if (!route) { fail(res, 404, "This station read endpoint is unavailable through the dashboard."); return; }
    if (!write && (req.headers["transfer-encoding"] || (req.headers["content-length"] && req.headers["content-length"] !== "0"))) {
      fail(res, 400, "Station read requests must not contain a body."); return;
    }
    if (write && (req.headers["x-morph-intent"] !== route.intent ||
      req.headers["content-type"]?.split(";", 1)[0]?.trim().toLowerCase() !== "application/json")) {
      fail(res, 415, "The matching explicit JSON request intent is required."); return;
    }
    if (write && req.headers["content-length"] && (!/^\d+$/.test(req.headers["content-length"]) || Number(req.headers["content-length"]) > 65536)) {
      fail(res, 413, "Request exceeds the allowed size."); return;
    }
    const resumed = req.headers["last-event-id"];
    if (resumed !== undefined && (route.kind !== "events" || typeof resumed !== "string" || !/^\d+$/.test(resumed) || !Number.isSafeInteger(Number(resumed)))) {
      fail(res, 400, "Invalid station event cursor."); return;
    }
    const upstream = new URL(route.path, origin); upstream.search = route.query.toString();
    const control = new AbortController(); let timedOut = false; let timer: ReturnType<typeof setTimeout> | undefined;
    const arm = (ms: number) => { clearTimeout(timer); timer = setTimeout(() => { timedOut = true; control.abort(); }, ms); };
    const disconnected = () => control.abort(); res.once("close", disconnected); req.once("aborted", disconnected); arm(requestTimeout);
    void (async () => {
      let reader: ReadableStreamDefaultReader<Uint8Array> | undefined;
      try {
        let requestBody: string | undefined;
        if (write) {
          const chunks: Buffer[] = []; let bytes = 0;
          const readBody = async () => {
            for await (const chunk of req) {
              const buffer = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
              bytes += buffer.length;
              if (bytes > 65536) { fail(res, 413, "Request exceeds the allowed size."); return false; }
              chunks.push(buffer);
            }
            return true;
          };
          if (!await observeAbort(readBody(), control.signal)) return;
          try { requestBody = new TextDecoder('utf-8', { fatal: true }).decode(Buffer.concat(chunks));
            const value: unknown = JSON.parse(requestBody); if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error(); }
          catch { fail(res, 400, "A JSON request object is required."); return; }
        }
        let token: string;
        try { token = await observeAbort(Promise.resolve().then(() => options.getToken()), control.signal); }
        catch (error) {
          if (control.signal.aborted) throw error;
          fail(res, 503, "The station token is unavailable. Configure the server token source."); return;
        }
        if (typeof token !== "string" || token.length < 32 || token.length > 4096 || !/^[!-~]+$/.test(token)) {
          fail(res, 503, "The station token is unavailable. Configure the server token source."); return;
        }
        const expected = route.kind === "events" ? ["text/event-stream"] : route.kind === "evidence" ?
          ["image/png", "image/jpeg", "application/json", "text/plain"] :
          route.kind === "export" && route.query.get("format") === "csv" ? ["text/csv"] : ["application/json"];
        const headers: Record<string, string> = { Authorization: `Bearer ${token}`, Accept: expected.join(",") };
        if (typeof resumed === "string") headers["Last-Event-ID"] = resumed;
        if (write) { headers["Content-Type"] = "application/json"; headers["X-Morph-Intent"] = route.intent!; }
        const response = await observeAbort(fetcher(upstream, { method: write ? "POST" : "GET", body: requestBody, headers, signal: control.signal,
          redirect: "error", credentials: "omit", cache: "no-store" }), control.signal);
        const errorResponse = response.status >= 400 && response.status <= 599;
        if (response.status !== 200 && !(route.intent === "evidence-analysis" && response.status === 202) && !errorResponse) {
          void response.body?.cancel().catch(() => {});
          fail(res, response.status >= 400 && response.status <= 599 ? response.status : 502, `Station request failed (HTTP ${response.status}).`); return;
        }
        const type = (response.headers.get("Content-Type") ?? "").split(";", 1)[0]!.trim().toLowerCase();
        if (errorResponse && type !== 'application/json') {
          void response.body?.cancel().catch(() => {});
          fail(res, response.status, `Station request failed (HTTP ${response.status}).`); return;
        }
        if (!response.body || !(errorResponse ? type === 'application/json' : expected.includes(type))) {
          void response.body?.cancel().catch(() => {}); fail(res, 502, "The station returned an unexpected response type."); return;
        }
        res.statusCode = response.status;
        res.setHeader("Content-Type", type + (type.startsWith("text/") || type === "application/json" ? "; charset=utf-8" : ""));
        res.setHeader("Cache-Control", "no-store"); res.setHeader("X-Content-Type-Options", "nosniff");
        if (route.kind === "export") res.setHeader("Content-Disposition", `attachment; filename="morph-session-export.${type === "text/csv" ? "csv" : "json"}"`);
        if (route.kind === "events" && !errorResponse) { res.setHeader("X-Accel-Buffering", "no"); res.flushHeaders(); arm(eventIdle); }
        reader = response.body.getReader(); let size = 0;
        const limit = (route.kind === "export" ? 64 : route.kind === "evidence" ? 5 : 16) * 1024 * 1024;
        while (true) {
          const part = await observeAbort(reader.read(), control.signal); if (part.done) break;
          if (route.kind === "events") arm(eventIdle);
          else { size += part.value.byteLength; if (size > limit) throw new Error("Station response exceeded its size limit."); }
          if (!res.write(part.value)) await observeAbort(new Promise<void>(resolve => res.once("drain", resolve)), control.signal);
        }
        res.end();
      } catch {
        if (!res.destroyed) fail(res, timedOut ? 504 : 502, timedOut ? "The station request timed out." : "The station is unavailable.");
      } finally {
        clearTimeout(timer); res.removeListener("close", disconnected); req.removeListener("aborted", disconnected); control.abort();
        if (reader) { void reader.cancel().catch(() => {}); try { reader.releaseLock(); } catch { /* Cancel may still settle. */ } }
      }
    })();
  };
}
