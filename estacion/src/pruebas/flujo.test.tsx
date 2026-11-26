import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from '../App'
import type { FichaOut, RutinaOut } from '../api/cliente'

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
function instalarBackend(o: { ficha?: FichaOut; atipica?: boolean; video?: 'ok' | 'error' } = {}) {
  const llamadas: string[] = []
  const ficha = o.ficha ?? { semaforo: 'verde', motivos: [], requiereAptoMedico: false, maquinasExcluidas: [] }
  const m: Manejador = (url, init) => {
    const metodo = init.method ?? 'GET'
    llamadas.push(`${metodo} ${url.replace(/^.*\/v1/, '')}`)
    if (/\/sesiones$/.test(url)) return ok({ sesionId: 's-1', socio: { id: 'socio-1', nombre: 'Carla Pérez', semaforo: 'verde' } }, 201)
    if (/\/mediciones$/.test(url))
      return ok(
        o.atipica
          ? { medicionId: 'm', atipica: true, usada: false, mensaje: 'Lectura atípica' }
          : { medicionId: 'm', atipica: false, usada: true },
        201,
      )
    if (/\/ficha-salud$/.test(url)) return ok(ficha)
    if (/\/rutinas\/generar$/.test(url)) return ok(RUTINA, 201)
    if (/\/prediccion\/espera/.test(url)) return ok({ hora: 19, dia: 0, sociosEnSala: 59, esperaMin: { 'M-17': 0.2, 'M-01': 6.8 } })
    if (/\/video$/.test(url))
      return o.video === 'error' ? ok({ detail: 'Videos no configurados' }, 503) : ok({ url: 'https://r2.example/video.mp4?firma=abc', expiraEnSeg: 900 })
    return ok({ detail: 'no encontrado' }, 404)
  }
  vi.stubGlobal('fetch', vi.fn(async (url: string, init: RequestInit = {}) => m(url, init)))
  return llamadas
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
  expect(screen.getByText(/La IA solo recibe el color de tu semáforo/)).toBeInTheDocument()
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

    expect(await screen.findByText(/Orden optimizado por el motor \(A\*\)/)).toBeInTheDocument()
    expect(screen.getByText('M-17')).toBeInTheDocument()
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
