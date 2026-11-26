/**
 * Cliente único del backend para el panel del coach. Los tipos reflejan las respuestas reales de
 * backend/app/modulos (auth.py, coach.py, prediccion.py).
 */

// ---------------------------------------------------------------- tipos
export type Rol = 'coach' | 'admin'
export type Semaforo = 'verde' | 'amarillo' | 'rojo'
export type Nivel = 'alto' | 'medio' | 'bajo'

/** POST /v1/auth/login */
export interface LoginOut {
  token: string
  rol: Rol
  nombre: string
  expiraEnSeg: number
}

export interface Ejercicio {
  id: string
  nombre: string
  maquina: string
  series: number
  repeticiones: number
  descansoSeg: number
}

/** GET /v1/coach/rutinas-pendientes (filas de la tabla rutinas + datos del socio y de su ficha) */
export interface RutinaPendiente {
  id: string
  socio_id: string
  coach_id: string | null
  semaforo: Semaforo
  dias: { ejercicios: Ejercicio[] }[]
  estado: string
  algoritmo: string | null
  costo_min: number | null
  creada: string
  socioNombre: string
  motivos: string[]
  maquinasExcluidas: string[]
}

export interface Factor {
  dato: 'dias_ultima_visita' | 'visitas_semana' | 'antiguedad_meses'
  efecto: 'sube' | 'baja' | 'neutro'
  texto: string
}

export interface SocioRiesgo {
  id: string
  nombre: string
  probabilidad: number
  nivel: Nivel
  segmento: string | null
  factores: Factor[]
  alertaId: string | null
}

/** GET /v1/coach/socios */
export interface SociosRiesgoOut {
  analizado: boolean
  totalSocios: number
  socios: SocioRiesgo[]
}

/** GET /v1/coach/perfiles */
export interface PerfilesOut {
  analizado: boolean
  perfiles: { segmento: string; socios: number; riesgoMedioPct: number; riesgoAlto: number }[]
}

export type Falla = 'báscula' | 'electrodos' | 'duración'

/** GET /v1/coach/mantenimiento */
export type MantenimientoOut = {
  estacionId: string
  estacion: string
  lecturas: { fecha: string; falla: Falla; deltaPesoKg: number | null; deltaGrasaPct: number | null }[]
}[]

/** GET /v1/coach/modelo */
export interface ModeloOut {
  version: string
  fechaEntrenamiento: string
  scikitLearn: string
  metricas: {
    abandono: { rocAuc: number; f1: number; precision: number; recall: number }
    afluencia: { r2: number; maeSocios: number }
    kmeans: { silueta: number }
    meanshift: { f1: number }
  }
}

/** POST /v1/prediccion/abandono/lote (solo admin) */
export interface LoteOut {
  procesados: number
  alertasNuevas: number
  modelo: string
}

export type Lesion = 'rodilla' | 'hombro' | 'espalda_baja' | 'cadera'

/** Ficha de salud tal como la guarda el backend (salud.py · ficha_publica) */
export interface FichaSalud {
  parq: boolean[]
  lesiones: Lesion[]
  semaforo: Semaforo
  motivos: string[]
  requiereAptoMedico: boolean
  maquinasExcluidas: string[]
  actualizada: string | null
}

interface EstadoFicha {
  parq: boolean[]
  lesiones: Lesion[]
  semaforo: Semaforo
}

/** Fila de fichas_salud_historial */
export interface CambioFicha {
  id: string
  socio_id: string
  motivo: string
  hecho_por: string | null
  fecha: string
  cambio: { antes: EstadoFicha; despues: EstadoFicha }
}

/** GET /v1/coach/fichas?dni=…  y  PUT /v1/coach/fichas/{socioId} */
export interface FichaSocioOut {
  socio: { id: string; nombre: string; dni: string | null; semaforo: Semaforo }
  ficha: FichaSalud | null
  historial: CambioFicha[]
}

// ---------------------------------------------------------------- errores y núcleo
export class ErrorApi extends Error {
  constructor(
    mensaje: string,
    public estado: number,
    public sinConexion = false,
  ) {
    super(mensaje)
    this.name = 'ErrorApi'
  }
}

export const MSG_SIN_CONEXION = 'Sin conexión con el servidor. Intenta de nuevo.'
const BASE = (import.meta.env.VITE_API_URL ?? '').replace(/\/$/, '')

let token: string | null = null
let alExpirar: (() => void) | null = null
export const fijarToken = (t: string | null) => {
  token = t
}
/** El panel registra aquí qué hacer si el servidor responde 401 con sesión abierta (token vencido). */
export const alSesionExpirada = (fn: (() => void) | null) => {
  alExpirar = fn
}

function mensaje(estado: number, detalle: unknown): string {
  if (typeof detalle === 'string' && estado !== 422) return detalle
  if (estado === 401) return 'Tu sesión venció. Entra de nuevo.'
  if (estado === 403) return 'No tienes permiso para esto.'
  if (estado === 422) return 'Revisa los datos e inténtalo de nuevo.'
  if (estado === 429) return 'Demasiados intentos. Espera un momento.'
  return 'Algo salió mal, intenta de nuevo.'
}

async function pedir<T>(metodo: 'GET' | 'POST' | 'PUT', ruta: string, cuerpo?: unknown): Promise<T> {
  let r: Response
  try {
    r = await fetch(`${BASE}/v1${ruta}`, {
      method: metodo,
      headers: {
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(cuerpo !== undefined ? { 'Content-Type': 'application/json' } : {}),
      },
      body: cuerpo !== undefined ? JSON.stringify(cuerpo) : undefined,
    })
  } catch {
    throw new ErrorApi(MSG_SIN_CONEXION, 0, true)
  }
  let datos: unknown = null
  try {
    datos = await r.json()
  } catch {
    /* sin cuerpo */
  }
  if (!r.ok) {
    if (r.status === 401 && token && ruta !== '/auth/login') alExpirar?.()
    throw new ErrorApi(mensaje(r.status, (datos as { detail?: unknown } | null)?.detail), r.status)
  }
  return datos as T
}

// ---------------------------------------------------------------- llamadas
export const login = (email: string, password: string) => pedir<LoginOut>('POST', '/auth/login', { email, password })
export const rutinasPendientes = () => pedir<RutinaPendiente[]>('GET', '/coach/rutinas-pendientes')
export const aprobarRutina = (id: string) => pedir<unknown>('POST', `/coach/rutinas/${encodeURIComponent(id)}/aprobar`)
export const rechazarRutina = (id: string, motivo: string) =>
  pedir<unknown>('POST', `/coach/rutinas/${encodeURIComponent(id)}/rechazar`, { motivo })
export const sociosRiesgo = () => pedir<SociosRiesgoOut>('GET', '/coach/socios?limite=100')
export const registrarContacto = (alertaId: string) => pedir<unknown>('POST', `/coach/alertas/${encodeURIComponent(alertaId)}/atender`)
export const perfiles = () => pedir<PerfilesOut>('GET', '/coach/perfiles')
export const mantenimiento = () => pedir<MantenimientoOut>('GET', '/coach/mantenimiento')
export const modelo = () => pedir<ModeloOut>('GET', '/coach/modelo')
export const ejecutarAnalisisNocturno = () => pedir<LoteOut>('POST', '/prediccion/abandono/lote')
export const buscarFicha = (dni: string) => pedir<FichaSocioOut>('GET', `/coach/fichas?dni=${encodeURIComponent(dni)}`)
export const corregirFicha = (socioId: string, cambio: { parq: boolean[]; lesiones: Lesion[]; motivo: string }) =>
  pedir<FichaSocioOut>('PUT', `/coach/fichas/${encodeURIComponent(socioId)}`, cambio)
