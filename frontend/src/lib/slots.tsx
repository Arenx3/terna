import { Fragment, type ReactNode } from "react"

/**
 * Fills `{name}` slots of a translated sentence with React nodes, e.g.
 * "Work at {company}". Values often come from users (names, titles), so they
 * are inserted as nodes and never parsed as markup.
 */
export function fillSlots(sentence: string, slots: Record<string, ReactNode>) {
  const names = Object.keys(slots).join("|")
  const pattern = new RegExp(`(\\{(?:${names})\\})`)
  return sentence.split(pattern).map((part, index) => {
    const name = /^\{(\w+)\}$/.exec(part)?.[1]
    return (
      <Fragment key={index}>
        {name !== undefined && name in slots ? slots[name] : part}
      </Fragment>
    )
  })
}
