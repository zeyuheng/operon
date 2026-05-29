import type { NextConfig } from "next";

const backendUrl = process.env.OPERON_BACKEND_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/market-scout/:path*",
        destination: `${backendUrl}/market-scout/:path*`,
      },
      {
        source: "/health",
        destination: `${backendUrl}/health`,
      },
      {
        source: "/docs",
        destination: `${backendUrl}/docs`,
      },
      {
        source: "/openapi.json",
        destination: `${backendUrl}/openapi.json`,
      },
    ];
  },
};

export default nextConfig;
