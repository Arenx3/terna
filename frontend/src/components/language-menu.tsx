import { LanguagesIcon } from "lucide-react"
import { useTranslation } from "react-i18next"

import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { currentLanguage, LANGUAGES, type Language } from "@/i18n"

export function LanguageMenu() {
  const { t, i18n } = useTranslation()

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={
          <Button
            variant="ghost"
            size="icon"
            aria-label={t("language.change")}
          />
        }
      >
        <LanguagesIcon />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuGroup>
          <DropdownMenuLabel>{t("language.label")}</DropdownMenuLabel>
          <DropdownMenuRadioGroup
            value={currentLanguage()}
            onValueChange={(value: Language) => i18n.changeLanguage(value)}
          >
            {LANGUAGES.map((language) => (
              // Each language is named in itself, so it is findable whatever the current one is.
              <DropdownMenuRadioItem
                key={language}
                value={language}
                lang={language}
                translate="no"
                closeOnClick
              >
                {t(`language.${language}`)}
              </DropdownMenuRadioItem>
            ))}
          </DropdownMenuRadioGroup>
        </DropdownMenuGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
