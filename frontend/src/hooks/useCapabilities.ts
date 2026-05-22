import { useEffect, useState } from 'react'
import { fetchCapabilities } from '../api'

let cached: string[] | null = null

export function useCapabilities(): string[] {
  const [capabilities, setCapabilities] = useState<string[]>(cached ?? [])

  useEffect(() => {
    if (cached) return
    fetchCapabilities()
      .then(({ capabilities: caps }) => {
        cached = caps
        setCapabilities(caps)
      })
      .catch(() => {})
  }, [])

  return capabilities
}
