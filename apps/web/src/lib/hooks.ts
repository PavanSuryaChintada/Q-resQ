import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api, type Backend } from "./api"

export function useRiskCells() {
  return useQuery({ queryKey: ["risk-cells"], queryFn: api.riskCells })
}

export function useRiskCellDetail(id: number | null) {
  return useQuery({
    queryKey: ["risk-cell", id],
    queryFn: () => api.riskCell(id as number),
    enabled: id !== null,
  })
}

export function useRequests(status?: string) {
  return useQuery({ queryKey: ["requests", status], queryFn: () => api.requests(status), refetchInterval: 4000 })
}

export function useUnits() {
  return useQuery({ queryKey: ["units"], queryFn: api.units, refetchInterval: 4000 })
}

export function useLog(since?: number) {
  return useQuery({ queryKey: ["log", since], queryFn: () => api.log(since), refetchInterval: 2000 })
}

export function useCreateRequest() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: api.createRequest,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["requests"] })
      qc.invalidateQueries({ queryKey: ["log"] })
    },
  })
}

export function useSolveDispatch() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ backend, timeout_s }: { backend: Backend; timeout_s?: number }) =>
      api.solveDispatch(backend, timeout_s),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["requests"] })
      qc.invalidateQueries({ queryKey: ["units"] })
      qc.invalidateQueries({ queryKey: ["log"] })
    },
  })
}

export function useRunBenchmark() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (backends?: Backend[]) => api.runBenchmark(backends),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["log"] })
    },
  })
}

export function useSeedTitli() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (n_requests?: number) => api.seedTitli(n_requests),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["requests"] })
      qc.invalidateQueries({ queryKey: ["units"] })
      qc.invalidateQueries({ queryKey: ["log"] })
    },
  })
}
