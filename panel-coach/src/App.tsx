import { Component, type ReactNode } from 'react'
import { ProveedorSesion, useSesion } from './estado/sesion'
import { Login, Panel } from './pantallas'

class ErrorBoundary extends Component<{ children: ReactNode }, { roto: boolean }> {
  state = { roto: false }
  static getDerivedStateFromError() {
    return { roto: true }
  }
  render() {
    if (!this.state.roto) return this.props.children
    return (
      <main className="flex h-full flex-col items-center justify-center gap-6">
        <p className="text-[26px] font-bold">Ups, algo salió mal.</p>
        <button type="button" className="rounded-xl bg-naranja px-6 py-3 font-bold text-[#1a1208]" onClick={() => location.reload()}>
          Recargar
        </button>
      </main>
    )
  }
}

function Raiz() {
  const { usuario } = useSesion()
  return usuario ? <Panel /> : <Login />
}

export default function App() {
  return (
    <ErrorBoundary>
      <ProveedorSesion>
        <Raiz />
      </ProveedorSesion>
    </ErrorBoundary>
  )
}
