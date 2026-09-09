const API_BASE = import.meta.env.VITE_API_BASE || '/api'

const DB_NAME = 'QResQOffline'
const DB_VERSION = 1
const STORE_REPORTS = 'reports'

// IndexedDB helper
async function openDB(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION)

    request.onerror = () => reject(request.error)
    request.onsuccess = () => resolve(request.result)

    request.onupgradeneeded = (event) => {
      const db = (event.target as IDBOpenDBRequest).result
      if (!db.objectStoreNames.contains(STORE_REPORTS)) {
        const store = db.createObjectStore(STORE_REPORTS, { keyPath: 'id' })
        store.createIndex('synced', 'synced', { unique: false })
      }
    }
  })
}

export async function submitReport(report: any, offline = false) {
  if (offline || !navigator.onLine) {
    await queueReport(report)
    return { queued: true, id: report.id }
  }

  try {
    const response = await fetch(`${API_BASE}/reports/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(report)
    })
    if (!response.ok) throw new Error('Submission failed')
    return response.json()
  } catch (error) {
    await queueReport(report)
    return { queued: true, id: report.id }
  }
}

export async function getAlerts() {
  try {
    const response = await fetch(`${API_BASE}/alerts/`)
    if (!response.ok) throw new Error('Failed to fetch alerts')
    return response.json()
  } catch (error) {
    console.error('Failed to fetch alerts:', error)
    return []
  }
}

export async function syncOfflineReports() {
  const queued = await getQueuedReports()
  const results = []

  for (const report of queued) {
    try {
      const response = await fetch(`${API_BASE}/reports/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(report)
      })
      if (response.ok) {
        await removeFromQueue(report.id)
        results.push({ id: report.id, synced: true })
      } else {
        results.push({ id: report.id, synced: false, error: 'Server error' })
      }
    } catch (error) {
      results.push({ id: report.id, synced: false, error: String(error) })
    }
  }

  return results
}

async function queueReport(report: any) {
  const db = await openDB()
  return new Promise<void>((resolve, reject) => {
    const transaction = db.transaction([STORE_REPORTS], 'readwrite')
    const store = transaction.objectStore(STORE_REPORTS)
    const request = store.put({ ...report, synced: false, queuedAt: new Date().toISOString() })

    request.onsuccess = () => resolve()
    request.onerror = () => reject(request.error)
  })
}

async function getQueuedReports() {
  const db = await openDB()
  return new Promise<any[]>((resolve, reject) => {
    const transaction = db.transaction([STORE_REPORTS], 'readonly')
    const store = transaction.objectStore(STORE_REPORTS)
    const index = store.index('synced')
    const request = index.getAll(IDBKeyRange.only(false))

    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error)
  })
}

async function removeFromQueue(id: string) {
  const db = await openDB()
  return new Promise<void>((resolve, reject) => {
    const transaction = db.transaction([STORE_REPORTS], 'readwrite')
    const store = transaction.objectStore(STORE_REPORTS)
    const request = store.delete(id)

    request.onsuccess = () => resolve()
    request.onerror = () => reject(request.error)
  })
}

export async function getQueueCount(): Promise<number> {
  const queued = await getQueuedReports()
  return queued.length
}
