import { useState, type FormEvent } from 'react'
import { ejecutarAnalisisNocturno, ErrorApi, type LoteOut } from './api/cliente'
import { Boton } from './componentes/ui'
import { useSesion } from './estado/sesion'
import { Aprobar } from './secciones/Aprobar'
import { Mantenimiento } from './secciones/Mantenimiento'
import { Modelo } from './secciones/Modelo'
import { Perfiles } from './secciones/Perfiles'
import { Riesgo } from './secciones/Riesgo'

// ---------------------------------------------------------------- login
export function Login() {
  const { entrar, aviso } = useSesion()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [ocupado, setOcupado] = useState(false)

  const enviar = async (e: FormEvent) => {
    e.preventDefault()
    setOcupado(true)
    setError(null)
    try {
      await entrar(email, password)
    } catch (err) {
      setError(err instanceof ErrorApi ? err.message : 'Algo salió mal, intenta de nuevo.')
    } finally {
      setOcupado(false)
    }
  }
  const campo = 'mt-1 w-full rounded-xl border border-borde bg-fondo px-4 py-3 text-[17px] outline-none focus:border-naranja'
  return (
    <main className="flex h-full items-center justify-center">
      <form onSubmit={enviar} className="w-[420px] rounded-3xl bg-tarjeta p-8" aria-label="Iniciar sesión">
        <p className="text-[14px] font-bold tracking-[0.18em] text-naranja">TNT FIT · PANEL DEL COACH</p>
        <h1 className="mt-2 text-[32px] font-extrabold">Iniciar sesión</h1>
        {aviso && <p className="mt-3 rounded-xl bg-sem-amarillo/15 px-4 py-2 text-sem-amarillo">{aviso}</p>}
        <label className="mt-6 block text-[14px] font-semibold text-suave">
          Correo
          <input className={campo} type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} />
        </label>
        <label className="mt-4 block text-[14px] font-semibold text-suave">
          Contraseña
          <input className={campo} type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
        </label>
        {error && (
          <p role="alert" className="mt-4 rounded-xl border border-sem-rojo/60 bg-sem-rojo/10 px-4 py-2 text-[#ffb4b6]">
            {error}
          </p>
        )}
        <Boton type="submit" disabled={ocupado} className="mt-6 w-full !py-3 !text-[18px]">
          {ocupado ? 'Entrando…' : 'Entrar'}
        </Boton>
      </form>
    </main>
  )
}

// ---------------------------------------------------------------- panel
const SECCIONES = [
  { id: 'aprobar', texto: 'Rutinas por aprobar' },
  { id: 'riesgo', texto: 'Riesgo de abandono' },
  { id: 'perfiles', texto: 'Perfiles de socio' },
  { id: 'mantenimiento', texto: 'Estaciones y mantenimiento' },
  { id: 'modelo', texto: 'Modelo de IA' },
] as const
type Id = (typeof SECCIONES)[number]['id']

export function Panel() {
  const { usuario, salir } = useSesion()
  const [seccion, setSeccion] = useState<Id>('aprobar')
  const [clave, setClave] = useState(0) // cambia tras el análisis nocturno para recargar todo
  const [ejecutando, setEjecutando] = useState(false)
  const [resultado, setResultado] = useState<{ ok: boolean; texto: string } | null>(null)
  const esAdmin = usuario?.rol === 'admin'

  const correrAnalisis = async () => {
    setEjecutando(true)
    setResultado(null)
    try {
      const r: LoteOut = await ejecutarAnalisisNocturno()
      setResultado({ ok: true, texto: `Análisis listo: ${r.procesados} socios procesados, ${r.alertasNuevas} alertas nuevas.` })
      setClave((c) => c + 1)
    } catch (e) {
      setResultado({ ok: false, texto: e instanceof ErrorApi ? e.message : 'No se pudo ejecutar el análisis.' })
    } finally {
      setEjecutando(false)
    }
  }

  return (
    <div className="flex h-full">
      <aside className="flex w-[270px] shrink-0 flex-col bg-lateral p-5">
        <p className="text-[14px] font-bold tracking-[0.18em] text-naranja">TNT FIT</p>
        <p className="text-[18px] font-extrabold">Panel del coach</p>
        <nav className="mt-8 flex flex-1 flex-col gap-1" aria-label="Secciones">
          {SECCIONES.map((s) => (
            <button
              key={s.id}
              type="button"
              aria-current={seccion === s.id ? 'page' : undefined}
              onClick={() => setSeccion(s.id)}
              className={`rounded-xl px-4 py-3 text-left text-[16px] font-semibold transition ${seccion === s.id ? 'bg-naranja/20 text-naranja' : 'text-suave hover:bg-tarjeta'}`}
            >
              {s.texto}
            </button>
          ))}
        </nav>
        <div className="border-t border-borde pt-4 text-[14px]">
          <p className="font-bold">{usuario?.nombre}</p>
          <p className="mb-3 text-suave">{esAdmin ? 'Administrador (ve todo)' : 'Coach (solo tus socios)'}</p>
          <Boton variante="secundario" className="w-full" onClick={() => salir()}>
            Salir
          </Boton>
        </div>
      </aside>
      <main className="flex-1 overflow-y-auto p-8">
        {esAdmin && (
          <div className="mb-6 flex items-center gap-4 rounded-2xl bg-tarjeta px-5 py-3">
            <Boton disabled={ejecutando} onClick={correrAnalisis}>
              {ejecutando ? 'Analizando…' : 'Ejecutar análisis nocturno ahora'}
            </Boton>
            <p className="text-[14px] text-suave">Calcula riesgo de abandono y perfiles de todos los socios (normalmente corre solo cada noche).</p>
            {resultado && (
              <p role="status" className={`ml-auto text-[15px] font-semibold ${resultado.ok ? 'text-sem-verde' : 'text-[#ffb4b6]'}`}>
                {resultado.texto}
              </p>
            )}
          </div>
        )}
        {seccion === 'aprobar' && <Aprobar clave={clave} />}
        {seccion === 'riesgo' && <Riesgo clave={clave} />}
        {seccion === 'perfiles' && <Perfiles clave={clave} />}
        {seccion === 'mantenimiento' && <Mantenimiento clave={clave} />}
        {seccion === 'modelo' && <Modelo clave={clave} />}
      </main>
    </div>
  )
}
