import "i18next"

import type { Resources } from "./locales/en"

// Typed keys: `t("status.titel")` is a compile error.
declare module "i18next" {
  interface CustomTypeOptions {
    defaultNS: "translation"
    resources: { translation: Resources }
  }
}
