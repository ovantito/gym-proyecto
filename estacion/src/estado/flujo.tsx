/** Estado del flujo en UN solo lugar: un reducer + acciones que llaman al backend. */
import { createContext, useCallback, useContext, useEffect, useMemo, useReducer, useRef, type ReactNode } from 'react'
import * as api from '../api/cliente'
import type { FichaIn, FichaOut, FichaPrevia, RutinaOut, Semaforo } from '../api/cliente'
import { lecturaImposible, lecturaNormal, lecturaPresionAlta, type Lectura } from './simulador'

export type Pantalla = 'identificacion' | 'medicion' | 'salud' | 'semaforo' | 'rutina' | 'ticket'

export interface Estado {
  pantalla: Pantalla
  cargando: boolean
  error: string | null
  socio: { id: string; nombre: string; semaforo: Semaforo } | null
  sesionId: string | null
  lectura: Lectura | null
  /** true = el backend (Mean-Shift) marcó la lectura como atípica y no se usa */
  atipica: boolean
  medicionValida: boolean
  ficha: FichaOut | null
  /** ficha que el socio ya tenía guardada (null si es su primera vez) */
  fichaPrevia: FichaPrevia | null
  rutina: RutinaOut | null
  /** motivo escrito por el coach si rechazó la rutina */
  motivoRechazo: string | null
  espera: Record<string, number>
}

export const estadoInicial: Estado = {
  pantalla: 'identificacion',
  cargando: false,
  error: null,
  socio: null,
  sesionId: null,
  lectura: null,
  atipica: false,
  medicionValida: false,
  ficha: null,
  fichaPrevia: null,
  rutina: null,
  motivoRechazo: null,
  espera: {},
}

type Accion =
  | { t: 'cargando' }
  | { t: 'error'; mensaje: string }
  | { t: 'limpiar_error' }
  | { t: 'sesion'; sesionId: string; socio: Estado['socio']; fichaPrevia: FichaPrevia | null }
  | { t: 'lectura'; lectura: Lectura }
  | { t: 'medicion'; atipica: boolean }
  | { t: 'ir'; pantalla: Pantalla }
  | { t: 'ficha'; ficha: FichaOut }
  | { t: 'rutina'; rutina: RutinaOut; espera: Record<string, number> }
  | { t: 'estado_rutina'; estado: RutinaOut['estado']; motivo: string | null }
  | { t: 'reiniciar' }

export function reducer(e: Estado, a: Accion): Estado {
  switch (a.t) {
    case 'cargando':
      return { ...e, cargando: true, error: null }
    case 'error':
      return { ...e, cargando: false, error: a.mensaje }
    case 'limpiar_error':
      return { ...e, error: null }
    case 'sesion':
      return { ...estadoInicial, pantalla: 'medicion', sesionId: a.sesionId, socio: a.socio, fichaPrevia: a.fichaPrevia }
    case 'lectura':
      return { ...e, cargando: true, error: null, lectura: a.lectura, atipica: false, medicionValida: false }
    case 'medicion':
      return { ...e, cargando: false, atipica: a.atipica, medicionValida: !a.atipica }
    case 'ir':
      return { ...e, pantalla: a.pantalla, error: null, cargando: false }
    case 'ficha':
      return { ...e, cargando: false, ficha: a.ficha, pantalla: 'semaforo' }
    case 'rutina':
      return { ...e, cargando: false, rutina: a.rutina, espera: a.espera, pantalla: 'rutina' }
    case 'estado_rutina':
      return e.rutina ? { ...e, rutina: { ...e.rutina, estado: a.estado }, motivoRechazo: a.motivo } : e
    case 'reiniciar':
      return estadoInicial // borra TODOS los datos del socio de la memoria
  }
}

interface Flujo {
  estado: Estado
  identificar: (dni: string) => Promise<void>
  medir: (tipo?: 'normal' | 'imposible' | 'presion_alta') => Promise<void>
  irA: (p: Pantalla) => void
  enviarFicha: (f: FichaIn) => Promise<void>
  verRutina: () => Promise<void>
  /** Consulta silenciosa del estado de la rutina (aprobada / rechazada por el coach). */
  consultarRutina: () => Promise<void>
  limpiarError: () => void
  reiniciar: () => void
}

const Ctx = createContext<Flujo | null>(null)

export function ProveedorFlujo({ children }: { children: ReactNode }) {
  const [estado, dispatch] = useReducer(reducer, estadoInicial)
  const generacion = useRef(0) // si se reinicia (inactividad), las respuestas tardías se descartan
  const ref = useRef(estado)
  useEffect(() => {
    ref.current = estado
  })

  /** Ejecuta una operación; ignora su resultado si el flujo se reinició mientras tanto. */
  const correr = useCallback(async (fn: () => Promise<void>) => {
    const g = generacion.current
    dispatch({ t: 'cargando' })
    try {
      await fn()
    } catch (e) {
      if (g === generacion.current)
        dispatch({ t: 'error', mensaje: e instanceof api.ErrorApi ? e.message : api.MSG_SIN_CONEXION })
    }
  }, [])
  const vigente = (g: number) => g === generacion.current

  const acciones = useMemo<Flujo>(
    () => ({
      estado,
      identificar: (dni) =>
        correr(async () => {
          const g = generacion.current
          const r = await api.abrirSesion({ dni })
          // La ficha guardada es opcional: si no se puede leer, el socio simplemente la llena de nuevo.
          const previa = await api.obtenerFicha(r.socio.id).catch(() => null)
          if (vigente(g)) dispatch({ t: 'sesion', sesionId: r.sesionId, socio: r.socio, fichaPrevia: previa?.existe ? previa : null })
        }),
      medir: async (tipo = 'normal') => {
        const imposible = tipo === 'imposible'
        const { socio, sesionId } = ref.current
        if (!socio) return
        const g = generacion.current
        const enviar = (l: Lectura) =>
          api.registrarMedicion(socio.id, {
            peso_kg: l.peso, grasa_pct: l.grasa, presion_sistolica: l.sistolica,
            presion_diastolica: l.diastolica, pulso_reposo: l.pulso, ...(sesionId ? { sesion_id: sesionId } : {}),
          })
        const lectura =
          tipo === 'imposible' ? lecturaImposible(socio.id) : tipo === 'presion_alta' ? lecturaPresionAlta(socio.id) : lecturaNormal(socio.id)
        dispatch({ t: 'lectura', lectura })
        try {
          // El backend compara contra la última lectura VÁLIDA: para que el salto se note, primero
          // se asegura una base válida en esta sesión (en la demo equivale a "la medición de ayer").
          if (imposible && !ref.current.medicionValida) await enviar(lecturaNormal(socio.id))
          const r = await enviar(lectura)
          if (vigente(g)) dispatch({ t: 'medicion', atipica: r.atipica })
        } catch (e) {
          if (vigente(g)) dispatch({ t: 'error', mensaje: e instanceof api.ErrorApi ? e.message : api.MSG_SIN_CONEXION })
        }
      },
      irA: (pantalla) => dispatch({ t: 'ir', pantalla }),
      enviarFicha: (f) =>
        correr(async () => {
          const g = generacion.current
          const r = await api.guardarFicha(ref.current.socio!.id, f)
          if (vigente(g)) dispatch({ t: 'ficha', ficha: r })
        }),
      verRutina: () =>
        correr(async () => {
          const g = generacion.current
          const rutina = await api.generarRutina(ref.current.socio!.id)
          // La espera por máquina es opcional: si falla, la rutina se muestra igual.
          const espera = await api.obtenerEspera().then((x) => x.esperaMin).catch(() => ({}))
          if (vigente(g)) dispatch({ t: 'rutina', rutina, espera })
        }),
      consultarRutina: async () => {
        const g = generacion.current
        const id = ref.current.rutina?.rutinaId
        if (!id) return
        try {
          const r = await api.obtenerEstadoRutina(id)
          if (vigente(g) && r.estado !== 'archivada' && r.estado !== ref.current.rutina?.estado)
            dispatch({ t: 'estado_rutina', estado: r.estado, motivo: r.motivoRechazo })
        } catch {
          /* sin red por un momento: se vuelve a intentar en 5 s */
        }
      },
      limpiarError: () => dispatch({ t: 'limpiar_error' }),
      reiniciar: () => {
        generacion.current++
        dispatch({ t: 'reiniciar' })
      },
    }),
    [estado, correr],
  )
  return <Ctx.Provider value={acciones}>{children}</Ctx.Provider>
}

export function useFlujo(): Flujo {
  const c = useContext(Ctx)
  if (!c) throw new Error('useFlujo fuera de ProveedorFlujo')
  return c
}
