---
name: ui-ux
description: UI/UX standards for JobScout (clean Tailwind UI, accessible interactions, consistent states, minimal friction). Use when designing new screens/components, polishing layout, or reviewing UX regressions.
---

# UI/UX (JobScout)

## Product UX goals

- **Fast to value**: user searches, triggers scrape, sees results quickly.
- **Trust**: clear status (loading/scraping), explain errors, no “silent failures”.
- **Low clutter**: prefer a few strong UI elements over many knobs.

## Visual system (match existing style)

- Use Tailwind + CSS variables (`bg-background`, `text-foreground`, `border-border`, `text-muted-foreground`).
- Common layout patterns:
  - page skeleton: `<Header />` + `<main className="flex-1">` + `<Footer />`
  - container: `container mx-auto max-w-5xl px-4` (or `max-w-3xl` on detail pages)
- Common surfaces:
  - cards: `rounded-xl border border-border bg-card p-6`
  - subtle sections: `border-b border-border/40` and `bg-muted/30` gradients

## UI consistency rules (don’t skip states)

- Always implement:
  - **Loading** state (skeleton/spinner/text)
  - **Empty** state (what happened + next action)
  - **Error** state (plain language + recovery action)
- Keep spacing consistent and typography readable.
- Prefer existing component patterns in `frontend/components/` over new one-offs.

## Accessibility checklist

- Interactive elements are keyboard reachable and have visible focus styles.
- Inputs have labels (or `aria-label`).
- Don’t rely on color alone to convey state.

## Copy rules

- Use short, action-oriented labels (“Scrape now”, “Try again”, “Save search”).
- When blocked (auth/config), say what’s missing and how to fix it.

## UX anti-footguns (common mistakes)

- Don’t hide failures: surface backend `detail` in a safe, user-readable way.
- Don’t create infinite retry loops (Apply workspace uses “attempt once” guards for auto-import).
- Don’t make auth-only pages appear usable when the user is logged out: redirect or show a clear login CTA.

## Additional resources

- Deeper UI patterns: [reference.md](reference.md)
- Copy/paste empty/loading/error patterns: [examples.md](examples.md)
