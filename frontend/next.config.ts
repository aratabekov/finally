import type { NextConfig } from "next";

/**
 * Production builds are a static export served by FastAPI, so every API call is
 * same-origin. `next dev` runs on its own port, so it proxies /api to the local
 * backend instead.
 */
const isDev = process.env.NODE_ENV === "development";
const backend = process.env.BACKEND_ORIGIN ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = isDev
  ? {
      async rewrites() {
        return [{ source: "/api/:path*", destination: `${backend}/api/:path*` }];
      },
    }
  : {
      output: "export",
      images: { unoptimized: true },
    };

export default nextConfig;
