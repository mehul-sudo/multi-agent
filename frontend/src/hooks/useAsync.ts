import { useCallback, useEffect, useRef, useState, type DependencyList } from 'react'

interface UseAsyncState<T> {
  data: T | null
  isLoading: boolean
  error: string | null
}

export function useAsync<T>(
  fn: () => Promise<T>,
  deps: DependencyList = [],
  immediate = true
): UseAsyncState<T> & { refetch: () => void } {
  const [state, setState] = useState<UseAsyncState<T>>({
    data: null,
    isLoading: immediate,
    error: null,
  })
  const mountedRef = useRef(true)

  const execute = useCallback(async () => {
    setState((s) => ({ ...s, isLoading: true, error: null }))
    try {
      const data = await fn()
      if (mountedRef.current) setState({ data, isLoading: false, error: null })
    } catch (e) {
      if (mountedRef.current)
        setState({ data: null, isLoading: false, error: (e as Error).message || 'Unknown error' })
    }
  }, deps) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    mountedRef.current = true
    if (immediate) execute()
    return () => { mountedRef.current = false }
  }, [execute, immediate])

  return { ...state, refetch: execute }
}
