import { useTranslation } from "react-i18next"

import { ROLES, type Role } from "@/api/team"
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

/** A role picker. With `name`, it also posts its value in a form. */
export function RoleSelect({
  value,
  onChange,
  name,
  id,
  label,
  disabled,
}: {
  value?: Role
  onChange?: (role: Role) => void
  name?: string
  id?: string
  label?: string
  disabled?: boolean
}) {
  const { t } = useTranslation()
  const items = ROLES.map((role) => ({
    value: role,
    label: t(`roles.${role}`),
  }))

  return (
    <Select
      items={items}
      value={value}
      defaultValue={value === undefined ? "recruiter" : undefined}
      onValueChange={(next) => next && onChange?.(next as Role)}
      name={name}
      disabled={disabled}
    >
      <SelectTrigger id={id} aria-label={label} className="min-w-44">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        <SelectGroup>
          {items.map((item) => (
            <SelectItem key={item.value} value={item.value}>
              {item.label}
            </SelectItem>
          ))}
        </SelectGroup>
      </SelectContent>
    </Select>
  )
}
