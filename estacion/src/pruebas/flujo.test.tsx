import { act, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from '../App'
import type { FichaGuardadaOut, FichaOut, RutinaOut } from '../api/cliente'

type Manejador = (url: string, init: RequestInit) => unknown
const ok = (cuerpo: unknown, status = 200) => new Response(JSON.stringify(cuerpo), { status })

const RUTINA: RutinaOut = {
  rutinaId: 'r-1',
  semaforo: 'verde',
  estado: 'activa',
  alertas: [],
  detalle: { algoritmo: 'a_estrella', tiempoPerdidoEstimadoMin: 27.5, sociosEnSala: 59 },
  dias: [
    {
      ejercicios: [
        { id: 'E-M-17', nombre: 'Plancha en banco', maquina: 'M-17', series: 3, repeticiones: 12, descansoSeg: 60 },
        { id: 'E-M-01', nombre: 'Prensa 45°', maquina: 'M-01', series: 3, repeticiones: 12, descansoSeg: 60 },
      ],
    },
  ],
}

/** Backend simulado. `ficha`, `medicion` y `video` se pueden cambiar por prueba. */
function instalarBackend(o: { ficha?: FichaOut; previa?: FichaGuardadaOut; atipica?: boolean; video?: 'ok' | 'error'; amarilla?: boolean; rechazarPut?: boolean } = {}) {
  const llamadas: string[] = []
  const bodies: Record<string, unknown>[] = []
  const remoto = { estado: 'pendiente_aprobacion', motivoRechazo: null as string | null } // lo que "decide" el coach
  const ficha = o.ficha ?? { semaforo: 'verde', motivos: [], requiereAptoMedico: false, maquinasExcluidas: [] }
  const m: Manejador = (url, init) => {
    const metodo = init.method ?? 'GET'
    llamadas.push(`${metodo} ${url.replace(/^.*\/v1/, '')}`)
    if (typeof init.body === 'string') bodies.push(JSON.parse(init.body))
    if (/\/sesiones$/.test(url)) return ok({ sesionId: 's-1', socio: { id: 'socio-1', nombre: 'Carla Pérez', semaforo: 'verde' } }, 201)
    if (/\/mediciones$/.test(url))
      return ok(
        o.atipica
          ? { medicionId: 'm', atipica: true, usada: false, mensaje: 'Lectura atípica' }
          : { medicionId: 'm', atipica: false, usada: true },
        201,
      )
    if (/\/ficha-salud$/.test(url) && metodo === 'GET') return ok(o.previa ?? { existe: false })
    if (/\/ficha-salud$/.test(url) && o.rechazarPut)
      return ok({ detail: 'No se puede quitar una condición ya registrada. Habla con tu coach: lesión: rodilla' }, 409)
    if (/\/ficha-salud$/.test(url)) return ok(ficha)
    if (/\/rutinas\/generar$/.test(url))
      return ok(o.amarilla ? { ...RUTINA, semaforo: 'amarillo', estado: 'pendiente_aprobacion' } : RUTINA, 201)
    if (/\/rutinas\/r-1$/.test(url)) return ok({ rutinaId: 'r-1', ...remoto })
    if (/\/prediccion\/espera/.test(url)) return ok({ hora: 19, dia: 0, sociosEnSala: 59, esperaMin: { 'M-17': 0.2, 'M-01': 6.8 } })
    if (/\/video$/.test(url))
      return o.video === 'error' ? ok({ detail: 'Videos no configurados' }, 503) : ok({ url: 'https://r2.example/video.mp4?firma=abc', expiraEnSeg: 900 })
    return ok({ detail: 'no encontrado' }, 404)
  }
  vi.stubGlobal('fetch', vi.fn(async (url: string, init: RequestInit = {}) => m(url, init)))
  return Object.assign(llamadas, { bodies, remoto })
}

async function escribirDni(u: ReturnType<typeof userEvent.setup>) {
  for (const d of '10000010') await u.click(screen.getByRole('button', { name: d }))
  await u.click(screen.getByRole('button', { name: 'Simular lectura' }))
}

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true })
})
afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

const nuevo = () => userEvent.setup({ advanceTimers: vi.advanceTimersByTime })

async function hastaSemaforo(u: ReturnType<typeof nuevo>) {
  await escribirDni(u)
  await screen.findByText(/Hola, Carla Pérez/)
  await u.click(screen.getByRole('button', { name: 'Simular báscula' }))
  await screen.findByText(/Medición registrada/)
  await u.click(screen.getByRole('button', { name: 'Continuar' }))
  await screen.findByText('Antes de entrenar')
  expect(screen.queryByText(/La IA solo recibe/)).not.toBeInTheDocument() // sin avisos técnicos
  await u.click(screen.getByRole('button', { name: 'Ver mi semáforo' }))
}

describe('flujo de la estación', () => {
  it('flujo verde completo: DNI → medición → ficha → semáforo → rutina → ticket → inicio', async () => {
    const llamadas = instalarBackend()
    const u = nuevo()
    render(<App />)
    expect(screen.getByText('Acerca tu DNI o QR')).toBeInTheDocument()

    await hastaSemaforo(u)
    expect(await screen.findByText(/Verde · ¡A entrenar!/)).toBeInTheDocument()
    await u.click(screen.getByRole('button', { name: 'Ver mi rutina' }))

    expect(await screen.findByText('M-17')).toBeInTheDocument()
    // rutina limpia: sin términos técnicos ni el recuadro del motor
    expect(screen.queryByText(/Orden optimizado|motor|A\*|socios en sala/)).not.toBeInTheDocument()
    expect(screen.getByText('espera 7 min')).toBeInTheDocument() // 6.8 redondeado
    await u.click(screen.getByRole('button', { name: /Prensa 45°, ver video/ }))
    await waitFor(() => expect(screen.getByLabelText('Video de Prensa 45°')).toBeInTheDocument())

    await u.click(screen.getByRole('button', { name: 'Imprimir mi ticket' }))
    expect(await screen.findByText('¡Recoge tu ticket!')).toBeInTheDocument()
    await waitFor(() => expect(screen.getAllByRole('img', { name: 'Código QR' }).length).toBeGreaterThan(0))
    await u.click(screen.getByRole('button', { name: 'Terminar' }))
    expect(await screen.findByText('Acerca tu DNI o QR')).toBeInTheDocument()

    expect(llamadas.filter((l) => l.startsWith('POST') || l.startsWith('PUT')).map((l) => l.split('/').slice(-1)[0])).toEqual([
      'sesiones', 'mediciones', 'ficha-salud', 'generar',
    ])
  })

  it('semáforo rojo termina en la pantalla 4: sin rutina y con apto médico', async () => {
    const llamadas = instalarBackend({
      ficha: { semaforo: 'rojo', motivos: ['Presión sistólica 165 ≥ 160'], requiereAptoMedico: true, maquinasExcluidas: [] },
    })
    const u = nuevo()
    render(<App />)
    await hastaSemaforo(u)

    expect(await screen.findByText(/Necesitas apto médico para entrenar hoy/, { selector: 'h1' })).toBeInTheDocument()
    expect(screen.getByText('• Tu presión está alta hoy.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Ver mi rutina' })).not.toBeInTheDocument()
    expect(llamadas.some((l) => l.includes('generar'))).toBe(false)

    await u.click(screen.getByRole('button', { name: 'Terminar' }))
    expect(await screen.findByText('Acerca tu DNI o QR')).toBeInTheDocument()
  })

  it('semáforo amarillo avisa que el coach revisará la rutina', async () => {
    instalarBackend({
      ficha: { semaforo: 'amarillo', motivos: ['Lesión declarada: rodilla'], requiereAptoMedico: false, maquinasExcluidas: ['M-02', 'M-03'] },
    })
    const u = nuevo()
    render(<App />)
    await hastaSemaforo(u)
    expect(await screen.findByText('Tu coach revisará tu rutina.')).toBeInTheDocument()
    expect(screen.getByText('• Por tu lesión de rodilla, cuidaremos tu rutina.')).toBeInTheDocument()
  })

  it('una medición atípica muestra el aviso y no deja continuar', async () => {
    instalarBackend({ atipica: true })
    const u = nuevo()
    render(<App />)
    await escribirDni(u)
    await screen.findByText(/Hola, Carla Pérez/)
    await u.click(screen.getByRole('button', { name: 'Simular lectura imposible' }))
    expect(await screen.findByText('Medición no válida, avisamos al personal. Vuelve a medirte.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Continuar' })).toBeDisabled()
  })

  it('sin conexión muestra un mensaje, nunca pantalla en blanco', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    const u = nuevo()
    render(<App />)
    await escribirDni(u)
    expect(await screen.findByText('Sin conexión, intenta de nuevo')).toBeInTheDocument()
    expect(screen.getByText('Acerca tu DNI o QR')).toBeInTheDocument()
  })

  it('si el video falla muestra "Video no disponible" y la pantalla sigue funcionando', async () => {
    instalarBackend({ video: 'error' })
    const u = nuevo()
    render(<App />)
    await hastaSemaforo(u)
    await u.click(await screen.findByRole('button', { name: 'Ver mi rutina' }))
    await u.click(await screen.findByRole('button', { name: /Plancha en banco, ver video/ }))
    expect(await screen.findByText('Video no disponible')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Imprimir mi ticket' })).toBeInTheDocument()
  })

  it('tras 60 s sin tocar vuelve al inicio y borra los datos del socio', async () => {
    instalarBackend()
    const u = nuevo()
    render(<App />)
    await escribirDni(u)
    await screen.findByText(/Hola, Carla Pérez/)
    act(() => {
      vi.advanceTimersByTime(60_000)
    })
    expect(await screen.findByText('Acerca tu DNI o QR')).toBeInTheDocument()
    expect(screen.queryByText(/Carla/)).not.toBeInTheDocument()
  })
})

describe('amarillo en vivo y presión alta', () => {
  const amarilla: FichaOut = { semaforo: 'amarillo', motivos: ['Lesión declarada: rodilla'], requiereAptoMedico: false, maquinasExcluidas: ['M-02', 'M-03'] }

  async function hastaRutinaAmarilla(u: ReturnType<typeof nuevo>) {
    await hastaSemaforo(u)
    await u.click(await screen.findByRole('button', { name: 'Ver mi rutina' }))
    await screen.findByText('Plancha en banco')
  }
  const consultas = (l: string[]) => l.filter((x) => x === 'GET /rutinas/r-1').length

  it('consulta cada 5 s y, cuando el coach aprueba, cambia sola y habilita el ticket', async () => {
    const l = instalarBackend({ ficha: amarilla, amarilla: true })
    const u = nuevo()
    render(<App />)
    await hastaRutinaAmarilla(u)
    expect(screen.getByText('Esperando la aprobación de tu coach…')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Imprimir mi ticket' })).toBeDisabled()

    await act(async () => { await vi.advanceTimersByTimeAsync(5000) })
    expect(consultas(l)).toBe(1)
    expect(screen.getByRole('button', { name: 'Imprimir mi ticket' })).toBeDisabled() // el coach aún no decide

    l.remoto.estado = 'activa'
    await act(async () => { await vi.advanceTimersByTimeAsync(5000) })
    expect(await screen.findByText('✓ Tu coach aprobó tu rutina')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Imprimir mi ticket' })).toBeEnabled()

    const n = consultas(l)
    await act(async () => { await vi.advanceTimersByTimeAsync(20000) })
    expect(consultas(l)).toBe(n) // ya no pregunta más
  })

  it('si el coach rechaza muestra "Acércate a tu coach" y no deja imprimir', async () => {
    const l = instalarBackend({ ficha: amarilla, amarilla: true })
    const u = nuevo()
    render(<App />)
    await hastaRutinaAmarilla(u)
    l.remoto.estado = 'rechazada'
    l.remoto.motivoRechazo = 'Carga muy alta'
    await act(async () => { await vi.advanceTimersByTimeAsync(5000) })
    expect(await screen.findByText(/Acércate a tu coach/)).toHaveTextContent('Carga muy alta')
    expect(screen.getByRole('button', { name: 'Imprimir mi ticket' })).toBeDisabled()
  })

  it('deja de consultar al salir por inactividad', async () => {
    const l = instalarBackend({ ficha: amarilla, amarilla: true })
    const u = nuevo()
    render(<App />)
    await hastaRutinaAmarilla(u)
    await act(async () => { await vi.advanceTimersByTimeAsync(5000) })
    expect(consultas(l)).toBe(1)
    await act(async () => { await vi.advanceTimersByTimeAsync(60_000) }) // inactividad: vuelve al inicio
    expect(await screen.findByText('Acércate a tu coach').catch(() => null)).toBeNull()
    expect(screen.getByText('Acerca tu DNI o QR')).toBeInTheDocument()
    const n = consultas(l)
    await act(async () => { await vi.advanceTimersByTimeAsync(30_000) })
    expect(consultas(l)).toBe(n)
  })

  it('"Simular presión alta" envía 165/102', async () => {
    const l = instalarBackend()
    const u = nuevo()
    render(<App />)
    await escribirDni(u)
    await screen.findByText(/Hola, Carla Pérez/)
    await u.click(screen.getByRole('button', { name: 'Simular presión alta' }))
    expect(await screen.findByText(/165 \/ 102/)).toBeInTheDocument()
    expect(l.bodies.find((b) => b.presion_sistolica === 165)).toMatchObject({ presion_diastolica: 102 })
  })
})

describe('ficha de salud persistente', () => {
  const PREVIA: FichaGuardadaOut = {
    existe: true,
    parq: [false, false, false, false, true, false, false],
    lesiones: ['rodilla'],
    semaforo: 'amarillo',
    motivos: ['Lesión declarada: rodilla'],
    requiereAptoMedico: false,
    maquinasExcluidas: ['M-02', 'M-03'],
  }
  const amarilla: FichaOut = { semaforo: 'amarillo', motivos: ['Lesión declarada: rodilla'], requiereAptoMedico: false, maquinasExcluidas: ['M-02', 'M-03'] }

  async function hastaSalud(u: ReturnType<typeof nuevo>) {
    await escribirDni(u)
    await screen.findByText(/Hola, Carla Pérez/)
    await u.click(screen.getByRole('button', { name: 'Simular báscula' }))
    await screen.findByText(/Medición registrada/)
    await u.click(screen.getByRole('button', { name: 'Continuar' }))
  }

  it('sin ficha previa muestra el formulario completo, sin la pregunta de «sigues igual»', async () => {
    instalarBackend()
    const u = nuevo()
    render(<App />)
    await hastaSalud(u)
    expect(await screen.findByText('Antes de entrenar')).toBeInTheDocument()
    expect(screen.queryByText('¿Sigues igual que la última vez?')).not.toBeInTheDocument()
  })

  it('con ficha previa la precarga y «Sí, sigo igual» la reutiliza tal cual', async () => {
    const l = instalarBackend({ previa: PREVIA, ficha: amarilla })
    const u = nuevo()
    render(<App />)
    await hastaSalud(u)
    expect(await screen.findByText('¿Sigues igual que la última vez?')).toBeInTheDocument()
    expect(screen.getByText('• Lesión de rodilla')).toBeInTheDocument()
    expect(screen.queryByText('Antes de entrenar')).not.toBeInTheDocument()

    await u.click(screen.getByRole('button', { name: 'Sí, sigo igual' }))
    expect(await screen.findByText(/Amarillo · Entrena con cuidado/)).toBeInTheDocument()
    const put = l.bodies.find((b) => 'parq' in b)
    expect(put).toEqual({ parq: PREVIA.parq, lesiones: ['rodilla'] })
  })

  it('«Actualizar» muestra lo anterior bloqueado: no se puede quitar, pero sí agregar', async () => {
    const l = instalarBackend({ previa: PREVIA, ficha: amarilla })
    const u = nuevo()
    render(<App />)
    await hastaSalud(u)
    await u.click(await screen.findByRole('button', { name: 'Actualizar' }))

    expect(await screen.findByText('Antes de entrenar')).toBeInTheDocument()
    const rodilla = screen.getByRole('button', { name: /Rodilla/ })
    expect(rodilla).toBeDisabled()
    expect(rodilla).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getAllByText(/Para quitarla, habla con tu coach/).length).toBeGreaterThan(0)
    // la respuesta «Sí» ya registrada tampoco se puede cambiar a «No»
    const pregunta5 = screen.getByRole('group', { name: 'Pregunta 5' })
    expect(within(pregunta5).getByRole('button', { name: 'No' })).toBeDisabled()
    await u.click(rodilla)
    expect(rodilla).toHaveAttribute('aria-pressed', 'true')

    await u.click(screen.getByRole('button', { name: 'Hombro' })) // agregar sí se puede
    await u.click(screen.getByRole('button', { name: 'Ver mi semáforo' }))
    await screen.findByText(/Amarillo · Entrena con cuidado/)
    expect(l.bodies.find((b) => 'parq' in b)).toEqual({ parq: PREVIA.parq, lesiones: ['rodilla', 'hombro'] })
  })

  it('si el backend responde 409 por quitar una condición, la estación lo muestra y no avanza', async () => {
    instalarBackend({ previa: PREVIA, rechazarPut: true })
    const u = nuevo()
    render(<App />)
    await hastaSalud(u)
    await u.click(await screen.findByRole('button', { name: 'Sí, sigo igual' }))
    expect(await screen.findByText(/No se puede quitar una condición ya registrada/)).toBeInTheDocument()
    expect(screen.getByText('¿Sigues igual que la última vez?')).toBeInTheDocument()
  })

  it('rojo y bloqueado: pide acercarse al coach y no da rutina', async () => {
    const l = instalarBackend({
      ficha: { semaforo: 'rojo', motivos: ['Presión sistólica 120 ≥ 160', 'Bloqueado: requiere liberación del coach'], requiereAptoMedico: true,
        maquinasExcluidas: [], bloqueado: true },
    })
    const u = nuevo()
    render(<App />)
    await hastaSalud(u)
    await u.click(await screen.findByRole('button', { name: 'Ver mi semáforo' }))
    expect(await screen.findByText('Tu semáforo sigue en rojo. Acércate al coach para que te evalúe y te libere.')).toBeInTheDocument()
    expect(screen.getByText('• Un coach debe liberarte antes de entrenar.')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Ver mi rutina' })).not.toBeInTheDocument()
    expect(l.some((x) => x.includes('generar'))).toBe(false)
  })
})

