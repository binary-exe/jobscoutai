# JobiQueue Saver (Chrome/Edge extension v1)

This extension lets users **save a job posting in 1 click** into the JobiQueue **Apply Workspace**.

Key constraint: **no server crawling** — the extension only uses the content the user already loaded in their browser.

## Features

- **Connect** by capturing the user’s Supabase session token from an active JobiQueue tab (best-effort).
- **Save job** from the current active tab (LinkedIn / Indeed / ATS pages) by extracting:
  - title, company, location (best-effort)
  - description text (best-effort)
  - job URL + apply URL (best-effort)
- Sends to backend: `POST /api/v1/apply/job/import` with `source="extension"`.

## Install (developer mode)

1. Open Chrome/Edge → Extensions
2. Enable **Developer mode**
3. Click **Load unpacked**
4. Select the `extension/` folder

## How to use

1. Open JobiQueue (`https://jobiqueue.com`) and log in.
2. With that tab active, open the extension popup and click **Connect**.
3. Go to a job detail page (LinkedIn / Indeed / ATS).
4. Open the extension popup and click **Save job**.
5. After saving, click **Open Apply Workspace →** to open the job in Apply Workspace and get a Trust Report + apply pack.

## Settings

- **API base** defaults to `https://jobscout-api.fly.dev/api/v1`
- **App base** defaults to `https://jobiqueue.com`

