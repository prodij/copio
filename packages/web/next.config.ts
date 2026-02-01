import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    return {
      // These rewrites are checked after pages/public files
      // but before dynamic routes
      beforeFiles: [],
      afterFiles: [],
      // Fallback rewrites only apply if no page/API route matches
      fallback: [
        {
          source: '/api/:path*',
          destination: `${process.env.API_URL || 'http://localhost:8000/api/v1'}/:path*`,
        },
      ],
    };
  },
};

export default nextConfig;
