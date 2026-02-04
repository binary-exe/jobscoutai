---
name: JobScoutAI Success Plan
overview: A comprehensive upgrade plan to increase JobScoutAI's success probability from 30-55% to 80%+ for reaching €1k MRR, based on consolidated recommendations from DeepSeek, Perplexity, and ChatGPT analyses.
todos:
  - id: auth-fix
    content: Fix authentication issues (Supabase config, header UX, magic link flow)
    status: completed
  - id: apply-mvp
    content: Complete Apply Workspace MVP (job parsing, Trust Report, Apply Pack generation)
    status: completed
  - id: analytics
    content: Implement analytics tracking (PostHog/Mixpanel) for conversion funnel
    status: completed
  - id: pricing-tiers
    content: Implement tiered pricing (Free, Pro €9, Pro+ €19, Annual €79)
    status: completed
  - id: pack-topups
    content: Add pack top-up purchases (+25 packs for €5)
    status: completed
  - id: google-jobs
    content: Implement JobPosting structured data for Google Jobs eligibility
    status: completed
  - id: referral-system
    content: Build referral system (Give 10 packs, Get 10 packs)
    status: completed
  - id: programmatic-seo
    content: Create programmatic SEO pages (/remote-[role]-jobs, /remote-jobs-in-[country])
    status: completed
  - id: email-onboarding
    content: Set up 5-email onboarding drip sequence
    status: completed
  - id: activation-flow
    content: Optimize activation flow (first value in under 2 minutes)
    status: completed
  - id: retention-features
    content: Add retention features (weekly digest, saved searches, alerts)
    status: completed
  - id: community-launch
    content: Execute community launch (Reddit, HN, LinkedIn with Founder's Deal)
    status: completed
isProject: false
---

# JobScoutAI Success Probability Improvement Plan

Based on the consolidated analysis from DeepSeek, Perplexity, and ChatGPT, this plan addresses the critical gaps to maximize JobScoutAI's success probability.

---

## Current State Assessment

- **Success Probability**: 30-55% for €1k MRR (112 Pro subscribers)
- **Main Bottleneck**: Distribution, not COGS (unit economics are excellent with gpt-4o-mini)
- **Key Gaps**: Incomplete Apply Workspace, single pricing tier, no referral system, limited SEO

---

## Phase 1: Product Foundation (Week 1-2)

### 1.1 Complete Apply Workspace MVP

The Apply Workspace is the primary monetization feature but has incomplete functionality.

**Required completions in** [backend/app/api/apply.py](backend/app/api/apply.py):

- Ensure job parsing from URL works reliably
- Trust Report generation is robust
- Apply Pack output includes: tailored cover letter + resume tweaks + trust signals

**Frontend improvements in** [frontend/app/apply/page.tsx](frontend/app/apply/page.tsx):

- One-click flow: Select job → Paste resume → Get Apply Pack in under 2 minutes
- Clear preview of Apply Pack before paywall
- DOCX export working for Pro users

### 1.2 Fix Authentication Issues

Current auth redirects to localhost and has UX issues (already identified).

**Required fixes**:

- Supabase Site URL configured to `https://jobscoutai.vercel.app`
- Consolidated header (user dropdown vs separate Account/Profile/Login)
- Smooth magic link flow

### 1.3 Implement Analytics

Add event tracking for conversion funnel:

- Sign-up rate
- "Created first Apply Pack" rate
- Upgrade prompt views
- Paid conversions
- Retention metrics

**Implementation**: Add PostHog or Mixpanel integration in [frontend/lib/](frontend/lib/).

---

## Phase 2: Pricing Strategy Upgrade (Week 2-3)

### 2.1 Implement Tiered Pricing

Update [frontend/app/pricing/page.tsx](frontend/app/pricing/page.tsx) and backend:


| Tier   | Price     | Features                                             |
| ------ | --------- | ---------------------------------------------------- |
| Free   | €0        | 2 Apply Packs/month, Trust Report, 5 tracked apps    |
| Pro    | €9/month  | 30 Apply Packs/month, Unlimited tracker, DOCX export |
| Pro+   | €19/month | 100 Apply Packs, Priority queue, Advanced analytics  |
| Annual | €79/year  | Pro features (save 27%)                              |


### 2.2 Add Pack Top-ups

Implement one-time purchase option:

- "+25 Apply Packs for €5" (one-time)
- Reduces friction for "bursty" job seekers

### 2.3 Clarify Value Proposition

Add to pricing page:

> "1 Apply Pack = tailored cover letter + resume tweaks + trust report + saved to tracker"

Show time-saved calculation (e.g., "Save 45 minutes per application").

---

## Phase 3: Distribution Engines (Week 3-5)

### 3.1 Engine A: Google Jobs + SEO

**Implement JobPosting structured data** for job detail pages in [frontend/app/job/[id]/page.tsx](frontend/app/job/[id]/page.tsx):

```json
{
  "@context": "https://schema.org/",
  "@type": "JobPosting",
  "title": "...",
  "hiringOrganization": {...},
  "jobLocation": {...},
  "datePosted": "...",
  "validThrough": "...",
  "description": "..."
}
```

**Create programmatic SEO pages**:

- `/remote-[role]-jobs` (e.g., `/remote-python-developer-jobs`)
- `/remote-jobs-in-[country]`
- `/company/[name]/remote-jobs`

### 3.2 Engine B: Referral Loop

Implement Dropbox-style referral system:

- "Give 10 packs, Get 10 packs" when referee creates first Apply Pack
- Shareable referral link in user dashboard
- Track referrals in [backend/app/storage/](backend/app/storage/)

### 3.3 Engine C: Community Launch

**Target communities** (Reddit, HN, LinkedIn):

- r/remotejs, r/cscareerquestionsEU, r/forhire
- Hacker News "Show HN" post focusing on technical architecture
- LinkedIn posts with case studies

**Launch offer**: "Founder's Deal" - €59/year for first 500 customers

---

## Phase 4: Activation Optimization (Week 4-5)

### 4.1 Instant Value Flow

Redesign onboarding to deliver value in under 2 minutes:

```
Landing → Select 1 job → Paste resume/LinkedIn → 
Get FREE Apply Pack preview → Paywall for DOCX/more packs
```

### 4.2 Email Onboarding Sequence

5-email drip for free users:

1. Welcome + how to create first Apply Pack
2. Case study: user who got interview
3. Reminder before hitting 2-pack limit
4. Launch offer reminder
5. Feedback request

---

## Phase 5: Retention Countermeasures (Week 5-6)

### 5.1 Combat Job-Seeker Churn

Job seekers stop paying once they land a job. Counter with:

- **Weekly job-matching digest** based on saved searches
- **Interview prep content** included in Pro (value after applying)
- **Annual plan as default** option (reduces churn pressure)
- **Application success tracking** with insights

### 5.2 Ongoing Value Features

- Saved searches with email alerts
- Application status tracking with reminders
- Salary negotiation tips after successful applications

---

## Success Metrics and KPIs


| Metric                    | Target              | Measurement         |
| ------------------------- | ------------------- | ------------------- |
| Website Visitors          | 5,000+/week         | Analytics           |
| Free Sign-ups             | 500+/week           | Database            |
| Free-to-Paid Conversion   | 10%+                | Payment system      |
| Customer Acquisition Cost | less than €30       | Ad spend / new paid |
| Monthly Recurring Revenue | €4,500+ (500 users) | Paddle              |
| User Churn (Monthly)      | less than 5%        | Payment system      |


---

## Risk Mitigations


| Risk                           | Mitigation                                                            |
| ------------------------------ | --------------------------------------------------------------------- |
| Apply Workspace not compelling | Phase 1 early adopter feedback; be ready to add one-click apply       |
| High CAC in paid channels      | Start tiny (€10/day); focus on organic/content                        |
| Low free-to-paid conversion    | Optimize "aha moment"; test pricing page layouts                      |
| Competitor response            | Emphasize unique combo: curated board + AI tailoring + scam detection |


---

## Implementation Priority Order

1. **Critical (Week 1)**: Complete Apply Workspace MVP, fix auth issues
2. **High (Week 2)**: Implement analytics, add annual pricing
3. **High (Week 3)**: Google Jobs structured data, referral system
4. **Medium (Week 4)**: Tiered pricing, pack top-ups, email sequences
5. **Medium (Week 5)**: Programmatic SEO pages, community launch
6. **Ongoing**: Retention features, content marketing

---

## Expected Outcome

With full execution of this plan:

- **Success probability for €1k MRR**: Increases from 30-55% to **75-85%**
- **Timeline**: 6-8 weeks to €1k MRR
- **Path to €10k MRR**: Viable within 6-12 months with sustained execution

