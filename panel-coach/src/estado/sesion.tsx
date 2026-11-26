/** Sesión del panel: token + rol. Se guarda en sessionStorage (se borra al cerrar la pestaña). */
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import * as api from '../api/cliente'
import type { Rol } from '../api/cliente'

interface Usuario {
  token: string
  rol: Rol
  nombre: string
}

interface Sesion {
  usuario: Usuario | null
  aviso: string | null
  /** Solo admin: id del coach cuyo panel se está viendo (null = todos). Se pasa como ?coach_id= a los listados. */
  coachVista: string | null
  fijarCoachVista: (id: string | null) => void
  entrar: (email: string, password: string) => Promise<void>
  salir: (aviso?: string) => void
}

const CLAVE = 'tnt-panel-sesion'
const Ctx = createContext<Sesion | null>(null)

function leer(): Usuario | null {
  try {
    const u = JSON.parse(sessionStorage.getItem(CLAVE) ?? 'null') as Usuario | null
    if (u) api.fijarToken(u.token)
    return u
  } catch {
    return null
  }
}

export function ProveedorSesion({ children }: { children: ReactNode }) {
  const [usuario, setUsuario] = useState<Usuario | null>(leer)
  const [aviso, setAviso] = useState<string | null>(null)
  const [coachVista, setCoachVista] = useState<string | null>(null)

  const salir = useCallback((msg?: string) => {
    api.fijarToken(null)
    try {
      sessionStorage.removeItem(CLAVE)
    } catch {
      /* sin storage */
    }
    setUsuario(null)
    setCoachVista(null)
    setAviso(msg ?? null)
  }, [])

  useEffect(() => {
    api.alSesionExpirada(() => salir('Tu sesión venció. Entra de nuevo.'))
    return () => api.alSesionExpirada(null)
  }, [salir])

  const valor = useMemo<Sesion>(
    () => ({
      usuario,
      aviso,
      salir,
      // un coach nunca ve «como otro»: el backend lo ignoraría, y aquí ni se guarda
      coachVista: usuario?.rol === 'admin' ? coachVista : null,
      fijarCoachVista: setCoachVista,
      entrar: async (email, password) => {
        const r = await api.login(email, password) // lanza ErrorApi si falla
        const u = { token: r.token, rol: r.rol, nombre: r.nombre }
        api.fijarToken(u.token)
        try {
          sessionStorage.setItem(CLAVE, JSON.stringify(u))
        } catch {
          /* sin storage: la sesión vive solo en memoria */
        }
        setAviso(null)
        setUsuario(u)
      },
    }),
    [usuario, aviso, coachVista, salir],
  )
  return <Ctx.Provider value={valor}>{children}</Ctx.Provider>
}

export function useSesion(): Sesion {
  const c = useContext(Ctx)
  if (!c) throw new Error('useSesion fuera de ProveedorSesion')
  return c
}
