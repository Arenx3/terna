import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { RouterProvider } from "react-router/dom"

import "./index.css"
import "./i18n"
import { SessionGate } from "@/components/route-guards"
import { ThemeProvider } from "@/components/theme-provider"
import { router } from "@/router"

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
    },
  },
})

const root = document.getElementById("root")
if (!root) {
  throw new Error("Missing #root element in index.html")
}

createRoot(root).render(
  <StrictMode>
    <ThemeProvider>
      <QueryClientProvider client={queryClient}>
        <SessionGate>
          <RouterProvider router={router} />
        </SessionGate>
      </QueryClientProvider>
    </ThemeProvider>
  </StrictMode>
)
