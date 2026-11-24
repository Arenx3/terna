import createClient, { type Middleware } from "openapi-fetch"

import { refreshSession, sessionStore } from "@/auth/session"
import { currentLanguage } from "@/i18n"

import type { components, paths } from "./schema"

export type Schemas = components["schemas"]

// Requests kept intact so they can be replayed once after a token refresh.
const replayable = new WeakMap<Request, Request>()

const auth: Middleware = {
  onRequest({ request }) {
    request.headers.set("Accept-Language", currentLanguage())
    const access = sessionStore.get()?.access
    if (access) request.headers.set("Authorization", `Bearer ${access}`)
    replayable.set(request, request.clone())
    return request
  },
  async onResponse({ request, response }) {
    // Expired access token: refresh once and replay. Auth endpoints handle 401 themselves.
    if (
      response.status !== 401 ||
      new URL(request.url).pathname.startsWith("/api/auth/")
    ) {
      return response
    }
    const copy = replayable.get(request)
    const session = await refreshSession()
    if (!session || !copy) return response
    copy.headers.set("Authorization", `Bearer ${session.access}`)
    return fetch(copy)
  },
}

// Same origin: nginx serves the app and proxies /api to Django. `npm run dev` proxies it too.
export const api = createClient<paths>({ baseUrl: "" })
api.use(auth)
