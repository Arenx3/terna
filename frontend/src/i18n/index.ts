import i18n from "i18next"
import LanguageDetector from "i18next-browser-languagedetector"
import { initReactI18next } from "react-i18next"

import { en } from "./locales/en"
import { es } from "./locales/es"

export const LANGUAGES = ["es", "en"] as const
export type Language = (typeof LANGUAGES)[number]

// Keep in sync with the inline script in index.html.
export const LANGUAGE_STORAGE_KEY = "terna.lang"

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      en: { translation: en },
      es: { translation: es },
    },
    supportedLngs: LANGUAGES,
    nonExplicitSupportedLngs: true,
    load: "languageOnly",
    fallbackLng: "en",
    detection: {
      // A saved choice wins; otherwise the browser's language.
      order: ["localStorage", "navigator"],
      lookupLocalStorage: LANGUAGE_STORAGE_KEY,
      caches: ["localStorage"],
      // "es-419" or "es-MX" become "es", so the saved value is always a supported language.
      convertDetectedLanguage: (language) => language.split("-")[0],
    },
    interpolation: {
      escapeValue: false, // React already escapes.
    },
  })

function syncDocumentLanguage(language: string) {
  document.documentElement.lang = language
}

syncDocumentLanguage(i18n.resolvedLanguage ?? "en")
i18n.on("languageChanged", syncDocumentLanguage)

export function currentLanguage(): Language {
  const language = i18n.resolvedLanguage
  return LANGUAGES.find((supported) => supported === language) ?? "en"
}

export default i18n
