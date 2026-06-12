import api from "./client";

// ---------------------------------------------------------------------------
// Secretary — the CEO chief-of-staff read surfaces.
//
// The live two-way chat lives in `prompter-live.ts` (the spawned intake/
// Secretary agent). This client covers the *proactive feed* (3.A2): a periodic
// digest of "what needs the CEO" the panel renders as a notifications-style
// strip alongside the chat. Mirrors the backend `GET /secretary/digest`
// (`roboco/api/routes/secretary.py`).
// ---------------------------------------------------------------------------

/** One queue item (a task or notification) the digest surfaces. */
export interface SecretaryFeedItem {
  kind: string;
  source: string;
  task_id?: string;
  notification_id?: string;
  title?: string;
  subject?: string;
  status?: string;
  team?: string | null;
  priority?: number | string;
  type?: string;
  pr_url?: string | null;
  related_task_id?: string | null;
  reason: string;
  updated_at?: string | null;
}

/** Goals-derived drift signal (objectives vs. in-flight work). */
export interface SecretaryDrift {
  active_objectives: number;
  in_flight_tasks: number;
  work_without_objectives: boolean;
  objectives_without_work: boolean;
}

/** The proactive feed payload — what the CEO should not be surprised by. */
export interface SecretaryDigest {
  pending_approvals: number;
  stale_decisions: SecretaryFeedItem[];
  fresh_pitches: SecretaryFeedItem[];
  drift: SecretaryDrift;
  generated_at: string;
}

export const secretaryApi = {
  // The proactive feed: pending approvals, stale decisions, drift, pitches.
  digest: async (): Promise<SecretaryDigest> => {
    const { data } = await api.get<SecretaryDigest>("/secretary/digest");
    return data;
  },
};
