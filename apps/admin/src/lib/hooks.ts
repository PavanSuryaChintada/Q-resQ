import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api, type Backend } from "./api"

export function useRiskCells() {
  return useQuery({
    queryKey: ["risk-cells"],
    queryFn: api.riskCells,
  })
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

export function useAssignments() {
  return useQuery({ queryKey: ["assignments"], queryFn: api.assignments, refetchInterval: 4000 })
}

export function useReports(status?: string) {
  return useQuery({ queryKey: ["reports", status], queryFn: () => api.reports(status), refetchInterval: 4000 })
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

export function useIsolation() {
  return useQuery({ queryKey: ["isolation"], queryFn: api.isolation, refetchInterval: 5000 })
}

export function useBlockDemoTrigger() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: api.blockDemoTrigger,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["isolation"] })
      qc.invalidateQueries({ queryKey: ["log"] })
    },
  })
}

export function useClearRoadSegment() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (segmentId: number) => api.clearRoadSegment(segmentId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["isolation"] })
      qc.invalidateQueries({ queryKey: ["log"] })
    },
  })
}
