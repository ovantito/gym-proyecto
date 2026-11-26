import { useCallback, useEffect, useRef, useState } from 'react'
import { ErrorApi } from './api/cliente'

export interface Carga<T> {
  datos: T | null
  cargando: boolean
  error: string | null
  recargar: () => void
}

/** Carga datos al montar y cada vez que cambia `clave` (p. ej. tras correr el análisis nocturno).
 *  `cadaMs` repite la carga en silencio (sin parpadeo) para ver cambios casi en vivo. */
export function useCarga<T>(fn: () => Promise<T>, clave: unknown = 0, cadaMs?: number): Carga<T> {
  const [datos, setDatos] = useState<T | null>(null)
  const [cargando, setCargando] = useState(true) // solo la primera carga; luego se refresca sin parpadeo
  const [error, setError] = useState<string | null>(null)
  const fnRef = useRef(fn)
  const hayDatos = useRef(false)
  useEffect(() => {
    fnRef.current = fn
  })

  const cargar = useCallback(async () => {
    try {
      const d = await fnRef.current()
      hayDatos.current = true
      setDatos(d)
      setError(null)
    } catch (e) {
      if (!hayDatos.current) setError(e instanceof ErrorApi ? e.message : 'Algo salió mal.')
    } finally {
      setCargando(false)
    }
  }, [])

  useEffect(() => {
    void cargar()
    if (!cadaMs) return
    const t = setInterval(() => void cargar(), cadaMs)
    return () => clearInterval(t)
  }, [cargar, clave, cadaMs])

  return { datos, cargando, error, recargar: () => void cargar() }
}
