export type MatchStatus = "waiting" | "matched";
export type Phase = "discussion" | "voting" | "resolution" | "finished";
export type Role = "human" | "ai";
export type Winner = "humans" | "ai";

export interface Match {
  ticket_id: string;
  player_token: string;
  status: MatchStatus;
  game_id: string | null;
  seat_id: string | null;
}

export interface Seat {
  id: string;
  alive: boolean;
  role: Role | null;
}

export interface ChatMessage {
  id: string;
  seat_id: string;
  content: string;
  sent_at: string;
}

export interface Vote {
  voter_id: string;
  target_id: string;
}

export interface RoundResult {
  round_number: number;
  eliminated_id: string | null;
  votes: Vote[];
}

export interface LocalizedText {
  en: string;
  zh_cn: string;
}

export interface RoundBrief {
  category: LocalizedText;
  keyword: LocalizedText | null;
}

export interface Game {
  id: string;
  seats: Seat[];
  phase: Phase;
  round_number: number;
  phase_deadline: string | null;
  winner: Winner | null;
  messages: ChatMessage[];
  round_results: RoundResult[];
  round_brief: RoundBrief | null;
}
