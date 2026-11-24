import { resolve } from "node:path"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"

// `npm run dev` talks to the running stack through nginx, like the built app does.
const stack = process.env.TERNA_STACK_URL ?? "http://127.0.0.1:8080"

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": resolve(import.meta.dirname, "./src"),
    },
  },
  build: {
    rolldownOptions: {
      output: {
        // Libraries change far less often than app code: separate chunks keep them cached.
        codeSplitting: {
          groups: [
            {
              name: "react",
              test: /node_modules[\\/](react|react-dom|scheduler|react-router)[\\/]/,
              priority: 20,
            },
            {
              name: "ui",
              test: /node_modules[\\/](@base-ui|@floating-ui|lucide-react)[\\/]/,
              priority: 10,
            },
            { name: "vendor", test: /node_modules[\\/]/, priority: 0 },
          ],
        },
      },
    },
  },
  server: {
    proxy: {
      "/api": stack,
      "/static": stack,
      "/ws": { target: stack, ws: true },
    },
  },
})
