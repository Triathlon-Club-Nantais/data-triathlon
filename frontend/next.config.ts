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
  // En-têtes de sécurité (#396, constat A05-2 de l'audit OWASP). Vercel posait
  // déjà HSTS et `x-robots-tag: noindex` ; tout le reste manquait, ce qui
  // laissait le back-office encadrable dans une iframe tierce — la seule
  // barrière contre un clickjacking sur les gestes destructifs étant le
  // `SameSite=Lax` du cookie de session.
  //
  // La CSP n'est **pas** ici : Next.js et PostHog demandent un `nonce`, c'est le
  // seul point du constat à coûter plus qu'une ligne, et il se traite à part.
  //
  // Ces en-têtes ne protègent que ce qui passe par Next : les deux backends
  // Render sont joignables directement, d'où le middleware jumeau dans
  // `backend/app/core/security_headers.py`.
  async headers() {
    return [
      {
        // Attrape-tout : `:path*` accepte le chemin vide, donc `/` en fait
        // partie. Les rewrites `/api/*` et `/ingest/*` aussi — c'est voulu.
        source: "/:path*",
        headers: [
          { key: "X-Frame-Options", value: "DENY" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          // Minimale au sens de l'audit : on ne refuse que ce dont l'app ne se
          // sert pas. Rien n'appelle `navigator.geolocation` (la carte n'affiche
          // que des épreuves géocodées côté serveur), ni caméra, ni micro. Le
          // presse-papiers, lui, n'est pas listé : `BenevoleAccessConfig` s'en
          // sert, et la politique par défaut l'autorise en même origine.
          {
            key: "Permissions-Policy",
            value: "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
          },
        ],
      },
    ];
  },
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${BACKEND_URL}/api/:path*` },
      // Proxy inverse PostHog — fait passer les événements client par Next.js
      // pour éviter les bloqueurs de pub. /static et /array pointent vers le
      // CDN d'assets ; tout le reste de /ingest va vers l'endpoint d'ingestion.
      {
        source: "/ingest/static/:path*",
        destination: "https://eu-assets.i.posthog.com/static/:path*",
      },
      {
        source: "/ingest/array/:path*",
        destination: "https://eu-assets.i.posthog.com/array/:path*",
      },
      {
        source: "/ingest/:path*",
        destination: "https://eu.i.posthog.com/:path*",
      },
    ];
  },
  // Requis pour que les requêtes API de PostHog (slash final) ne soient pas redirigées
  skipTrailingSlashRedirect: true,
};

export default nextConfig;
