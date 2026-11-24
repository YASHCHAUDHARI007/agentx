import type { NextConfig } from "next";

// A static export: `npm run build` writes plain HTML/JS/CSS to out/, which the Python service
// (server/app.py) serves next to its API. One process, one port, no Node.js in production.
const nextConfig: NextConfig = {
  output: "export",
  reactStrictMode: true,
  poweredByHeader: false,
  agentRules: false, // no generated AGENTS.md in the repo
};

export default nextConfig;
