import { Component, type ReactNode } from 'react'

/** Red de seguridad: si algo se rompe, se ve un mensaje y un botón, nunca pantalla en blanco. */
export class ErrorBoundary extends Component<{ children: ReactNode }, { roto: boolean }> {
  state = { roto: false }
  static getDerivedStateFromError() {
    return { roto: true }
  }
  render() {
    if (!this.state.roto) return this.props.children
    return (
      <main className="flex h-full flex-col items-center justify-center gap-8 text-center">
        <p className="text-[34px] font-bold">Ups, algo salió mal.</p>
        <button type="button" className="min-h-[72px] rounded-2xl bg-naranja px-10 text-[26px] font-bold text-[#1a1208]" onClick={() => location.reload()}>
          Volver al inicio
        </button>
      </main>
    )
  }
}
