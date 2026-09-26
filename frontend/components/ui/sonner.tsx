"use client"

import { Toaster as Sonner, type ToasterProps } from "sonner"
import { CircleCheckIcon, InfoIcon, TriangleAlertIcon, OctagonXIcon, Loader2Icon } from "lucide-react"

// `theme="light"` en dur : aucun `<ThemeProvider>` n'est monté dans l'arbre et
// `globals.css` le dit — « Mode sombre opt-in via la classe `.dark` (jamais
// posée) ». `useTheme` rendait donc systématiquement son défaut. Le jour où le
// mode sombre est branché pour de vrai, `next-themes` revient : ce qu'on retire
// est un provider absent, pas la capacité.
const Toaster = ({ ...props }: ToasterProps) => {
  return (
    <Sonner
      theme="light"
      className="toaster group"
      icons={{
        success: (
          <CircleCheckIcon className="size-4" />
        ),
        info: (
          <InfoIcon className="size-4" />
        ),
        warning: (
          <TriangleAlertIcon className="size-4" />
        ),
        error: (
          <OctagonXIcon className="size-4" />
        ),
        loading: (
          <Loader2Icon className="size-4 animate-spin" />
        ),
      }}
      style={
        {
          "--normal-bg": "var(--popover)",
          "--normal-text": "var(--popover-foreground)",
          "--normal-border": "var(--border)",
          "--border-radius": "var(--radius)",
          // `richColors` garderait sinon la palette de Sonner, sous 4,5:1 en
          // succès et en erreur (#1030). `info` n'a pas de token TCN et
          // n'est pas utilisée.
          "--success-bg": "var(--tcn-success-bg)",
          "--success-text": "var(--tcn-success-text)",
          "--success-border": "var(--tcn-success-border)",
          "--error-bg": "var(--tcn-danger-bg)",
          "--error-text": "var(--tcn-danger-text)",
          "--error-border": "var(--tcn-danger-border)",
          "--warning-bg": "var(--tcn-warning-bg)",
          "--warning-text": "var(--tcn-warning-text)",
          "--warning-border": "var(--tcn-warning-border)",
        } as React.CSSProperties
      }
      toastOptions={{
        classNames: {
          toast: "cn-toast",
        },
      }}
      {...props}
    />
  )
}

export { Toaster }
