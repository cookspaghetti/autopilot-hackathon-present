'use client'

import { useCallback, useEffect, useState } from 'react'

import { apiClient } from '@/lib/api-client'

interface UseApiResourceOptions {
  enabled?: boolean
}

export function useApiResource<T>(
  endpoint: string,
  { enabled = true }: UseApiResourceOptions = {}
) {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(enabled)

  const refresh = useCallback(async () => {
    if (!enabled) return
    setIsLoading(true)
    setError(null)
    try {
      setData(await apiClient.get<T>(endpoint))
    } catch (requestError) {
      setError(
        requestError instanceof Error ? requestError.message : 'Request failed'
      )
    } finally {
      setIsLoading(false)
    }
  }, [enabled, endpoint])

  useEffect(() => {
    void refresh()
  }, [refresh])

  return { data, error, isLoading, refresh, setData }
}
