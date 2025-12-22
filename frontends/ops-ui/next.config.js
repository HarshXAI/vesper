/** @type {import('next').NextConfig} */
const nextConfig = {
    output: 'standalone',
    experimental: {
        serverActions: {
            bodySizeLimit: '2mb',
        },
    },
    async rewrites() {
        return [
            {
                source: '/api/v1/:path*',
                destination: `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/v1/:path*`,
            },
            {
                source: '/grafana/:path*',
                destination: `${process.env.GRAFANA_URL || 'http://localhost:3000'}/:path*`,
            },
        ];
    },
    async headers() {
        return [
            {
                source: '/grafana/:path*',
                headers: [
                    { key: 'X-Frame-Options', value: 'SAMEORIGIN' },
                ],
            },
        ];
    },
};

module.exports = nextConfig;
