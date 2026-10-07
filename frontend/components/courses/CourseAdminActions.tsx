"use client";
import dynamic from "next/dynamic";
import { useHydratedSession } from "@/lib/queries/auth";
import type { CourseBrief } from "@/lib/types";

// Le panneau tire quatre fenêtres du back-office : chargé seulement une fois un
// pouvoir établi, il ne pèse rien sur la fiche d'un visiteur ordinaire.
const CourseAdminPanel = dynamic(() =>
  import("./CourseAdminPanel").then((module) => module.CourseAdminPanel),
);

const POWERS = ["courses:write", "courses:delete", "quality:override"];

export function CourseAdminActions(props: { course: CourseBrief; total: number; tcnCount: number }) {
  const permissions = useHydratedSession().data?.permissions ?? [];
  if (!POWERS.some((power) => permissions.includes(power))) return null;
  return <CourseAdminPanel {...props} permissions={permissions} />;
}
