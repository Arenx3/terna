import createClient from "openapi-fetch"

import type { components, paths } from "./schema"

// Same origin: nginx serves the app and proxies /api to Django. `npm run dev` proxies it too.
export const api = createClient<paths>({ baseUrl: "" })

export type Schemas = components["schemas"]
