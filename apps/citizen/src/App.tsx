import { useState, useEffect } from 'react'
import { submitReport, getAlerts, syncOfflineReports, getQueueCount } from './lib/api'
import {
  HomeIcon, WarningIcon, BellIcon, UserIcon, CameraIcon, GalleryIcon,
  CheckIcon, CloseIcon, ShieldIcon, SyncIcon,
} from './icons'

type View = 'home' | 'report' | 'alerts' | 'sos-countdown' | 'sos-sent' | 'profile'

const SEVERITY_BANDS = ['NORMAL', 'WATCH', 'ALERT', 'WARNING', 'SEVERE'] as const
const SEVERITY_COLORS = ['#3D6B4F', '#B8901F', '#C26A15', '#B02E18', '#6E1810']

const PROFILE_STORAGE_KEY = 'qresq-profile'

interface Profile {
  householdSize: number
  areaName: string
  language: 'English' | 'Hindi' | 'Assamese'
}

const DEFAULT_PROFILE: Profile = { householdSize: 4, areaName: 'Chaltlang', language: 'English' }

function loadProfile(): Profile {
  try {
    const raw = localStorage.getItem(PROFILE_STORAGE_KEY)
    if (!raw) return DEFAULT_PROFILE
    return { ...DEFAULT_PROFILE, ...JSON.parse(raw) }
  } catch {
    return DEFAULT_PROFILE
  }
}

function App() {
  const [view, setView] = useState<View>('home')
  const [location, setLocation] = useState<[number, number] | null>(null)
  const [alerts, setAlerts] = useState<any[]>([])
  const [reportKind, setReportKind] = useState<'crack' | 'slope_movement' | 'road_blocked' | 'water_seepage' | 'other'>('crack')
  const [note, setNote] = useState('')
  const [photo, setPhoto] = useState<string | null>(null)
  const [photoError, setPhotoError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [submitResult, setSubmitResult] = useState<{queued?: boolean; id?: string} | null>(null)
  const [queueCount, setQueueCount] = useState(0)
  const [isOnline, setIsOnline] = useState(navigator.onLine)
  const [sending, setSending] = useState(false)
  const [countdown, setCountdown] = useState(3)
  const [severityBand, setSeverityBand] = useState(2) // Default to ALERT for demo
  const [lastSync, setLastSync] = useState<Date | null>(null)
  const [profile, setProfile] = useState<Profile>(loadProfile)
  const [profileDraft, setProfileDraft] = useState<Profile>(profile)
  const [profileSaved, setProfileSaved] = useState(false)

  useEffect(() => {
    updateQueueCount()
    window.addEventListener('online', () => {
      setIsOnline(true)
      updateQueueCount()
    })
    window.addEventListener('offline', () => {
      setIsOnline(false)
    })

    loadAlerts()
    getLocation()
  }, [])

  const MAX_PHOTO_BYTES = 6 * 1024 * 1024

  const handlePhotoChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file) return
    setPhotoError(null)
    if (file.size > MAX_PHOTO_BYTES) {
      setPhotoError('Photo is too large. Try again with a smaller image.')
      return
    }
    const reader = new FileReader()
    reader.onload = () => setPhoto(reader.result as string)
    reader.onerror = () => setPhotoError('Could not read that photo. Try again.')
    reader.readAsDataURL(file)
  }

  const getLocation = () => {
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (pos) => setLocation([pos.coords.latitude, pos.coords.longitude]),
        (err) => console.error('Geolocation error:', err)
      )
    }
  }

  const loadAlerts = async () => {
    const alertsData = await getAlerts()
    setAlerts(alertsData)
    setLastSync(new Date())
  }

  const updateQueueCount = async () => {
    const count = await getQueueCount()
    setQueueCount(count)
  }

  const handleSync = async () => {
    await syncOfflineReports()
    await updateQueueCount()
    setLastSync(new Date())
  }

  const saveProfile = () => {
    setProfile(profileDraft)
    localStorage.setItem(PROFILE_STORAGE_KEY, JSON.stringify(profileDraft))
    setProfileSaved(true)
    setTimeout(() => setProfileSaved(false), 2000)
  }

  const handleSubmit = async () => {
    if (!location) {
      getLocation()
      return
    }

    setSubmitting(true)
    setSubmitResult(null)

    const report = {
      id: crypto.randomUUID(),
      location,
      accuracy_m: 10,
      kind: reportKind,
      note: note || null,
      media_url: photo,
      media_type: photo ? 'image' : null,
      reporter_hash: btoa(crypto.randomUUID()),
      lang: 'en',
      created_at: new Date().toISOString()
    }

    try {
      const result = await submitReport(report)
      setSubmitResult(result)
      await updateQueueCount()
    } catch (error) {
      setSubmitResult({ queued: true, id: report.id })
    }

    setSubmitting(false)
    setNote('')
    setPhoto(null)
  }

  const handleSOS = () => {
    setView('sos-countdown')
    setCountdown(3)
    setSending(true)
  }

  useEffect(() => {
    if (sending && countdown > 0 && view === 'sos-countdown') {
      const timer = setTimeout(() => setCountdown(countdown - 1), 1000)
      return () => clearTimeout(timer)
    } else if (sending && countdown === 0 && view === 'sos-countdown') {
      sendEmergency()
    }
  }, [sending, countdown, view])

  const sendEmergency = async () => {
    if (!location) {
      getLocation()
      return
    }

    const emergency = {
      id: crypto.randomUUID(),
      location,
      people_count: profile.householdSize,
      category: 'medical',
      note: 'Emergency danger signal',
      status: 'open',
      created_at: new Date().toISOString()
    }

    try {
      const API_BASE = import.meta.env.VITE_API_BASE || '/api'
      const response = await fetch(`${API_BASE}/requests`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(emergency)
      })
      if (response.ok) {
        setSubmitResult({ queued: false, id: emergency.id })
      } else {
        setSubmitResult({ queued: true, id: emergency.id })
      }
    } catch (error) {
      setSubmitResult({ queued: true, id: emergency.id })
    }

    setSending(false)
    setView('sos-sent')
  }

  const cancelSOS = () => {
    setSending(false)
    setCountdown(3)
    setView('home')
  }

  const isMainView = view === 'home' || view === 'report' || view === 'alerts' || view === 'profile'

  return (
    <div className="min-h-screen bg-ground-000 text-ink-000 flex flex-col">
      {/* Header */}
      <header className="sticky top-0 z-10 h-14 border-b border-ground-300 bg-ground-100/95 backdrop-blur px-4 flex items-center justify-between shadow-sm shrink-0">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-xl bg-ink-000 text-ground-100 flex items-center justify-center font-display font-bold text-16">Q</div>
          <div className="font-display font-semibold text-18">Q-ResQ</div>
        </div>
        <div className="flex items-center gap-2">
          <span
            className={`flex items-center gap-1.5 text-13 font-medium px-2.5 py-1 rounded-full ${
              isOnline ? 'bg-sev-0/10 text-sev-0' : 'bg-ink-300/15 text-ink-200'
            }`}
          >
            <span className={`w-1.5 h-1.5 rounded-full ${isOnline ? 'bg-sev-0 animate-pulse' : 'bg-ink-300'}`} />
            {sending ? 'Sending…' : isOnline ? 'Online' : 'No signal'}
          </span>
        </div>
      </header>

      <main className="flex-1">
      {view === 'home' && (
        <div className="p-4 space-y-4 pb-6">
          {/* Status strip */}
          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-2xl border border-ground-300 bg-ground-100 p-3 shadow-sm">
              <div className="text-12 text-ink-200 mb-0.5">Your location</div>
              <div className="font-data text-14 text-ink-000">
                {location ? `${location[0].toFixed(3)}, ${location[1].toFixed(3)}` : 'Locating…'}
              </div>
            </div>
            <div className="rounded-2xl border border-ground-300 bg-ground-100 p-3 shadow-sm">
              <div className="text-12 text-ink-200 mb-0.5">Last updated</div>
              <div className="font-data text-14 text-ink-000">
                {lastSync ? lastSync.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '—'}
              </div>
            </div>
          </div>

          {/* Risk Banner */}
          <div
            className="rounded-2xl p-4 shadow-md"
            style={{ backgroundColor: SEVERITY_COLORS[severityBand] }}
          >
            <div className="flex items-center gap-2 mb-2">
              <div className="w-2.5 h-2.5 rounded-full bg-white"></div>
              <span className="font-display font-semibold text-18 text-white tracking-wide">
                {SEVERITY_BANDS[severityBand]}
              </span>
            </div>
            <div className="text-white text-16 font-medium mb-1">{profile.areaName}</div>
            <div className="text-white text-14 opacity-90">
              Heavy rain over the last 3 days. Slopes near you are at raised risk.
            </div>
            <div className="flex items-center justify-between mt-3">
              <span className="text-white text-13 opacity-75">
                Updated {lastSync ? lastSync.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '14:22'}
              </span>
              <button
                onClick={() => location && window.open(`https://www.google.com/maps?q=${location[0]},${location[1]}`, '_blank')}
                className="text-white text-13 font-medium bg-white/15 rounded-full px-3 py-1.5"
              >
                View map
              </button>
            </div>
          </div>

          {/* SOS Button */}
          <button
            onClick={handleSOS}
            className="w-full rounded-2xl text-white text-center py-5 shadow-lg active:scale-[0.99] transition-transform"
            style={{ background: 'linear-gradient(180deg, #C23B22 0%, #A32C17 100%)', minHeight: '96px' }}
          >
            <div className="font-display font-bold text-22 tracking-wide">EMERGENCY</div>
            <div className="text-14 opacity-90 mt-0.5">Tap if you need help right now</div>
          </button>

          {/* Quick actions */}
          <div className="grid grid-cols-2 gap-3">
            <button
              onClick={() => setView('report')}
              className="rounded-2xl border border-ground-300 bg-ground-100 p-4 text-left shadow-sm active:bg-ground-200"
            >
              <div className="w-9 h-9 rounded-full bg-sev-1/15 text-sev-1 flex items-center justify-center mb-2">
                <WarningIcon className="w-5 h-5" />
              </div>
              <div className="font-medium text-15">Report</div>
              <div className="text-13 text-ink-200">Cracks, slipping, blocked roads</div>
            </button>
            <button
              onClick={() => setView('alerts')}
              className="rounded-2xl border border-ground-300 bg-ground-100 p-4 text-left shadow-sm active:bg-ground-200"
            >
              <div className="w-9 h-9 rounded-full bg-ink-000/10 text-ink-000 flex items-center justify-center mb-2">
                <BellIcon className="w-5 h-5" />
              </div>
              <div className="font-medium text-15 flex items-center gap-2">
                Alerts
                {alerts.length > 0 && (
                  <span className="text-11 bg-emergency text-white rounded-full w-5 h-5 flex items-center justify-center">
                    {alerts.length}
                  </span>
                )}
              </div>
              <div className="text-13 text-ink-200">Official warnings for your area</div>
            </button>
          </div>

          {/* Queue Footer */}
          {queueCount > 0 && (
            <div className="rounded-2xl border border-ground-300 bg-ground-100 shadow-sm flex items-center justify-between px-4 py-3">
              <span className="text-14 text-ink-200">
                {queueCount} report{queueCount > 1 ? 's' : ''} waiting to send
              </span>
              <button
                onClick={handleSync}
                className="flex items-center gap-1.5 text-14 text-sev-1 font-medium rounded-full bg-sev-1/10 px-3 py-1.5"
              >
                <SyncIcon className="w-3.5 h-3.5" />
                Sync now
              </button>
            </div>
          )}
        </div>
      )}

      {view === 'sos-countdown' && (
        <div
          className="p-4 text-center min-h-[calc(100vh-112px)] flex flex-col justify-center"
          style={{ background: 'linear-gradient(180deg, #B02E18 0%, #6E1810 100%)' }}
        >
          <div className="font-display text-18 mb-6 text-white tracking-[0.1em]">SENDING IN</div>
          <div className="font-data font-bold mb-6 text-white" style={{ fontSize: '96px', lineHeight: 1 }}>
            {countdown}
          </div>
          <div className="text-15 text-white/85 mb-10 px-6">
            Your location and details will be sent to the district emergency team.
          </div>
          <button
            onClick={cancelSOS}
            className="w-full rounded-2xl border-2 border-white/40 bg-white/10 text-white font-display font-semibold text-16 py-5 active:bg-white/20"
            style={{ minHeight: '72px' }}
          >
            CANCEL
          </button>
        </div>
      )}

      {view === 'sos-sent' && (
        <div className="p-4 pb-6">
          <div className="rounded-2xl bg-sev-0/10 border border-sev-0/30 p-4 flex items-center gap-3 mb-4">
            <div className="w-10 h-10 rounded-full bg-sev-0 text-white flex items-center justify-center shrink-0">
              <CheckIcon className="w-5 h-5" />
            </div>
            <div>
              <div className="font-display font-semibold text-18 text-sev-0">Sent</div>
              <div className="text-14 text-ink-100">Your emergency alert has been received by the district team.</div>
            </div>
          </div>

          <div className="rounded-2xl border border-ground-300 bg-ground-100 shadow-sm p-4 mb-4 space-y-2 font-data text-14">
            <div className="flex justify-between"><span className="text-ink-200">Sent at</span><span>{new Date().toLocaleTimeString()}</span></div>
            <div className="flex justify-between"><span className="text-ink-200">Reference</span><span>SOS-0184</span></div>
            <div className="flex justify-between">
              <span className="text-ink-200">Location</span>
              <span>{location ? `${location[0].toFixed(4)}, ${location[1].toFixed(4)}` : 'Pending'}</span>
            </div>
            <div className="flex justify-between"><span className="text-ink-200">People</span><span>{profile.householdSize}</span></div>
          </div>

          <div className="rounded-2xl border border-ground-300 bg-ground-100 shadow-sm p-4 mb-4">
            <div className="font-medium text-16 mb-3">What happens next</div>
            <div className="space-y-3 text-14">
              <div className="flex items-center gap-3">
                <div className="w-5 h-5 rounded-full bg-sev-0 text-white flex items-center justify-center">
                  <CheckIcon className="w-3 h-3" />
                </div>
                <span>Received</span>
              </div>
              <div className="flex items-center gap-3">
                <div className="w-5 h-5 rounded-full border-2 border-ground-400"></div>
                <span className="text-ink-200">Being assessed</span>
              </div>
              <div className="flex items-center gap-3">
                <div className="w-5 h-5 rounded-full border-2 border-ground-400"></div>
                <span className="text-ink-200">Help assigned</span>
              </div>
            </div>
          </div>
          <button
            onClick={() => setView('home')}
            className="w-full rounded-2xl border border-ground-300 bg-ground-100 text-ink-000 font-medium text-16 py-4 shadow-sm active:bg-ground-200"
            style={{ minHeight: '56px' }}
          >
            Add more information
          </button>
        </div>
      )}

      {view === 'report' && (
        <div className="p-4 space-y-4 pb-6">
          <h2 className="font-display font-semibold text-22">Report landslide sign</h2>
          <p className="text-14 text-ink-200 -mt-2">Every detail helps the district team assess risk faster.</p>

          <div className="rounded-2xl border border-ground-300 bg-ground-100 shadow-sm p-4">
            <label className="text-13 text-ink-200 block mb-1.5 font-medium">Location</label>
            {location ? (
              <span className="font-data text-14">{location[0].toFixed(4)}, {location[1].toFixed(4)}</span>
            ) : (
              <button onClick={getLocation} className="text-14 text-sev-1 font-medium">
                Get location
              </button>
            )}
          </div>

          <div className="rounded-2xl border border-ground-300 bg-ground-100 shadow-sm p-4">
            <label className="text-13 text-ink-200 block mb-1.5 font-medium">Type</label>
            <select
              value={reportKind}
              onChange={(e) => setReportKind(e.target.value as any)}
              className="w-full text-14 bg-transparent -ml-0.5 focus:outline-none"
            >
              <option value="crack">Crack in the ground</option>
              <option value="slope_movement">Slope slipping or bulging</option>
              <option value="road_blocked">Road blocked</option>
              <option value="water_seepage">Water coming out of a slope</option>
              <option value="other">Something else</option>
            </select>
          </div>

          <div className="rounded-2xl border border-ground-300 bg-ground-100 shadow-sm p-4">
            <label className="text-13 text-ink-200 block mb-1.5 font-medium">Note</label>
            <textarea
              value={note}
              onChange={(e) => setNote(e.target.value)}
              className="w-full text-14 focus:outline-none resize-none"
              rows={3}
              placeholder="Describe what you see..."
            />
          </div>

          <div>
            <label className="text-13 text-ink-200 block mb-1.5 font-medium px-1">Photo (optional)</label>
            {photo ? (
              <div className="relative rounded-2xl border border-ground-300 bg-ground-100 shadow-sm overflow-hidden">
                <img src={photo} alt="Attached report photo" className="w-full max-h-64 object-cover block" />
                <button
                  onClick={() => setPhoto(null)}
                  className="absolute top-2 right-2 h-8 px-3 flex items-center gap-1.5 bg-ink-000/85 text-white text-13 font-medium rounded-full"
                >
                  <CloseIcon className="w-3.5 h-3.5" />
                  Remove
                </button>
              </div>
            ) : (
              <div className="grid grid-cols-2 gap-3">
                <button
                  onClick={() => document.getElementById('camera-input')?.click()}
                  className="flex flex-col items-center justify-center gap-1.5 h-24 rounded-2xl border-2 border-dashed border-ground-400 bg-ground-100 text-ink-100 text-13 font-medium shadow-sm cursor-pointer active:bg-ground-200"
                >
                  <CameraIcon className="w-6 h-6" />
                  Take photo
                  <input
                    id="camera-input"
                    type="file"
                    accept="image/*"
                    capture="environment"
                    onChange={handlePhotoChange}
                    className="hidden"
                  />
                </button>
                <button
                  onClick={() => document.getElementById('gallery-input')?.click()}
                  className="flex flex-col items-center justify-center gap-1.5 h-24 rounded-2xl border-2 border-dashed border-ground-400 bg-ground-100 text-ink-100 text-13 font-medium shadow-sm cursor-pointer active:bg-ground-200"
                >
                  <GalleryIcon className="w-6 h-6" />
                  From gallery
                  <input
                    id="gallery-input"
                    type="file"
                    accept="image/*"
                    onChange={handlePhotoChange}
                    className="hidden"
                  />
                </button>
              </div>
            )}
            {photoError && <p className="text-13 text-emergency mt-1.5 px-1">{photoError}</p>}
          </div>

          <button
            onClick={handleSubmit}
            disabled={submitting || !location}
            className="w-full rounded-2xl bg-ink-000 text-ground-100 font-display font-semibold text-16 py-4 shadow-md active:opacity-90 disabled:opacity-40"
            style={{ minHeight: '56px' }}
          >
            {submitting ? 'Submitting...' : 'Send report'}
          </button>

          {submitResult && (
            <div className="rounded-2xl border border-sev-0/30 bg-sev-0/10 text-sev-0 p-3 text-14 font-medium text-center">
              {submitResult.queued ? 'Saved on your phone. Will send when you have signal.' : 'Report sent.'}
            </div>
          )}
        </div>
      )}

      {view === 'alerts' && (
        <div className="p-4 space-y-3 pb-6">
          <h2 className="font-display font-semibold text-22 mb-1">Alerts</h2>

          {alerts.length === 0 ? (
            <div className="rounded-2xl border border-ground-300 bg-ground-100 shadow-sm p-8 text-center">
              <div className="w-12 h-12 rounded-full bg-sev-0/10 text-sev-0 flex items-center justify-center mx-auto mb-3">
                <CheckIcon className="w-6 h-6" />
              </div>
              <p className="text-14 text-ink-200">No active alerts for your area right now.</p>
            </div>
          ) : (
            alerts.map((alert) => (
              <div key={alert.id} className="rounded-2xl border-l-4 border-l-emergency border border-ground-300 bg-ground-100 shadow-sm p-4">
                <div className="font-medium text-16">{alert.headline}</div>
                <div className="text-14 text-ink-200 mt-1">{alert.description}</div>
              </div>
            ))
          )}
        </div>
      )}

      {view === 'profile' && (
        <div className="p-4 space-y-4 pb-6">
          <h2 className="font-display font-semibold text-22 mb-1">Profile</h2>

          <div className="rounded-2xl border border-ground-300 bg-ground-100 shadow-sm p-4 space-y-4">
            <div>
              <label className="text-13 text-ink-200 block mb-1.5 font-medium">Household size</label>
              <input
                type="number"
                min={1}
                max={20}
                value={profileDraft.householdSize}
                onChange={(e) => setProfileDraft({ ...profileDraft, householdSize: Math.max(1, parseInt(e.target.value) || 1) })}
                className="w-full text-14 font-data focus:outline-none border-b border-ground-300 pb-1.5 bg-transparent"
              />
            </div>
            <div>
              <label className="text-13 text-ink-200 block mb-1.5 font-medium">Area</label>
              <input
                type="text"
                value={profileDraft.areaName}
                onChange={(e) => setProfileDraft({ ...profileDraft, areaName: e.target.value })}
                className="w-full text-14 focus:outline-none border-b border-ground-300 pb-1.5 bg-transparent"
              />
            </div>
            <div>
              <label className="text-13 text-ink-200 block mb-1.5 font-medium">Language</label>
              <select
                value={profileDraft.language}
                onChange={(e) => setProfileDraft({ ...profileDraft, language: e.target.value as Profile['language'] })}
                className="w-full text-14 focus:outline-none border-b border-ground-300 pb-1.5 bg-transparent"
              >
                <option>English</option>
                <option>Hindi</option>
                <option>Assamese</option>
              </select>
            </div>
            <button
              onClick={saveProfile}
              className="w-full rounded-2xl bg-ink-000 text-ground-100 font-display font-semibold text-15 py-3 active:opacity-90"
            >
              {profileSaved ? 'Saved' : 'Save changes'}
            </button>
          </div>

          <div className="rounded-2xl border border-ground-300 bg-ground-100 shadow-sm p-4 flex items-start gap-3">
            <ShieldIcon className="w-5 h-5 text-ink-200 shrink-0 mt-0.5" />
            <div className="text-13 text-ink-200">
              Reports and emergency alerts are linked to a device identifier only. We never store your name or contact details.
            </div>
          </div>

          <div className="text-center pt-2">
            <div className="text-12 text-ink-300 font-data">Q-ResQ · v1.0.0</div>
            <div className="text-12 text-ink-300">Aizawl district, Mizoram</div>
          </div>
        </div>
      )}
      </main>

      {/* Bottom navigation */}
      {isMainView && (
        <nav className="sticky bottom-0 z-10 bg-ground-100/95 backdrop-blur border-t border-ground-300 shadow-[0_-2px_8px_rgba(0,0,0,0.04)] px-2 py-1.5 flex items-center justify-around shrink-0">
          {([
            { key: 'home', label: 'Home', Icon: HomeIcon },
            { key: 'report', label: 'Report', Icon: WarningIcon },
            { key: 'alerts', label: 'Alerts', Icon: BellIcon },
            { key: 'profile', label: 'Profile', Icon: UserIcon },
          ] as const).map((item) => (
            <button
              key={item.key}
              onClick={() => setView(item.key)}
              className={`flex flex-col items-center gap-0.5 px-4 py-1.5 rounded-xl text-12 font-medium min-w-[64px] ${
                view === item.key ? 'text-ink-000 bg-ground-200' : 'text-ink-300'
              }`}
            >
              <item.Icon className="w-5 h-5" />
              {item.label}
            </button>
          ))}
        </nav>
      )}
    </div>
  )
}

export default App
