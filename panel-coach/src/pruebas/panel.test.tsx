import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from '../App'
import { fijarToken } from '../api/cliente'

const ok = (cuerpo: unknown, status = 200) => new Response(JSON.stringify(cuerpo), { status })

const RUTINA = {
  id: 'r-1', socio_id: 's-1', coach_id: 'c-1', semaforo: 'amarillo', estado: 'pendiente_aprobacion', algoritmo: 'a_estrella', costo_min: 8,
  creada: '2026-11-26T15:00:00+00:00', socioNombre: 'Socio 0011', motivos: ['Lesión declarada: rodilla'], maquinasExcluidas: ['M-02', 'M-03'],
  dias: [{ ejercicios: [{ id: 'E-M-17', nombre: 'Plancha en banco', maquina: 'M-17', series: 2, repeticiones: 10, descansoSeg: 90 }] }],
}
const PARQ_NO = [false, false, false, false, false, false, false]
const SOCIO = (n: string, p: number) => ({
  id: n, nombre: n, probabilidad: p, nivel: p > 0.6 ? 'alto' : 'bajo', segmento: 'nocturno_nuevo', alertaId: p > 0.6 ? `a-${n}` : null,
  factores: [
    { dato: 'dias_ultima_visita', efecto: 'sube', texto: '12 días sin venir (más que la mayoría)' },
    { dato: 'visitas_semana', efecto: 'sube', texto: '1.2 visitas por semana (menos que la mayoría)' },
    { dato: 'antiguedad_meses', efecto: 'baja', texto: '30 meses como socio (socio veterano)' },
  ],
})

interface Opciones { rol?: 'coach' | 'admin'; clave?: string }
function instalar(o: Opciones = {}) {
  const rol = o.rol ?? 'coach'
  const llamadas: { metodo: string; ruta: string; body?: unknown }[] = []
  let pendientes = [RUTINA]
  let fichaActual: Record<string, unknown> = { parq: PARQ_NO, lesiones: ['rodilla'], semaforo: 'amarillo', motivos: ['Lesión declarada: rodilla'],
    requiereAptoMedico: false, maquinasExcluidas: ['M-02', 'M-03'], actualizada: '2026-11-25T10:00:00+00:00' }
  let historial: unknown[] = []
  const vistaFicha = () => ({ socio: { id: 's-9', nombre: 'Socio 0009', dni: '12345678', semaforo: fichaActual.semaforo }, ficha: fichaActual, historial })
  vi.stubGlobal('fetch', vi.fn(async (url: string, init: RequestInit = {}) => {
    const ruta = url.replace(/^.*\/v1/, '')
    const metodo = init.method ?? 'GET'
    llamadas.push({ metodo, ruta, body: typeof init.body === 'string' ? JSON.parse(init.body) : undefined })
    if (ruta === '/auth/login') {
      const b = JSON.parse(init.body as string)
      return b.password === 'bien' ? ok({ token: 'tok-' + rol, rol, nombre: 'Coach Demo', expiraEnSeg: 3600 }) : ok({ detail: 'Correo o contraseña incorrectos' }, 401)
    }
    if (init.headers && (init.headers as Record<string, string>).Authorization !== 'Bearer tok-' + rol) return ok({ detail: 'x' }, 401)
    if (ruta === '/coach/rutinas-pendientes') return ok(pendientes)
    if (/\/coach\/rutinas\/r-1\/(aprobar|rechazar)$/.test(ruta)) { pendientes = []; return ok({ ok: true }) }
    if (ruta.startsWith('/coach/socios')) return ok({ analizado: true, totalSocios: 600, socios: [SOCIO('Socio 0001', 0.93), SOCIO('Socio 0002', 0.2)] })
    if (/\/coach\/alertas\/.+\/atender$/.test(ruta)) return ok({ resuelta: true })
    if (ruta.startsWith('/coach/fichas?dni=')) {
      return ruta.endsWith('12345678') ? ok(vistaFicha()) : ok({ detail: 'No encontramos ese DNI entre tus socios' }, 404)
    }
    if (ruta === '/coach/fichas/s-9' && metodo === 'PUT') {
      const b = JSON.parse(init.body as string)
      fichaActual = { ...fichaActual, parq: b.parq, lesiones: b.lesiones, semaforo: b.lesiones.length ? 'amarillo' : 'verde' }
      historial = [{ id: 'h-1', socio_id: 's-9', motivo: b.motivo, hecho_por: 'c-1', fecha: '2026-11-26T16:00:00+00:00',
        cambio: { antes: { parq: PARQ_NO, lesiones: ['rodilla'], semaforo: 'amarillo' }, despues: { parq: b.parq, lesiones: b.lesiones, semaforo: fichaActual.semaforo } } }]
      return ok(vistaFicha())
    }
    if (ruta === '/prediccion/abandono/lote') return ok({ procesados: 3000, alertasNuevas: 14, modelo: '1.0.0' })
    return ok({ detail: 'no encontrado' }, 404)
  }))
  return llamadas
}

async function entrar(u: ReturnType<typeof userEvent.setup>, clave = 'bien') {
  await u.type(screen.getByLabelText('Correo'), 'coach@tnt.demo')
  await u.type(screen.getByLabelText('Contraseña'), clave)
  await u.click(screen.getByRole('button', { name: 'Entrar' }))
}

beforeEach(() => {
  sessionStorage.clear()
  fijarToken(null)
})
afterEach(() => vi.unstubAllGlobals())

describe('login', () => {
  it('login correcto entra al panel y guarda el rol', async () => {
    instalar()
    const u = userEvent.setup()
    render(<App />)
    await entrar(u)
    expect(await screen.findByText('Rutinas por aprobar', { selector: 'h2' })).toBeInTheDocument()
    expect(screen.getByText('Coach (solo tus socios)')).toBeInTheDocument()
  })

  it('login incorrecto muestra el error y se queda en el login', async () => {
    instalar()
    const u = userEvent.setup()
    render(<App />)
    await entrar(u, 'mala')
    expect(await screen.findByRole('alert')).toHaveTextContent('Correo o contraseña incorrectos')
    expect(screen.getByRole('button', { name: 'Entrar' })).toBeInTheDocument()
  })

  it('si el token vence (401) vuelve al login con un aviso', async () => {
    instalar()
    const u = userEvent.setup()
    render(<App />)
    await entrar(u)
    await screen.findByText('Rutinas por aprobar', { selector: 'h2' })
    fijarToken('token-vencido') // el backend lo rechazará
    await u.click(screen.getByRole('button', { name: 'Riesgo de abandono' }))
    expect(await screen.findByText('Tu sesión venció. Entra de nuevo.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Entrar' })).toBeInTheDocument()
  })
})

describe('roles', () => {
  it('el botón de análisis nocturno NO aparece para un coach', async () => {
    instalar({ rol: 'coach' })
    const u = userEvent.setup()
    render(<App />)
    await entrar(u)
    await screen.findByText('Rutinas por aprobar', { selector: 'h2' })
    expect(screen.queryByRole('button', { name: /análisis nocturno/i })).not.toBeInTheDocument()
  })

  it('el admin ve el botón y al pulsarlo ejecuta el lote', async () => {
    const l = instalar({ rol: 'admin' })
    const u = userEvent.setup()
    render(<App />)
    await entrar(u)
    await u.click(await screen.findByRole('button', { name: 'Ejecutar análisis nocturno ahora' }))
    expect(await screen.findByText(/3000 socios procesados, 14 alertas nuevas/)).toBeInTheDocument()
    expect(l.some((x) => x.metodo === 'POST' && x.ruta === '/prediccion/abandono/lote')).toBe(true)
  })

  it('el coach solo ve los socios que el backend le devuelve (los suyos)', async () => {
    instalar()
    const u = userEvent.setup()
    render(<App />)
    await entrar(u)
    await u.click(await screen.findByRole('button', { name: 'Riesgo de abandono' }))
    expect(await screen.findByText('Socio 0001')).toBeInTheDocument()
    expect(screen.getByText('Socio 0002')).toBeInTheDocument()
    expect(screen.queryByText('Socio 2999')).not.toBeInTheDocument()
    expect(screen.getByText(/Mostrando 2 de 600 socios/)).toBeInTheDocument()
  })
})

describe('secciones', () => {
  it('aprobar una rutina llama al backend y la quita de la lista', async () => {
    const l = instalar()
    const u = userEvent.setup()
    render(<App />)
    await entrar(u)
    const tarjeta = await screen.findByRole('article', { name: 'Rutina de Socio 0011' })
    expect(within(tarjeta).getByText('Lesión declarada: rodilla')).toBeInTheDocument()
    expect(within(tarjeta).getByText(/Máquinas excluidas: M-02, M-03/)).toBeInTheDocument()
    await u.click(within(tarjeta).getByRole('button', { name: 'Aprobar' }))
    await waitFor(() => expect(l.some((x) => x.ruta === '/coach/rutinas/r-1/aprobar' && x.metodo === 'POST')).toBe(true))
    expect(await screen.findByText(/No hay rutinas por aprobar/)).toBeInTheDocument()
  })

  it('rechazar exige un motivo y lo envía', async () => {
    const l = instalar()
    const u = userEvent.setup()
    render(<App />)
    await entrar(u)
    const tarjeta = await screen.findByRole('article', { name: 'Rutina de Socio 0011' })
    await u.click(within(tarjeta).getByRole('button', { name: 'Rechazar' }))
    const confirmar = within(tarjeta).getByRole('button', { name: 'Confirmar rechazo' })
    expect(confirmar).toBeDisabled()
    await u.type(within(tarjeta).getByLabelText('Motivo del rechazo'), 'Carga muy alta')
    await u.click(confirmar)
    await waitFor(() => expect(l.find((x) => x.ruta === '/coach/rutinas/r-1/rechazar')?.body).toEqual({ motivo: 'Carga muy alta' }))
  })

  it('"Registrar contacto" marca la alerta como atendida', async () => {
    const l = instalar()
    const u = userEvent.setup()
    render(<App />)
    await entrar(u)
    await u.click(await screen.findByRole('button', { name: 'Riesgo de abandono' }))
    await screen.findByText('Socio 0001')
    expect(screen.getAllByText('▲ 12 días sin venir (más que la mayoría)')).toHaveLength(2)
    await u.click(screen.getByRole('button', { name: 'Registrar contacto' }))
    await waitFor(() => expect(l.some((x) => x.metodo === 'POST' && x.ruta === '/coach/alertas/a-Socio%200001/atender')).toBe(true))
  })
})

describe('fichas de salud', () => {
  it('busca por DNI, quita una lesión con motivo y queda en el historial', async () => {
    const l = instalar()
    const u = userEvent.setup()
    render(<App />)
    await entrar(u)
    await u.click(await screen.findByRole('button', { name: 'Fichas de salud' }))
    const buscar = screen.getByRole('button', { name: 'Buscar' })
    expect(buscar).toBeDisabled()
    await u.type(screen.getByLabelText('DNI del socio'), '12345678')
    await u.click(buscar)
    expect(await screen.findByText('Socio 0009')).toBeInTheDocument()
    expect(screen.getByText('Sin cambios hechos por el coach.')).toBeInTheDocument()

    const guardar = screen.getByRole('button', { name: 'Guardar cambio' })
    expect(guardar).toBeDisabled()
    await u.click(screen.getByLabelText('Rodilla'))   // quitar la lesión
    expect(guardar).toBeDisabled()                    // sin motivo no se puede guardar
    await u.click(screen.getByRole('button', { name: 'Presentó apto médico' }))
    expect(guardar).toBeEnabled()
    await u.click(guardar)

    expect(await screen.findByText('Motivo: Presentó apto médico')).toBeInTheDocument()
    expect(screen.getByText('Quitó la lesión de rodilla')).toBeInTheDocument()
    expect(l.find((x) => x.metodo === 'PUT' && x.ruta === '/coach/fichas/s-9')?.body).toEqual({
      parq: PARQ_NO, lesiones: [], motivo: 'Presentó apto médico',
    })
  })

  it('un DNI que no es de sus socios muestra el aviso del backend', async () => {
    instalar()
    const u = userEvent.setup()
    render(<App />)
    await entrar(u)
    await u.click(await screen.findByRole('button', { name: 'Fichas de salud' }))
    await u.type(screen.getByLabelText('DNI del socio'), '99999999')
    await u.click(screen.getByRole('button', { name: 'Buscar' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('No encontramos ese DNI entre tus socios')
  })
})
