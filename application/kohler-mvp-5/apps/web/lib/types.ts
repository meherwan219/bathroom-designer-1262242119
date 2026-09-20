/** Mirrors app/store.py's spec_to_dict shape and the /generate response. */
export interface DesignSpecPayload {
  room: {
    width_mm: number;
    depth_mm: number;
    height_mm?: number;
    wet_walls?: string[];
  };
  budget: { max_inr: number; flexibility?: "none" | "soft_10pct" };
  hard_required: string[];
  preferences?: {
    styles?: string[];
    features?: string[];
    sustainability_weight?: number;
    space_efficiency_weight?: number;
  };
  constraints_profile?: "nkba_std" | "compact_apt";
}

export interface LayoutObject {
  id: string;
  sku: string;
  category: string;
  role: string;
  finish: string;
  origin: { x: number; y: number };
  rotation_deg: number;
  bbox: { w: number; d: number; h: number };
}

export interface LayoutIR {
  units: "mm";
  room: { polygon: [number, number][]; height_mm: number; doors: unknown[]; windows: unknown[] };
  wet_walls: string[];
  grid_mm: number;
  objects: LayoutObject[];
  circulation: unknown[];
  meta: { profile: string; solver_version: string; seed: number };
}

export interface BomItem {
  role: string;
  sku: string;
  name: string;
  category: string;
  price_inr: number;
}

export interface Violation {
  code: string;
  message: string;
}

export interface SoftScore {
  style_match: number;
  feature_coverage: number;
  sustainability: number;
  space_efficiency: number;
  family_coherence: number;
  waste_penalty: number;
  total: number;
}

export interface ItemsetTrace {
  matched_tags: string[];
  total_water_use_lpf_or_gpm: number;
  baseline_water_use: number;
  water_savings_pct_vs_baseline: number;
  score_breakdown: SoftScore;
}

export interface RecommendationAlternative {
  rank: number;
  feasible: boolean;
  items: BomItem[];
  hard_violations: Violation[];
  layout_ir: LayoutIR | Record<string, never>;
  totals: { price_inr: number; budget_inr: number };
  score: SoftScore;
  trace: ItemsetTrace;
}

export interface GenerateResponse {
  spec: DesignSpecPayload;
  layout_ir: LayoutIR | Record<string, never>;
  items: BomItem[];
  totals: { price_inr: number; budget_inr: number };
  hard_violations: Violation[];
  soft_scores: SoftScore | null;
  explanation: string | null;
  recommendation_alternatives: RecommendationAlternative[];
}

export interface ChatAlternative {
  description: string;
  delta: Record<string, unknown>;
  would_be_feasible: boolean;
}

export interface ChatResponse {
  reply: string;
  extracted_delta: Record<string, unknown>;
  spec: DesignSpecPayload;
  layout_ir: LayoutIR | Record<string, never>;
  items: BomItem[];
  totals: { price_inr: number; budget_inr: number };
  hard_violations: Violation[];
  alternatives: ChatAlternative[];
}

export interface ChatMessage {
  role: "user" | "assistant";
  text: string;
}

export interface ConfigFlags {
  enable_3d: boolean;
  enable_vision: boolean;
}

export interface FloorplanDoor {
  wall: "N" | "S" | "E" | "W";
  offset_mm: number;
  width_mm: number;
}

export interface FloorplanProposal {
  width_mm: number;
  depth_mm: number;
  doors?: FloorplanDoor[];
  confidence: number;
}

export interface FloorplanResponse {
  proposal: FloorplanProposal | null;
  error: string | null;
}
