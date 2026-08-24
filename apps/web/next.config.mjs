/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    // Server-side only: the browser calls same-origin /api/v1/* and Next
    // proxies it to the backend. No browser-facing localhost URLs.
    const backend = process.env.CF_API_URL ?? "http://127.0.0.1:8001";
    return [
      {
        source: "/api/v1/:path*",
        destination: `${backend}/api/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;
