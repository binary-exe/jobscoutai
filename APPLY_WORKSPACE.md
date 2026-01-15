# Apply Workspace V1 - Implementation Status

## ✅ Phase 0: Foundation (COMPLETED)

### Frontend Routes
- ✅ `/apply` - Main Apply Workspace page with split-pane layout
- ✅ `/apply/history` - Application history dashboard
- ✅ `/pricing` - Pricing page with Free/Pro plans
- ✅ Navigation updated in Header component

### Database Schema
- ✅ Created `apply_schema.sql` with all required tables:
  - `users` - User accounts and subscription info
  - `resume_versions` - Resume storage with caching
  - `job_targets` - Parsed job descriptions
  - `trust_reports` - Scam/ghost/staleness analysis
  - `apply_packs` - Generated tailored content
  - `applications` - Application tracker
  - `usage_ledger` - Quota tracking
  - `entitlements` - Feature access control

### Backend API
- ✅ `/api/v1/apply/job/parse` - Parse job URL or text
- ✅ `/api/v1/apply/job/{id}/trust` - Generate trust report
- ✅ `/api/v1/apply/pack/generate` - Generate apply pack (with quota checking)
- ✅ `/api/v1/apply/pack/{id}` - Get apply pack
- ✅ `/api/v1/apply/history` - Get user's apply packs
- ✅ `/api/v1/apply/quota` - Get quota status

### Storage Layer
- ✅ `backend/app/storage/apply_storage.py` - All CRUD operations
- ✅ Resume hashing for caching
- ✅ Job target hashing for caching
- ✅ Apply pack hashing (resume + job combination)
- ✅ Usage tracking and quota checking

## 🚧 Next Steps

### Phase 1: Job Intake + Parsing (TODO)
1. **URL Fetching**
   - Implement `fetch_job_page()` to download HTML
   - Sanitize and store HTML in `job_targets`
   - Handle errors (404, timeout, etc.)

2. **JSON-LD Extraction**
   - Parse `application/ld+json` scripts
   - Extract `JobPosting` schema.org data
   - Map to our schema (title, company, location, salary, etc.)

3. **HTML Parsing Fallback**
   - Use BeautifulSoup to extract job details
   - Look for common patterns (h1 for title, meta tags, etc.)
   - LLM normalization for unstructured text

4. **Editable Fields UI**
   - Show extracted fields in frontend
   - Allow user to edit/correct
   - Save updates to `job_targets`

### Phase 2: Trust Report Engine (TODO)
1. **Scam Risk Signals**
   - Check for WhatsApp/Telegram in apply links
   - Detect upfront fee requests
   - Suspicious email domains
   - Generic company info

2. **Ghost-Likelihood Signals**
   - Missing posting dates
   - Generic job descriptions
   - No company website
   - Broken apply links

3. **Staleness Signals**
   - Parse posting date from page
   - Check for "expired" indicators
   - Broken apply links
   - Missing dates

4. **Trust Report UI**
   - Display risk levels with color coding
   - Show reasons for each signal
   - Include disclaimers

### Phase 3: Resume Intake + Apply Pack (TODO)
1. **Resume Upload**
   - PDF parsing (use `pdfplumber` or similar)
   - DOCX parsing (use `python-docx`)
   - Text extraction and cleaning

2. **Resume Analysis (Pass A)**
   - Extract skills (structured JSON)
   - Determine seniority level
   - Extract evidence bullets
   - Cache by resume hash

3. **Job Analysis (Pass A)**
   - Extract must-haves
   - Extract keywords
   - Generate role rubric
   - Cache by job hash

4. **Apply Pack Generation (Pass B)**
   - Tailored summary (match resume to job)
   - Tailored bullets (rewrite resume bullets)
   - Short cover note
   - ATS checklist + keyword coverage

5. **Anti-Generic Guardrails**
   - Ensure content is specific to job
   - Avoid generic phrases
   - Include quantified achievements

### Phase 4: DOCX Export + Tracker (TODO)
1. **DOCX Generation**
   - Use `python-docx` to create documents
   - Template for tailored resume
   - Template for cover note
   - Paid feature only

2. **Application Tracker**
   - CRUD operations for applications
   - Status management (applied, interview, offer, rejected)
   - Notes and reminders
   - Dashboard view

3. **History Dashboard**
   - List all apply packs
   - Filter by date, company, status
   - Quick actions (copy, download, track)

### Phase 5: Freemium Gating + Paddle Payments (TODO)
1. **Quota Enforcement**
   - Middleware to check quotas
   - Show upgrade modal on limit
   - Track usage in real-time

2. **Paddle Integration**
   - Set up Paddle account
   - Create products (Free, Pro)
   - Implement checkout flow
   - Webhook handler for subscription events

3. **Webhook Events**
   - `subscription.created` → Upgrade to paid
   - `subscription.updated` → Update status
   - `subscription.cancelled` → Revert to free at period end
   - `payment.succeeded` → Extend subscription
   - `payment.failed` → Handle gracefully

4. **Account Page**
   - Show current plan
   - Display usage stats
   - "Manage subscription" link (Paddle hosted portal)
   - Invoice history

## Database Migration

To apply the schema, run the SQL in `backend/app/storage/apply_schema.sql` in your Supabase SQL Editor.

## Environment Variables (To Add)

```bash
# Paddle
JOBSCOUT_PADDLE_VENDOR_ID=your_vendor_id
JOBSCOUT_PADDLE_API_KEY=your_api_key
JOBSCOUT_PADDLE_PUBLIC_KEY=your_public_key
JOBSCOUT_PADDLE_WEBHOOK_SECRET=your_webhook_secret
```

## API Client (Frontend)

Create `frontend/lib/apply-api.ts` to interact with the backend:

```typescript
const API_URL = process.env.NEXT_PUBLIC_API_URL;

export async function parseJob(jobUrl?: string, jobText?: string) {
  // POST /api/v1/apply/job/parse
}

export async function generateTrustReport(jobTargetId: string) {
  // POST /api/v1/apply/job/{id}/trust
}

export async function generateApplyPack(resumeText: string, jobUrl?: string, jobText?: string) {
  // POST /api/v1/apply/pack/generate
}

export async function getQuota() {
  // GET /api/v1/apply/quota
}
```

## User Management

Currently using anonymous users (UUID in `X-User-ID` header). For production, consider:
- Email-based authentication
- Session management
- OAuth (Google, GitHub)

## Cost Considerations

- **Caching**: Resume/job/apply pack hashing reduces redundant LLM calls
- **Quotas**: Free plan limits to 2 apply packs/month
- **AI Usage**: Only use AI when `use_ai=true` (optional for basic parsing)

## Testing

1. Test job parsing with various job board URLs
2. Test trust report with known scam/ghost job examples
3. Test quota enforcement (free vs paid)
4. Test Paddle webhooks (use Paddle sandbox)
