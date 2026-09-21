const API = process.env.API || "http://localhost:8000";

module.exports = {
  // Off because this server proxies an SSE endpoint. Chrome's gzip decoder buffers
  // a compressed event stream to completion, which silently turns streaming back
  // into a single chunk. In production, terminate TLS and compress static assets at
  // the CDN/reverse proxy instead, exempting /api/chat/stream there.
  compress: false,

  // The browser only ever talks to its own origin; Next proxies to the backend.
  // Keeps CORS out of the picture and stops the API host being baked into the bundle.
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API}/:path*` }];
  },
};
