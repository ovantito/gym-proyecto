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
  /** rojo: bloqueado hasta que un coach/admin lo libere */
  bloqueado: boolean
  bloqueadoDesde: string | null
  actualizada: string | null
}

interface EstadoFicha {
  parq: boolean[]
  lesiones: Lesion[]
  semaforo: Semaforo
  bloqueado?: boolean
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

/** Última medición válida del socio. tallaCm e imc son null en lecturas anteriores a la talla. */
export interface MedicionSocio {
  pesoKg: number
  tallaCm: number | null
  imc: number | null
  grasaPct: number
  sistolica: number
  diastolica: number
  pulso: number
  fecha: string
}

/** GET /v1/coach/fichas?dni=…  y  PUT /v1/coach/fichas/{socioId} */
export interface FichaSocioOut {
  socio: { id: string; nombre: string; dni: string | null; semaforo: Semaforo }
  ficha: FichaSalud | null
  medicion?: MedicionSocio | null
  historial: CambioFicha[]
}

/** GET /v1/admin/coaches */
export interface CoachAdmin {
  id: string
  nombre: string
  email: string
  activo: boolean
  socios: number
  alertasAbiertas: number
  rutinasPendientes: number
}

interface CoachRef {
  id: string | null
  nombre: string | null
}

/** GET /v1/admin/socios?dni=…  y  POST /v1/admin/socios/{id}/reasignar */
export interface SocioAdmin {
  id: string
  nombre: string
  dni: string | null
  plan: string | null
  semaforo: Semaforo | null
  coach: CoachRef
  historial: { id: string; fecha: string; motivo: string; loteId: string | null; coachAntes: CoachRef; coachDespues: CoachRef }[]
}

/** POST /v1/admin/coaches/{id}/traspasar */
export interface TraspasoOut {
  sociosMovidos: number
  alertasMovidas: number
  rutinasMovidas: number
  loteId: string
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

async function pedir<T>(metodo: 'GET' | 'POST' | 'PUT' | 'PATCH', ruta: string, cuerpo?: unknown): Promise<T> {
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

/** `?coach_id=` (o `&coach_id=`) para que el admin vea el panel de un coach. Vacío si no hay coach elegido. */
const filtroCoach = (coachId?: string | null, sep: '?' | '&' = '?') => (coachId ? `${sep}coach_id=${encodeURIComponent(coachId)}` : '')

// ---------------------------------------------------------------- llamadas
export const login = (email: string, password: string) => pedir<LoginOut>('POST', '/auth/login', { email, password })
export const rutinasPendientes = (coachId?: string | null) =>
  pedir<RutinaPendiente[]>('GET', `/coach/rutinas-pendientes${filtroCoach(coachId)}`)
export const aprobarRutina = (id: string) => pedir<unknown>('POST', `/coach/rutinas/${encodeURIComponent(id)}/aprobar`)
export const rechazarRutina = (id: string, motivo: string) =>
  pedir<unknown>('POST', `/coach/rutinas/${encodeURIComponent(id)}/rechazar`, { motivo })
export const sociosRiesgo = (coachId?: string | null) =>
  pedir<SociosRiesgoOut>('GET', `/coach/socios?limite=100${filtroCoach(coachId, '&')}`)
export const registrarContacto = (alertaId: string) => pedir<unknown>('POST', `/coach/alertas/${encodeURIComponent(alertaId)}/atender`)
export const perfiles = (coachId?: string | null) => pedir<PerfilesOut>('GET', `/coach/perfiles${filtroCoach(coachId)}`)
export const mantenimiento = (coachId?: string | null) =>
  pedir<MantenimientoOut>('GET', `/coach/mantenimiento${filtroCoach(coachId)}`)
export const modelo = () => pedir<ModeloOut>('GET', '/coach/modelo')
export const ejecutarAnalisisNocturno = () => pedir<LoteOut>('POST', '/prediccion/abandono/lote')
export const buscarFicha = (dni: string, coachId?: string | null) =>
  pedir<FichaSocioOut>('GET', `/coach/fichas?dni=${encodeURIComponent(dni)}${filtroCoach(coachId, '&')}`)
export const corregirFicha = (socioId: string, cambio: { parq: boolean[]; lesiones: Lesion[]; motivo: string }) =>
  pedir<FichaSocioOut>('PUT', `/coach/fichas/${encodeURIComponent(socioId)}`, cambio)
export const liberarSocio = (socioId: string, motivo: string) =>
  pedir<FichaSocioOut>('POST', `/coach/fichas/${encodeURIComponent(socioId)}/liberar`, { motivo })

// ---- solo admin
export const listarCoaches = () => pedir<CoachAdmin[]>('GET', '/admin/coaches')
export const buscarSocioAdmin = (dni: string) => pedir<SocioAdmin>('GET', `/admin/socios?dni=${encodeURIComponent(dni)}`)
export const reasignarSocio = (socioId: string, coachId: string, motivo: string) =>
  pedir<SocioAdmin>('POST', `/admin/socios/${encodeURIComponent(socioId)}/reasignar`, { coach_id: coachId, motivo })
export const traspasarCoach = (origenId: string, destinoId: string, motivo: string, desactivarOrigen: boolean) =>
  pedir<TraspasoOut>('POST', `/admin/coaches/${encodeURIComponent(origenId)}/traspasar`, {
    coach_destino_id: destinoId,
    motivo,
    desactivar_origen: desactivarOrigen,
  })
export const cambiarEstadoCoach = (coachId: string, activo: boolean) =>
  pedir<unknown>('PATCH', `/admin/coaches/${encodeURIComponent(coachId)}`, { activo })
