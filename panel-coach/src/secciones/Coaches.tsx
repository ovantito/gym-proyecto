import { useState, type FormEvent } from 'react'
import * as api from '../api/cliente'
import type { CoachAdmin, SocioAdmin, TraspasoOut } from '../api/cliente'
import { Boton, Estado, Etiqueta, Tarjeta, Titulo } from '../componentes/ui'
import { useCarga } from '../hooks'

const MOTIVOS_REASIGNAR = ['Cambio de turno', 'Pedido del socio', 'Balancear carga']
const MOTIVOS_TRASPASO = ['Renuncia', 'Vacaciones', 'Licencia']
const CAMPO = 'mt-1 w-full rounded-xl border border-borde bg-fondo px-4 py-3 text-[16px] text-texto outline-none focus:border-naranja'
const msg = (e: unknown, defecto: string) => (e instanceof api.ErrorApi ? e.message : defecto)   // errores del backend, tal cual

const fecha = (iso: string) => new Date(iso).toLocaleString('es-PE', { dateStyle: 'short', timeStyle: 'short' })

function Motivo({ motivos, valor, alCambiar, etiqueta }: { motivos: string[]; valor: string; alCambiar: (m: string) => void; etiqueta: string }) {
  return (
    <>
      <div className="mt-3 flex flex-wrap gap-2">
        {motivos.map((m) => (
          <Boton key={m} variante="secundario" onClick={() => alCambiar(m)}>
            {m}
          </Boton>
        ))}
      </div>
      <input aria-label={etiqueta} className={CAMPO} maxLength={200} placeholder="Motivo (obligatorio)" value={valor} onChange={(e) => alCambiar(e.target.value)} />
    </>
  )
}

/** Solo admin: coaches, reasignar un socio y traspasar todos los socios de un coach. */
export function Coaches({ clave, alCambiar }: { clave: number; alCambiar: () => void }) {
  const carga = useCarga(api.listarCoaches, clave)
  return (
    <>
      <Titulo titulo="Coaches y socios" sub="Solo el administrador reasigna socios. Al moverlos, sus alertas y rutinas por aprobar pasan con ellos y todo queda en el historial." />
      <Estado carga={carga}>
        {(coaches) => (
          <div className="space-y-5">
            <TablaCoaches coaches={coaches} alCambiar={alCambiar} />
            <ReasignarSocio coaches={coaches} alCambiar={alCambiar} />
            <Traspaso coaches={coaches} alCambiar={alCambiar} />
          </div>
        )}
      </Estado>
    </>
  )
}

function FilaCoach({ c, alCambiar }: { c: CoachAdmin; alCambiar: () => void }) {
  const [error, setError] = useState<string | null>(null)
  const [ocupado, setOcupado] = useState(false)
  const alternar = async () => {
    setOcupado(true)
    setError(null)
    try {
      await api.cambiarEstadoCoach(c.id, !c.activo)
      alCambiar()
    } catch (e) {
      setError(msg(e, 'No se pudo cambiar el estado.'))
    } finally {
      setOcupado(false)
    }
  }
  return (
    <tr className="border-t border-borde align-top">
      <td className="py-3 pr-4 font-bold">{c.nombre}</td>
      <td className="py-3 pr-4 text-suave">{c.email}</td>
      <td className="py-3 pr-4">
        <Etiqueta tipo={c.activo ? 'verde' : 'rojo'}>{c.activo ? 'activo' : 'inactivo'}</Etiqueta>
      </td>
      <td className="py-3 pr-4">{c.socios}</td>
      <td className="py-3 pr-4">{c.alertasAbiertas}</td>
      <td className="py-3 pr-4">{c.rutinasPendientes}</td>
      <td className="py-3">
        <Boton variante="secundario" disabled={ocupado} onClick={alternar} aria-label={`${c.activo ? 'Desactivar' : 'Activar'} a ${c.nombre}`}>
          {c.activo ? 'Desactivar' : 'Activar'}
        </Boton>
        {error && (
          <p role="alert" className="mt-2 max-w-[260px] text-[14px] text-[#ffb4b6]">
            {error}
          </p>
        )}
      </td>
    </tr>
  )
}

function TablaCoaches({ coaches, alCambiar }: { coaches: CoachAdmin[]; alCambiar: () => void }) {
  return (
    <Tarjeta>
      <h3 className="mb-3 text-[18px] font-bold">Coaches</h3>
      <table className="w-full text-left text-[15px]">
        <thead className="text-[13px] uppercase text-suave">
          <tr>
            <th className="pb-2 pr-4">Nombre</th>
            <th className="pb-2 pr-4">Email</th>
            <th className="pb-2 pr-4">Estado</th>
            <th className="pb-2 pr-4">Socios</th>
            <th className="pb-2 pr-4">Alertas abiertas</th>
            <th className="pb-2 pr-4">Rutinas pendientes</th>
            <th className="pb-2" />
          </tr>
        </thead>
        <tbody>
          {coaches.map((c) => (
            <FilaCoach key={c.id} c={c} alCambiar={alCambiar} />
          ))}
        </tbody>
      </table>
    </Tarjeta>
  )
}

function ReasignarSocio({ coaches, alCambiar }: { coaches: CoachAdmin[]; alCambiar: () => void }) {
  const [dni, setDni] = useState('')
  const [socio, setSocio] = useState<SocioAdmin | null>(null)
  const [nuevo, setNuevo] = useState('')
  const [motivo, setMotivo] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [hecho, setHecho] = useState<string | null>(null)
  const [ocupado, setOcupado] = useState(false)

  const buscar = async (e: FormEvent) => {
    e.preventDefault()
    setOcupado(true)
    setError(null)
    setHecho(null)
    setSocio(null)
    try {
      setSocio(await api.buscarSocioAdmin(dni))
      setNuevo('')
      setMotivo('')
    } catch (err) {
      setError(msg(err, 'No se pudo buscar el socio.'))
    } finally {
      setOcupado(false)
    }
  }

  const reasignar = async (e: FormEvent) => {
    e.preventDefault()
    if (!socio) return
    setOcupado(true)
    setError(null)
    try {
      const actualizado = await api.reasignarSocio(socio.id, nuevo, motivo.trim())
      setSocio(actualizado)
      setHecho(`${actualizado.nombre} ahora es de ${actualizado.coach.nombre ?? 'otro coach'}.`)
      setNuevo('')
      setMotivo('')
      alCambiar()
    } catch (err) {
      setError(msg(err, 'No se pudo reasignar.'))
    } finally {
      setOcupado(false)
    }
  }

  const candidatos = coaches.filter((c) => c.activo && c.id !== socio?.coach.id)
  return (
    <Tarjeta>
      <h3 className="text-[18px] font-bold">Reasignar un socio</h3>
      <form onSubmit={buscar} className="mt-3 flex items-end gap-3" aria-label="Buscar socio a reasignar">
        <label className="text-[14px] font-semibold text-suave">
          DNI del socio
          <input className={`${CAMPO} w-[220px]`} inputMode="numeric" maxLength={8} placeholder="8 dígitos" value={dni} onChange={(e) => setDni(e.target.value.replace(/\D/g, ''))} />
        </label>
        <Boton type="submit" disabled={ocupado || dni.length !== 8} className="!py-3">
          Buscar socio
        </Boton>
      </form>
      {socio && (
        <div className="mt-4">
          <p className="text-[17px]">
            <span className="font-bold">{socio.nombre}</span> · DNI {socio.dni} · Coach actual: <span className="font-bold">{socio.coach.nombre ?? '—'}</span>
          </p>
          {socio.historial.length > 0 && (
            <ul className="mt-2 list-disc pl-5 text-[14px] text-suave">
              {socio.historial.map((h) => (
                <li key={h.id}>
                  {fecha(h.fecha)} · {h.coachAntes.nombre ?? '—'} → {h.coachDespues.nombre ?? '—'} · {h.motivo}
                </li>
              ))}
            </ul>
          )}
          <form onSubmit={reasignar} aria-label="Reasignar socio" className="mt-4">
            <label className="text-[14px] font-semibold text-suave">
              Coach nuevo
              <select className={CAMPO} value={nuevo} onChange={(e) => setNuevo(e.target.value)}>
                <option value="">Elige un coach…</option>
                {candidatos.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.nombre}
                  </option>
                ))}
              </select>
            </label>
            <Motivo motivos={MOTIVOS_REASIGNAR} valor={motivo} alCambiar={setMotivo} etiqueta="Motivo de la reasignación" />
            <Boton type="submit" disabled={ocupado || !nuevo || motivo.trim().length < 3} className="mt-3">
              Reasignar
            </Boton>
          </form>
        </div>
      )}
      {hecho && (
        <p role="status" className="mt-3 font-semibold text-sem-verde">
          {hecho}
        </p>
      )}
      {error && (
        <p role="alert" className="mt-3 text-[#ffb4b6]">
          {error}
        </p>
      )}
    </Tarjeta>
  )
}

function Traspaso({ coaches, alCambiar }: { coaches: CoachAdmin[]; alCambiar: () => void }) {
  const [origen, setOrigen] = useState('')
  const [destino, setDestino] = useState('')
  const [motivo, setMotivo] = useState('')
  const [desactivar, setDesactivar] = useState(false)
  const [confirmando, setConfirmando] = useState(false)
  const [ocupado, setOcupado] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [resultado, setResultado] = useState<TraspasoOut | null>(null)

  const nOrigen = coaches.find((c) => c.id === origen)
  const listo = !!origen && !!destino && origen !== destino && motivo.trim().length >= 3

  const ejecutar = async () => {
    setOcupado(true)
    setError(null)
    try {
      setResultado(await api.traspasarCoach(origen, destino, motivo.trim(), desactivar))
      setConfirmando(false)
      setOrigen('')
      setDestino('')
      setMotivo('')
      setDesactivar(false)
      alCambiar()
    } catch (err) {
      setError(msg(err, 'No se pudo traspasar.'))
      setConfirmando(false)
    } finally {
      setOcupado(false)
    }
  }

  return (
    <Tarjeta>
      <h3 className="text-[18px] font-bold">Traspasar todos los socios de un coach</h3>
      <p className="mt-1 text-[14px] text-suave">Para renuncias, vacaciones o licencias: mueve sus socios, alertas abiertas y rutinas por aprobar.</p>
      <form
        aria-label="Traspasar socios"
        className="mt-3"
        onSubmit={(e) => {
          e.preventDefault()
          if (listo) setConfirmando(true)
        }}
      >
        <div className="grid grid-cols-2 gap-4">
          <label className="text-[14px] font-semibold text-suave">
            Coach de origen
            <select className={CAMPO} value={origen} onChange={(e) => { setOrigen(e.target.value); setConfirmando(false) }}>
              <option value="">Elige un coach…</option>
              {coaches.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.nombre} ({c.socios} socios)
                </option>
              ))}
            </select>
          </label>
          <label className="text-[14px] font-semibold text-suave">
            Coach de destino
            <select className={CAMPO} value={destino} onChange={(e) => { setDestino(e.target.value); setConfirmando(false) }}>
              <option value="">Elige un coach…</option>
              {coaches.filter((c) => c.activo && c.id !== origen).map((c) => (
                <option key={c.id} value={c.id}>
                  {c.nombre}
                </option>
              ))}
            </select>
          </label>
        </div>
        <Motivo motivos={MOTIVOS_TRASPASO} valor={motivo} alCambiar={(m) => { setMotivo(m); setConfirmando(false) }} etiqueta="Motivo del traspaso" />
        <label className="mt-3 flex items-center gap-3 text-[15px]">
          <input type="checkbox" checked={desactivar} onChange={(e) => setDesactivar(e.target.checked)} />
          Desactivar al coach de origen
        </label>
        {!confirmando && (
          <Boton type="submit" disabled={!listo || ocupado} className="mt-3">
            Traspasar
          </Boton>
        )}
      </form>
      {confirmando && (
        <div role="alertdialog" aria-label="Confirmar traspaso" className="mt-4 rounded-2xl border border-sem-amarillo/60 bg-sem-amarillo/10 p-4">
          <p className="text-[16px] font-semibold">
            Vas a pasar los socios de {nOrigen?.nombre} a {coaches.find((c) => c.id === destino)?.nombre}
            {desactivar ? ' y desactivar al primero' : ''}. Esto queda registrado en el historial.
          </p>
          <div className="mt-3 flex gap-3">
            <Boton disabled={ocupado} onClick={ejecutar}>
              {ocupado ? 'Traspasando…' : `Sí, traspasar ${nOrigen?.socios ?? 0} socios`}
            </Boton>
            <Boton variante="secundario" disabled={ocupado} onClick={() => setConfirmando(false)}>
              Cancelar
            </Boton>
          </div>
        </div>
      )}
      {resultado && (
        <p role="status" className="mt-3 font-semibold text-sem-verde">
          Se movieron {resultado.sociosMovidos} socios, {resultado.alertasMovidas} alertas y {resultado.rutinasMovidas} rutinas.
        </p>
      )}
      {error && (
        <p role="alert" className="mt-3 text-[#ffb4b6]">
          {error}
        </p>
      )}
    </Tarjeta>
  )
}
