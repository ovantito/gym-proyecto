/**
 * Cliente del backend de la Estación TNT Fit. TODAS las llamadas a la API viven aquí.
 * Los tipos reflejan las respuestas reales de backend/app (módulos estacion, salud, rutinas, prediccion).
 */

// ---------------------------------------------------------------- tipos (respuestas)
export type Semaforo = 'verde' | 'amarillo' | 'rojo'

/** POST /v1/estaciones/{id}/sesiones  (estacion.py) */
export interface SesionOut {
  sesionId: string
  socio: { id: string; nombre: string; semaforo: Semaforo }
}

/** POST /v1/socios/{id}/mediciones  (salud.py). `mensaje` solo viene si la lectura es atípica. */
export interface MedicionOut {
  medicionId: string
  atipica: boolean
  usada: boolean
  mensaje?: string
}

/** PUT /v1/socios/{id}/ficha-salud  (salud.py) */
export interface FichaOut {
  semaforo: Semaforo
  motivos: string[]
  requiereAptoMedico: boolean
  maquinasExcluidas: string[]
}

/** GET /v1/socios/{id}/ficha-salud  (salud.py). `existe: false` si el socio aún no tiene ficha. */
export type FichaGuardadaOut =
  | { existe: false }
  | {
      existe: true
      parq: boolean[]
      lesiones: string[]
      semaforo: Semaforo
      motivos: string[]
      requiereAptoMedico: boolean
      maquinasExcluidas: string[]
    }

/** Ficha ya guardada del socio (lo que la estación precarga al identificarse). */
export type FichaPrevia = Extract<FichaGuardadaOut, { existe: true }>

export type EstadoRutina = 'activa' | 'pendiente_aprobacion' | 'rechazada' | 'requiere_apto_medico'

export interface Ejercicio {
  id: string // "E-M-17"
  nombre: string
  maquina: string // código "M-17"
  series: number
  repeticiones: number
  descansoSeg: number
}

/** POST /v1/socios/{id}/rutinas/generar  (rutinas.py). Si el semáforo es rojo: rutinaId null y dias []. */
export interface RutinaOut {
  rutinaId: string | null
  semaforo: Semaforo
  dias: { ejercicios: Ejercicio[] }[]
  estado: EstadoRutina
  alertas: string[]
  detalle?: { algoritmo: 'a_estrella' | 'hill_climbing'; tiempoPerdidoEstimadoMin: number; sociosEnSala: number } // la pantalla no lo muestra
}

/** GET /v1/prediccion/espera  (prediccion.py) */
export interface EsperaOut {
  hora: number
  dia: number
  sociosEnSala: number
  esperaMin: Record<string, number>
}

/** GET /v1/rutinas/{id}  (rutinas.py) — la estación lo consulta mientras espera al coach */
export interface EstadoRutinaOut {
  rutinaId: string
  estado: EstadoRutina | 'archivada'
  motivoRechazo: string | null
}

/** GET /v1/ejercicios/{id}/video  (rutinas.py) */
export interface VideoOut {
  url: string
  expiraEnSeg: number
}

// ---------------------------------------------------------------- tipos (peticiones)
export type SesionIn = { dni: string } | { qr: string }

export interface MedicionIn {
  peso_kg: number
  grasa_pct: number
  presion_sistolica: number
  presion_diastolica: number
  pulso_reposo: number
  talla_cm?: number
  duracion_seg?: number
  sesion_id?: string
}

export interface FichaIn {
  parq: boolean[] // exactamente 7 respuestas
  lesiones: string[] // rodilla | hombro | espalda_baja | cadera
  presion_sistolica?: number
  presion_diastolica?: number
  pulso_reposo?: number
}

export interface RutinaIn {
  hora?: number
  dia?: number
}

// ---------------------------------------------------------------- errores
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

export const MSG_SIN_CONEXION = 'Sin conexión, intenta de nuevo'

function mensajeDeEstado(estado: number, detalle: unknown): string {
  if (estado === 401) return 'Esta estación no está autorizada. Avisa al personal.'
  if (estado === 403) return 'No tienes permiso para esta operación.'
  if (estado === 404) return typeof detalle === 'string' ? detalle : 'No encontramos lo que buscabas.'
  if (estado === 409) return typeof detalle === 'string' ? detalle : 'Falta completar un paso anterior.'
  if (estado === 422) return 'Revisa los datos e inténtalo de nuevo.'
  if (estado === 429) return 'Demasiados intentos. Espera un momento.'
  if (estado === 503) return typeof detalle === 'string' ? detalle : 'Servicio no disponible por ahora.'
  return 'Algo salió mal, intenta de nuevo.'
}

// ---------------------------------------------------------------- núcleo
const env = import.meta.env
const BASE = (env.VITE_API_URL ?? '').replace(/\/$/, '')
const ESTACION_ID = env.VITE_STATION_ID ?? ''
const CLAVE = env.VITE_STATION_KEY ?? ''
const TIMEOUT_MS = 15000

async function pedir<T>(metodo: 'GET' | 'POST' | 'PUT', ruta: string, cuerpo?: unknown): Promise<T> {
  const ctrl = new AbortController()
  const t = setTimeout(() => ctrl.abort(), TIMEOUT_MS)
  let resp: Response
  try {
    resp = await fetch(`${BASE}/v1${ruta}`, {
      method: metodo,
      headers: { 'X-Station-Key': CLAVE, ...(cuerpo !== undefined ? { 'Content-Type': 'application/json' } : {}) },
      body: cuerpo !== undefined ? JSON.stringify(cuerpo) : undefined,
      signal: ctrl.signal,
    })
  } catch {
    throw new ErrorApi(MSG_SIN_CONEXION, 0, true) // red caída, CORS o timeout
  } finally {
    clearTimeout(t)
  }
  let datos: unknown = null
  try {
    datos = await resp.json()
  } catch {
    /* cuerpo vacío o no JSON */
  }
  if (!resp.ok) {
    const detalle = (datos as { detail?: unknown } | null)?.detail
    throw new ErrorApi(mensajeDeEstado(resp.status, detalle), resp.status)
  }
  return datos as T
}

// ---------------------------------------------------------------- llamadas
export const abrirSesion = (datos: SesionIn) =>
  pedir<SesionOut>('POST', `/estaciones/${encodeURIComponent(ESTACION_ID)}/sesiones`, datos)

export const registrarMedicion = (socioId: string, m: MedicionIn) =>
  pedir<MedicionOut>('POST', `/socios/${encodeURIComponent(socioId)}/mediciones`, m)

export const obtenerFicha = (socioId: string) => pedir<FichaGuardadaOut>('GET', `/socios/${encodeURIComponent(socioId)}/ficha-salud`)

export const guardarFicha = (socioId: string, f: FichaIn) =>
  pedir<FichaOut>('PUT', `/socios/${encodeURIComponent(socioId)}/ficha-salud`, f)

export const generarRutina = (socioId: string, datos: RutinaIn = {}) =>
  pedir<RutinaOut>('POST', `/socios/${encodeURIComponent(socioId)}/rutinas/generar`, datos)

export const obtenerEspera = (hora?: number, dia?: number) => {
  const q = new URLSearchParams()
  if (hora !== undefined) q.set('hora', String(hora))
  if (dia !== undefined) q.set('dia', String(dia))
  const s = q.toString()
  return pedir<EsperaOut>('GET', `/prediccion/espera${s ? `?${s}` : ''}`)
}

export const obtenerVideo = (ejercicioId: string) =>
  pedir<VideoOut>('GET', `/ejercicios/${encodeURIComponent(ejercicioId)}/video`)

export const obtenerEstadoRutina = (rutinaId: string) =>
  pedir<EstadoRutinaOut>('GET', `/rutinas/${encodeURIComponent(rutinaId)}`)

/** Ruta PÚBLICA y permanente (302 a una URL firmada nueva). Es lo que lleva el QR del ticket. */
export const urlVideoPermanente = (ejercicioId: string) => `${BASE || location.origin}/v1/ejercicios/${encodeURIComponent(ejercicioId)}/ver`
