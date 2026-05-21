import { useState, useEffect, useRef, useCallback } from 'react'

type ReadyState = 0 | 1 | 2 | 3

interface UseWebSocketReturn {
  lastMessage: MessageEvent | null
  readyState: ReadyState
  sendMessage: (msg: string) => void
}

export function useWebSocket(url: string): UseWebSocketReturn {
  const [lastMessage, setLastMessage] = useState<MessageEvent | null>(null)
  const [readyState, setReadyState] = useState<ReadyState>(3)
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const unmountedRef = useRef(false)

  const connect = useCallback(() => {
    if (unmountedRef.current) return

    try {
      const ws = new WebSocket(url)
      wsRef.current = ws

      ws.onopen = () => {
        if (!unmountedRef.current) setReadyState(1)
      }

      ws.onmessage = (evt) => {
        if (!unmountedRef.current) setLastMessage(evt)
      }

      ws.onclose = () => {
        if (!unmountedRef.current) {
          setReadyState(3)
          // Auto-reconnect after 3 seconds
          reconnectTimer.current = setTimeout(connect, 3000)
        }
      }

      ws.onerror = () => {
        if (!unmountedRef.current) setReadyState(3)
        ws.close()
      }

      setReadyState(0)
    } catch {
      // WebSocket construction failed; retry
      if (!unmountedRef.current) {
        reconnectTimer.current = setTimeout(connect, 3000)
      }
    }
  }, [url])

  useEffect(() => {
    unmountedRef.current = false
    connect()
    return () => {
      unmountedRef.current = true
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
      wsRef.current?.close()
    }
  }, [connect])

  const sendMessage = useCallback((msg: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(msg)
    }
  }, [])

  return { lastMessage, readyState, sendMessage }
}
