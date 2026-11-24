/** Reads the emails the stack sent, through Mailpit's HTTP API. */

const MAILPIT_URL = process.env.MAILPIT_URL ?? "http://localhost:8025"

type Summary = { ID: string; Subject: string; Created: string }

export async function waitForEmail(
  to: string,
  subject: RegExp,
  timeoutMs = 20_000
): Promise<{ subject: string; text: string }> {
  const deadline = Date.now() + timeoutMs
  const query = encodeURIComponent(`to:"${to}"`)
  while (Date.now() < deadline) {
    const response = await fetch(`${MAILPIT_URL}/api/v1/search?query=${query}`)
    const { messages } = (await response.json()) as { messages: Summary[] }
    const match = messages.find((message) => subject.test(message.Subject))
    if (match) {
      const message = await fetch(`${MAILPIT_URL}/api/v1/message/${match.ID}`)
      const body = (await message.json()) as { Subject: string; Text: string }
      return { subject: body.Subject, text: body.Text }
    }
    await new Promise((resolve) => setTimeout(resolve, 500))
  }
  throw new Error(
    `No email to ${to} matching ${subject} within ${timeoutMs} ms`
  )
}

/** Path and query of the app link to `path` in an email, ready for page.goto(). */
export function appLink(text: string, path: string): string {
  const match = text.match(new RegExp(`https?://[^\\s]+(${path}\\?[^\\s]+)`))
  if (!match) throw new Error(`No ${path} link in:\n${text}`)
  return match[1]
}

export function uniqueEmail(label: string): string {
  return `e2e-${label}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@terna.test`
}
