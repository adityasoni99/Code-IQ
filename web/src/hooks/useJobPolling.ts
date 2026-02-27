import { useQuery } from '@tanstack/react-query'
import { getJob } from '../api/client'

export function useJobPolling(jobId: string | undefined, options?: { enabled?: boolean; refetchInterval?: number | false }) {
  return useQuery({
    queryKey: ['job', jobId],
    queryFn: () => getJob(jobId!),
    enabled: !!jobId && (options?.enabled ?? true),
    refetchInterval: options?.refetchInterval !== undefined ? options.refetchInterval : (jobId ? 2000 : false),
  })
}
