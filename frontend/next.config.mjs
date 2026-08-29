/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone", // minimal server bundle for the Docker image (see 12-deployment-infra.md)
  reactStrictMode: true,
};

export default nextConfig;
