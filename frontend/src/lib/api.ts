const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

export type Market = {
  id: string;
  question: string;
  slug?: string | null;
  description?: string | null;
  category?: string | null;
  active: boolean;
  closed: boolean;
  volume?: number | null;
  liquidity?: number | null;
  market_probability?: number | null;
  end_date?: string | null;
};

export type MarketCandidate = {
  market: Market;
  operon_score: number;
  reason: string;
  model_type: string;
  category_guess: string;
  risk_flags: string[];
  selected_reason: string;
  resolution_score: number;
  evidence_score: number;
  liquidity_score: number;
  market_structure_type: string;
  primary_edge_source: string;
  scout_penalty: number;
};

export type EventDraft = {
  id: string;
  market: Market;
  model_type: string;
  market_probability?: number | null;
  operon_probability: number;
  evidence_items: string[];
  probability_timeline: Array<{ label: string; probability: number }>;
  risk_flags: string[];
  financial_barrier?: FinancialBarrierDiagnostics | null;
  product_release?: ModelDiagnostics | null;
  macro_policy?: ModelDiagnostics | null;
  election_polling?: ModelDiagnostics | null;
  logic_consistency?: ModelDiagnostics | null;
  general_event?: ModelDiagnostics | null;
};

export type FinancialBarrierDiagnostics = {
  asset: string;
  spot_price: number;
  barrier_price: number;
  deadline?: string | null;
  days_remaining: number;
  annualized_volatility: number;
  simulations: number;
  steps: number;
  hit_probability: number;
  expected_contract_value: number;
  fallback_probability: number;
  rule_type: string;
  rule_summary: string;
  valuation_formula: string;
  drift: number;
  data_source: string;
  notes: string[];
};

export type ModelDiagnostics = {
  model_name: string;
  posterior_probability: number;
  confidence: number;
  uncertainty_interval: [number, number];
  state_scores: Record<string, number>;
  key_drivers: string[];
  notes: string[];
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed with ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export function runMarketScout(limit: number, topN: number) {
  return request<MarketCandidate[]>(`/market-scout/run?limit=${limit}&top_n=${topN}`, {
    method: "POST",
  });
}

export function promoteToEvent(candidate: MarketCandidate) {
  return request<EventDraft>("/market-scout/promote-to-event", {
    method: "POST",
    body: JSON.stringify(candidate),
  });
}

export function getEvent(eventId: string) {
  return request<EventDraft>(`/market-scout/events/${eventId}`);
}
