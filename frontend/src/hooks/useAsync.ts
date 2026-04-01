import { useState, useCallback } from 'react'
import { getApiErrorMessage } from '@/services/api'

interface AsyncState<T> {
  data: T | null
  isLoading: boolean
  error: string | null
}

export function useAsync<T>() {
  const [state, setState] = useState<AsyncState<T>>({
    data: null,
    isLoading: false,
    error: null,
  })

  const run = useCallback(async (promise: Promise<T>) => {
    setState({ data: null, isLoading: true, error: null })
    try {
      const data = await promise
      setState({ data, isLoading: false, error: null })
      return data
    } catch (err) {
      const error = getApiErrorMessage(err)
      setState({ data: null, isLoading: false, error })
      throw err
    }
  }, [])

  return { ...state, run }
}
