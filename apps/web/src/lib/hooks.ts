import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api, type Backend, type DisasterType } from "./api"

export function useRiskCells(disasterType: DisasterType = "cyclone") {
  return useQuery({
    queryKey: ["risk-cells", disasterType],
    queryFn: () => api.riskCells(disasterType),
  })
}

export function useRiskCellDetail(id: number | null, disasterType: DisasterType = "cyclone") {
  return useQuery({
    queryKey: ["risk-cell", id, disasterType],
    queryFn: () => api.riskCell(id as number, disasterType),
    enabled: id !== null,
  })
}

export function useRequests(status?: string) {
  return useQuery({ queryKey: ["requests", status], queryFn: () => api.requests(status), refetchInterval: 4000 })
}

export function useUnits() {
  return useQuery({ queryKey: ["units"], queryFn: api.units, refetchInterval: 4000 })
}

export function useAssignments() {
  return useQuery({ queryKey: ["assignments"], queryFn: api.assignments, refetchInterval: 4000 })
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
      qc.invalidateQueries({ queryKey: ["assignments"] })
    },
  })
}

export function useAssignUnit() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ requestId, unitId }: { requestId: string; unitId: string }) =>
      api.assignUnit(requestId, unitId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["requests"] })
      qc.invalidateQueries({ queryKey: ["units"] })
      qc.invalidateQueries({ queryKey: ["log"] })
      qc.invalidateQueries({ queryKey: ["assignments"] })
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

export function useLiveRiskRange() {
  return useQuery({ queryKey: ["live-risk-range"], queryFn: api.liveRiskRange, staleTime: 60_000 })
}

export function useLiveRisk() {
  return useMutation({
    mutationFn: ({ date, disasterType }: { date?: string; disasterType?: DisasterType }) =>
      api.liveRisk(date, disasterType),
  })
}

export function useSeedTitli() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ n_requests, disasterType }: { n_requests?: number; disasterType?: DisasterType }) =>
      api.seedTitli(n_requests, disasterType),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["requests"] })
      qc.invalidateQueries({ queryKey: ["units"] })
      qc.invalidateQueries({ queryKey: ["log"] })
    },
  })
}
