import type { Metadata } from "next";
import { AccountPage } from "@/components/auth/AccountPage";
import { PageShell } from "@/components/layout/PageShell";
import { Eyebrow } from "@/components/tcn";

export const metadata: Metadata = { title: "Mon compte" };

export default function MonComptePage() {
  return (
    <PageShell form>
      <div style={{ marginBottom: 26 }}>
        <Eyebrow>Compte</Eyebrow>
        <h1 style={{ fontFamily: "var(--tcn-font-display)", fontSize: "clamp(28px, 5vw, 40px)", fontWeight: 400, color: "var(--tcn-ink)", lineHeight: 1, margin: 0, marginTop: 6 }}>
          Mon compte
        </h1>
      </div>
      <AccountPage />
    </PageShell>
  );
}
