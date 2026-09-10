import { useEffect, useRef, useState } from 'react'
import { CloseIcon } from './icons'

interface Props {
  onCapture: (dataUrl: string) => void
  onClose: () => void
}

// Real in-page camera via getUserMedia - works on desktop (asks for
// webcam permission, like the user asked) as well as mobile, unlike
// <input capture> which desktop Chrome silently ignores and just opens
// a file picker.
export function CameraCapture({ onCapture, onClose }: Props) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [ready, setReady] = useState(false)

  useEffect(() => {
    let cancelled = false

    async function start() {
      if (!navigator.mediaDevices?.getUserMedia) {
        setError('Camera access is not available in this browser.')
        return
      }
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: 'environment' },
          audio: false,
        })
        if (cancelled) {
          stream.getTracks().forEach((t) => t.stop())
          return
        }
        streamRef.current = stream
        if (videoRef.current) {
          videoRef.current.srcObject = stream
          await videoRef.current.play()
          setReady(true)
        }
      } catch (err) {
        if (cancelled) return
        const name = (err as DOMException)?.name
        if (name === 'NotAllowedError') {
          setError('Camera permission was denied. Allow camera access, or choose from gallery instead.')
        } else if (name === 'NotFoundError') {
          setError('No camera found on this device.')
        } else {
          setError('Could not open the camera. Choose from gallery instead.')
        }
      }
    }

    start()
    return () => {
      cancelled = true
      streamRef.current?.getTracks().forEach((t) => t.stop())
    }
  }, [])

  const handleCapture = () => {
    const video = videoRef.current
    if (!video) return
    const canvas = document.createElement('canvas')
    canvas.width = video.videoWidth
    canvas.height = video.videoHeight
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    ctx.drawImage(video, 0, 0)
    onCapture(canvas.toDataURL('image/jpeg', 0.85))
  }

  return (
    <div className="fixed inset-0 z-50 bg-black flex flex-col">
      <div className="h-14 flex items-center justify-between px-4 shrink-0">
        <span className="text-white font-display font-semibold text-16">Take photo</span>
        <button onClick={onClose} className="text-white p-2 -mr-2">
          <CloseIcon className="w-6 h-6" />
        </button>
      </div>

      <div className="flex-1 relative flex items-center justify-center">
        {error ? (
          <div className="p-6 text-center">
            <p className="text-white text-14">{error}</p>
          </div>
        ) : (
          <video ref={videoRef} playsInline muted className="w-full h-full object-cover" />
        )}
      </div>

      <div className="h-24 flex items-center justify-center shrink-0 pb-4">
        {!error && (
          <button
            onClick={handleCapture}
            disabled={!ready}
            aria-label="Capture photo"
            className="w-16 h-16 rounded-full bg-white border-4 border-white/40 active:scale-95 transition-transform disabled:opacity-40"
          />
        )}
      </div>
    </div>
  )
}
