import { useEffect, useRef, useState } from "react"

import type { JobApplication } from "@/api/applications"
import { refreshSession, sessionStore } from "@/auth/session"

export type Viewer = { key: string; user: { id: string; name: string } }

export type BoardUpdate = {
  event:
    | "application.submitted"
    | "application.stage_changed"
    | "screening.completed"
  application: JobApplication
  by: { id: string | null; name: string }
}

export type ChannelStatus = "connecting" | "live" | "offline"

// Close codes from the server: get a fresh token and retry, or give up.
const UNAUTHENTICATED = 4401
const FORBIDDEN = 4403
const MAX_BACKOFF_MS = 30_000

/**
 * The job board's live channel: other people's moves and who else is looking.
 * The token goes in the first message, never in the URL. On reconnect the
 * caller refetches, so nothing missed while offline stays missing.
 */
export function useBoardChannel(
  jobId: string,
  handlers: { onUpdate: (update: BoardUpdate) => void; onReady: () => void }
) {
  const [viewers, setViewers] = useState<Viewer[]>([])
  const [status, setStatus] = useState<ChannelStatus>("connecting")
  const latest = useRef(handlers)

  useEffect(() => {
    latest.current = handlers
  })

  useEffect(() => {
    let socket: WebSocket | null = null
    let stopped = false
    let attempt = 0
    let refreshed = false
    let timer: number | undefined

    function open() {
      const protocol = window.location.protocol === "https:" ? "wss" : "ws"
      socket = new WebSocket(
        `${protocol}://${window.location.host}/ws/jobs/${jobId}/board/`
      )
      socket.onopen = () => {
        socket?.send(
          JSON.stringify({
            type: "auth",
            token: sessionStore.get()?.access ?? "",
          })
        )
      }
      socket.onmessage = (message: MessageEvent<string>) => {
        const data = JSON.parse(message.data) as
          | { type: "ready" }
          | ({ type: "presence.join" } & Viewer)
          | { type: "presence.leave"; key: string }
          | ({ type: "board.update" } & BoardUpdate)
        if (data.type === "ready") {
          attempt = 0
          refreshed = false
          setStatus("live")
          latest.current.onReady()
        } else if (data.type === "presence.join") {
          setViewers((current) => [
            ...current.filter((viewer) => viewer.key !== data.key),
            { key: data.key, user: data.user },
          ])
        } else if (data.type === "presence.leave") {
          setViewers((current) =>
            current.filter((viewer) => viewer.key !== data.key)
          )
        } else if (data.type === "board.update") {
          latest.current.onUpdate(data)
        }
      }
      socket.onclose = (event) => {
        setViewers([])
        if (stopped || event.code === FORBIDDEN) {
          setStatus("offline")
          return
        }
        setStatus("offline")
        if (event.code === UNAUTHENTICATED && !refreshed) {
          // The access token expired while the board was open: renew once, right away.
          refreshed = true
          void refreshSession().then(() => !stopped && open())
          return
        }
        attempt += 1
        timer = window.setTimeout(
          open,
          Math.min(MAX_BACKOFF_MS, 1000 * 2 ** attempt)
        )
      }
    }

    open()
    return () => {
      stopped = true
      window.clearTimeout(timer)
      socket?.close()
    }
  }, [jobId])

  return { viewers, status }
}
