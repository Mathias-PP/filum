/**
 * Same-origin proxy for the FastAPI backend.
 *
 * Why: when the SPA calls the backend directly (e.g. https://api.railway.app
 * from https://filum.app), the session cookie set by the backend is a
 * THIRD-PARTY cookie from the browser's point of view. Mobile Safari and
 * iOS WebKit (which Chrome iOS also uses) block third-party cookies by
 * default via ITP, so the OAuth state and session cookies are silently
 * dropped — the symptom is "Echec de l'authentification" only on mobile.
 *
 * Routing /api/* through this SvelteKit endpoint makes every backend call
 * first-party (same origin as the SPA), so cookies just work everywhere.
 *
 * Configuration: set the `BACKEND_URL` environment variable on Vercel
 * (server-side; NOT `PUBLIC_BACKEND_URL`) to the backend host, e.g.
 * `https://filum-api.up.railway.app`. In dev, defaults to localhost:8000
 * which mirrors the existing vite proxy.
 *
 * Notes:
 * - `redirect: 'manual'` so the OAuth 302/303 hops surface to the browser
 *   unchanged (Google → callback → frontend redirect).
 * - Set-Cookie headers from the backend are forwarded as-is. Since the
 *   response goes to the browser FROM the proxy origin, the cookie attaches
 *   to the proxy origin (first-party), regardless of the backend's host.
 * - The `host` request header is stripped so `fetch` sets the correct one
 *   for the upstream backend.
 */

import { env } from '$env/dynamic/private';
import type { RequestHandler } from './$types';

const BACKEND_URL = (env.BACKEND_URL ?? '').replace(/\/$/, '') || 'http://localhost:8000';

// Hop-by-hop headers (RFC 7230 §6.1) — must not be forwarded by a proxy.
const HOP_BY_HOP = new Set([
  'connection',
  'keep-alive',
  'proxy-authenticate',
  'proxy-authorization',
  'te',
  'trailers',
  'transfer-encoding',
  'upgrade',
]);

const proxy: RequestHandler = async ({ request, params, url }) => {
  const upstreamPath = params.path ?? '';
  const upstream = `${BACKEND_URL}/api/${upstreamPath}${url.search}`;

  const headers = new Headers();
  for (const [name, value] of request.headers) {
    const lower = name.toLowerCase();
    if (HOP_BY_HOP.has(lower)) continue;
    if (lower === 'host') continue;
    headers.set(name, value);
  }
  // Tell the FastAPI backend what public origin it is being reached from so
  // it can build the correct OAuth redirect_uri (see _public_callback_url in
  // apps/backend/app/api/v1/endpoints/auth.py). Without this, Google would
  // be told to redirect to Railway directly, bypassing this proxy on the
  // return trip and posting the session cookie on the wrong host.
  const publicHost = url.host;
  const publicProto = url.protocol.replace(':', '');
  if (!headers.has('x-forwarded-host')) headers.set('x-forwarded-host', publicHost);
  if (!headers.has('x-forwarded-proto')) headers.set('x-forwarded-proto', publicProto);

  const hasBody = request.method !== 'GET' && request.method !== 'HEAD';
  const body = hasBody ? await request.arrayBuffer() : undefined;

  const upstreamResp = await fetch(upstream, {
    method: request.method,
    headers,
    body,
    redirect: 'manual',
  });

  const respHeaders = new Headers();
  for (const [name, value] of upstreamResp.headers) {
    const lower = name.toLowerCase();
    if (HOP_BY_HOP.has(lower)) continue;
    if (lower === 'content-encoding' || lower === 'content-length') continue;
    respHeaders.append(name, value);
  }

  return new Response(upstreamResp.body, {
    status: upstreamResp.status,
    statusText: upstreamResp.statusText,
    headers: respHeaders,
  });
};

export const GET = proxy;
export const POST = proxy;
export const PUT = proxy;
export const PATCH = proxy;
export const DELETE = proxy;
export const OPTIONS = proxy;
export const HEAD = proxy;
