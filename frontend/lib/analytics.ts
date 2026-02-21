/**
 * PostHog Analytics Integration
 * 
 * Tracks conversion funnel events for JobiQueue:
 * - Sign-up rate
 * - First Apply Pack created
 * - Upgrade prompt views
 * - Paid conversions
 * - Retention metrics
 * 
 * Setup:
 * 1. Create account at https://app.posthog.com (US) or https://eu.posthog.com (EU)
 * 2. Get Project API Key from Project Settings
 * 3. Set NEXT_PUBLIC_POSTHOG_KEY in Vercel env vars
 * 4. If EU region, also set NEXT_PUBLIC_POSTHOG_HOST=https://eu.posthog.com
 */

import posthog from 'posthog-js';
import { supabase, isSupabaseConfigured } from '@/lib/supabase';

// Initialize PostHog only on client side
let initialized = false;
let initializationFailed = false;

export function initAnalytics() {
  if (typeof window === 'undefined') return;
  if (initialized || initializationFailed) return;
  
  const posthogKey = process.env.NEXT_PUBLIC_POSTHOG_KEY;
  const posthogHost = process.env.NEXT_PUBLIC_POSTHOG_HOST || 'https://us.i.posthog.com';
  
  if (!posthogKey) {
    // Silently skip if not configured - this is expected in development
    if (process.env.NODE_ENV === 'development') {
      console.log('[Analytics] PostHog not configured (dev mode)');
    }
    initializationFailed = true;
    return;
  }
  
  try {
    posthog.init(posthogKey, {
      api_host: posthogHost,
      loaded: (ph) => {
        // Disable in development if needed
        if (process.env.NODE_ENV === 'development') {
          // ph.opt_out_capturing(); // Uncomment to disable in dev
        }
      },
      capture_pageview: false, // We'll capture manually to avoid double-tracking
      capture_pageleave: true,
      persistence: 'localStorage',
      autocapture: true, // Capture clicks/inputs for deeper analytics
      // Session recording: set to false to reduce volume/cost; true for full session replay
      disable_session_recording: true,
      bootstrap: {
        distinctID: undefined,
      },
      advanced_disable_decide: false,
      // Handle errors gracefully
      on_request_error: () => {
        if (process.env.NODE_ENV === 'development') {
          console.warn('[Analytics] PostHog request failed');
        }
      },
    });
    
    initialized = true;
  } catch (error) {
    // If initialization fails, mark as failed and continue without analytics
    initializationFailed = true;
    if (process.env.NODE_ENV === 'development') {
      console.warn('[Analytics] PostHog initialization failed:', error);
    }
  }
}

// ==================== Server-side capture (Postgres) ====================

const METRICS_URL = `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1'}/metrics/event`;

function getOrCreateDistinctId(): string | null {
  if (typeof window === 'undefined') return null;
  try {
    const key = 'jobscout_distinct_id';
    const existing = window.localStorage.getItem(key);
    if (existing) return existing;
    const id = (globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random()}`).toString();
    window.localStorage.setItem(key, id);
    return id;
  } catch {
    return null;
  }
}

async function serverCapture(eventName: string, properties?: Record<string, unknown>) {
  if (typeof window === 'undefined') return;
  try {
    const distinctId = getOrCreateDistinctId();
    const path = window.location?.pathname || undefined;

    let token: string | null = null;
    if (isSupabaseConfigured()) {
      const { data } = await supabase.auth.getSession();
      token = data.session?.access_token || null;
    }

    // Fire-and-forget; ignore failures.
    fetch(METRICS_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({
        event_name: eventName,
        properties: properties || {},
        distinct_id: distinctId,
        path,
        client_ts: new Date().toISOString(),
      }),
      keepalive: true,
    }).catch(() => undefined);
  } catch {
    // swallow
  }
}

function capture(eventName: string, properties?: Record<string, unknown>) {
  if (isAnalyticsReady()) {
    posthog.capture(eventName, {
      ...properties,
      timestamp: new Date().toISOString(),
    });
  }
  // Always attempt server-side capture (even when PostHog disabled)
  serverCapture(eventName, properties);
}

// Check if analytics is ready
export function isAnalyticsReady(): boolean {
  return initialized && !initializationFailed && typeof window !== 'undefined';
}

// Identify user (call after authentication)
export function identifyUser(userId: string, properties?: Record<string, unknown>) {
  if (!isAnalyticsReady()) return;
  
  posthog.identify(userId, {
    ...properties,
    source: 'jobscout',
  });
}

// Reset user identity (call on logout)
export function resetUser() {
  if (!isAnalyticsReady()) return;
  posthog.reset();
}

/**
 * Set user properties for segmentation (has_resume, has_completed_profile, plan).
 * Call after loading profile or subscription state.
 */
export function setUserProperties(properties: Record<string, unknown>) {
  if (!isAnalyticsReady()) return;
  posthog.people.set(properties);
}

// ==================== Conversion Funnel Events ====================

/**
 * Track when user signs up (creates account)
 */
export function trackSignUp(method: 'email' | 'google' = 'email') {
  capture('user_signed_up', { method });
}

/**
 * Track when user completes their profile
 */
export function trackProfileCompleted(hasResume: boolean) {
  capture('profile_completed', { has_resume: hasResume });
}

/**
 * Track when user views a job
 */
export function trackJobViewed(jobId: string, jobTitle?: string, company?: string) {
  capture('job_viewed', { job_id: jobId, job_title: jobTitle, company });
}

/**
 * Track when user opens Apply Workspace
 */
export function trackApplyWorkspaceOpened(source: 'direct' | 'job_card' | 'job_detail') {
  capture('apply_workspace_opened', { source });
}

/**
 * Track when user imports a job into Apply Workspace
 */
export function trackJobImported(jobId: string, method: 'url_parse' | 'text_paste' | 'jobscout_import') {
  capture('job_imported', { job_id: jobId, method });
}

/**
 * Track when user generates a Trust Report
 */
export function trackTrustReportGenerated(jobTargetId: string, trustScore?: number) {
  capture('trust_report_generated', { job_target_id: jobTargetId, trust_score: trustScore });
}

/**
 * Track when user creates their first Apply Pack (key activation event!)
 */
export function trackFirstApplyPackCreated(applyPackId: string) {
  capture('first_apply_pack_created', { apply_pack_id: applyPackId });
  
  // Also set user property for segmentation
  if (isAnalyticsReady()) {
    posthog.people.set({
      first_apply_pack_date: new Date().toISOString(),
      has_created_apply_pack: true,
    });
  }
}

/**
 * Track when user creates any Apply Pack
 */
export function trackApplyPackCreated(applyPackId: string, packNumber: number) {
  capture('apply_pack_created', { apply_pack_id: applyPackId, pack_number: packNumber });
}

/**
 * Track when user downloads DOCX (paid feature)
 */
export function trackDocxDownloaded(applyPackId: string, format: 'resume' | 'cover' | 'combined') {
  capture('docx_downloaded', { apply_pack_id: applyPackId, format });
}

/**
 * Track when user starts tracking an application
 */
export function trackApplicationTracked(applicationId: string) {
  capture('application_tracked', { application_id: applicationId });
}

/**
 * Track when user views upgrade/pricing prompt
 */
export function trackUpgradePromptViewed(source: 'quota_limit' | 'docx_paywall' | 'tracking_limit' | 'pricing_page') {
  capture('upgrade_prompt_viewed', { source });
}

/**
 * Track when user clicks upgrade button
 */
export function trackUpgradeClicked(plan: string, source: string) {
  capture('upgrade_clicked', { plan, source });
}

/**
 * Track when user completes a paid subscription
 */
export function trackSubscriptionStarted(plan: string, amount: number, currency: string) {
  capture('subscription_started', { plan, amount, currency });
  
  // Set user properties
  if (isAnalyticsReady()) {
    posthog.people.set({
      plan,
      subscription_started_at: new Date().toISOString(),
      is_paying_customer: true,
    });
  }
}

/**
 * Track when user cancels subscription
 */
export function trackSubscriptionCancelled(plan: string, reason?: string) {
  capture('subscription_cancelled', { plan, reason });
}

// ==================== Referral Events ====================

/**
 * Track referral link copied
 */
export function trackReferralLinkCopied() {
  capture('referral_link_copied', {});
}

/**
 * Track referral signup
 */
export function trackReferralSignup(referrerId: string) {
  capture('referral_signup', { referrer_id: referrerId });
}

// ==================== Retention Events ====================

/**
 * Track weekly digest email opened
 */
export function trackWeeklyDigestOpened() {
  capture('weekly_digest_opened', {});
}

/**
 * Track saved search created
 */
export function trackSavedSearchCreated(searchId: string, filters: Record<string, unknown>) {
  capture('saved_search_created', { search_id: searchId, filters });
}

/**
 * Track job alert created
 */
export function trackJobAlertCreated(alertId: string) {
  capture('job_alert_created', { alert_id: alertId });
}

// ==================== Feature Usage Events ====================

/**
 * Track feature flag evaluation
 */
export function isFeatureEnabled(flagName: string): boolean {
  if (!isAnalyticsReady()) return false;
  return posthog.isFeatureEnabled(flagName) ?? false;
}

/**
 * Generic event tracker for custom events
 */
export function trackEvent(eventName: string, properties?: Record<string, unknown>) {
  capture(eventName, properties);
}

// Export posthog instance for advanced usage
export { posthog };
