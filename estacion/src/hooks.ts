import { useEffect } from 'react'

/** Llama a `alExpirar` si nadie toca la pantalla durante `ms`. Cualquier toque reinicia la cuenta. */
export function useInactividad(ms: number, alExpirar: () => void, activo = true) {
  useEffect(() => {
    if (!activo) return
    let t = setTimeout(alExpirar, ms)
    const reiniciar = () => {
      clearTimeout(t)
      t = setTimeout(alExpirar, ms)
    }
    const eventos = ['pointerdown', 'keydown', 'touchstart'] as const
    eventos.forEach((e) => window.addEventListener(e, reiniciar))
    return () => {
      clearTimeout(t)
      eventos.forEach((e) => window.removeEventListener(e, reiniciar))
    }
  }, [ms, alExpirar, activo])
}
