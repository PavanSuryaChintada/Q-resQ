import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { createRoot } from "react-dom/client"
import App from "./App"
import "./styles/tokens.css"
import "maplibre-gl/dist/maplibre-gl.css"

const queryClient = new QueryClient({
  defaultOptions: { queries: { refetchOnWindowFocus: false } },
})

// No StrictMode: its dev-mode double-mount (mount -> cleanup -> mount,
// synchronously, to catch non-idempotent effects) was creating two
// MapLibre instances sharing the same container ref. Every addLayer/
// setData call landed on the "logical" instance MapView's own state
// tracked (hence every diagnostic log reporting success), while a
// different instance ended up the one actually attached to the DOM -
// so nothing our code did ever appeared on screen. StrictMode only
// runs in dev; production builds were never affected.
createRoot(document.getElementById("root")!).render(
  <QueryClientProvider client={queryClient}>
    <App />
  </QueryClientProvider>,
)
