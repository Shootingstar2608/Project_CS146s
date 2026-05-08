import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async redirects() {
    return [
      {
        source: "/",
        destination: "/papers",
        permanent: true,
      },
    ];
  },
};

export default nextConfig;
