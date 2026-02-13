# UI/UX Reference (JobScout)

## Global styles to respect

See `frontend/app/globals.css`:

- uses CSS variables for theme tokens (light/dark)
- focus-visible ring is already defined globally; don’t remove it
- prefers subtle borders, muted backgrounds, rounded corners

## Common page patterns

- **Home**: hero + search bar + stats + CTA + filters + job list
- **Job detail**: `max-w-3xl`, structured data (`application/ld+json`), “Apply” primary CTA + “Open in Apply Workspace” secondary
- **Apply Workspace**: multi-step flow with many async states; guard against loops; always show actionable errors

## Component conventions

- Buttons:
  - primary: `bg-primary text-primary-foreground hover:bg-primary/90`
  - neutral primary: `bg-foreground text-background hover:bg-foreground/90`
  - secondary: `border border-border hover:bg-muted`
- Cards:
  - `rounded-xl border border-border bg-card p-6`
- Skeletons:
  - `animate-pulse` with `bg-muted`
