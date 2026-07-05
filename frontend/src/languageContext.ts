import { createContext } from "react";

import type { Language, TranslationKey, TranslationValues } from "./i18n";

export interface LanguageContextValue {
  language: Language;
  setLanguage: (language: Language) => void;
  seatName: (seatId: string) => string;
  t: (key: TranslationKey, values?: TranslationValues) => string;
}

export const LanguageContext = createContext<LanguageContextValue | null>(null);
