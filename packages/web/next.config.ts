import type { NextConfig } from "next";

const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8001";

const config: NextConfig = {
  async rewrites() {
    return [
      { source: "/proxy/:path*", destination: `${apiBase}/:path*` },
    ];
  },
};

export default config;
