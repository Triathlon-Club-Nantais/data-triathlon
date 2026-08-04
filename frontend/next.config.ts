import type { NextConfig } from "next";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8001";

const nextConfig: NextConfig = {
  // Build autonome pour l'image Docker (copie `.next/standalone` → `node server.js`).
  output: "standalone",
  // Next 16 bloque HMR par défaut pour toute origine dev qui n'est pas
  // `localhost`. `.dev-backend.json` publie 127.0.0.1 (cf.
  // `docs/dev-multi-worktree.md`) : sans autorisation, l'hydratation client
  // échoue et les toggles clients (sélecteurs, tabs…) restent inertes sur
  // cette origine.
  allowedDevOrigins: ["127.0.0.1"],
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${BACKEND_URL}/api/:path*` },
    ];
  },
};

export default nextConfig;
