"use client";
import Link from "next/link";
import type { ComponentProps } from "react";
import { useSession } from "@/lib/queries/auth";
import { ROLE, destinationVisible } from "./nav.config";

/** Le rail rend-il `href` à cette session ? Faux tant qu'elle n'est pas lue. */
export function useDestinationVisible(href: string): boolean {
  const { data: session } = useSession();
  const rank = session ? ROLE.CONNECTED : ROLE.ANON;
  return destinationVisible(href, new Set(session?.permissions ?? []), rank);
}

/** Lien vers une destination du rail, rendu seulement si le rail la montre. */
export function LienDestination({ href, ...props }: ComponentProps<typeof Link> & { href: string }) {
  return useDestinationVisible(href) ? <Link href={href} {...props} /> : null;
}
