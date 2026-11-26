import { useState } from 'react'
import * as api from '../api/cliente'
import type { Nivel, SocioRiesgo } from '../api/cliente'
import { Boton, Estado, Etiqueta, nombrePerfil, Tarjeta, Titulo } from '../componentes/ui'
import { useCarga } from '../hooks'

const COLOR_EFECTO = { sube: 'text-[#ffb4b6]', baja: 'text-sem-verde', neutro: 'text-suave' } as const
const FLECHA = { sube: '▲', baja: '▼', neutro: '•' } as const

function Fila({ s, alAtender }: { s: SocioRiesgo; alAtender: () => void }) {
  const [ocupado, setOcupado] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const atender = async () => {
    if (!s.alertaId) return
    setOcupado(true)
    try {
      await api.registrarContacto(s.alertaId)
      alAtender()
    } catch (e) {
      setError(e instanceof api.ErrorApi ? e.message : 'No se pudo registrar.')
    } finally {
      setOcupado(false)
    }
  }
  return (
    <tr className="border-t border-borde align-top">
      <td className="py-3 pr-4">
        <p className="font-bold">{s.nombre}</p>
        <p className="text-[13px] text-suave">{nombrePerfil(s.segmento)}</p>
      </td>
      <td className="py-3 pr-4">
        <p className="text-[20px] font-extrabold">{Math.round(s.probabilidad * 100)}%</p>
        <div className="mt-1 h-1.5 w-24 rounded-full bg-borde">
          <div className="h-1.5 rounded-full bg-naranja" style={{ width: `${Math.round(s.probabilidad * 100)}%` }} />
        </div>
      </td>
      <td className="py-3 pr-4">
        <Etiqueta tipo={s.nivel}>{s.nivel}</Etiqueta>
      </td>
      <td className="py-3 pr-4 text-[14px]">
        <ul className="space-y-0.5">
          {s.factores.map((f) => (
            <li key={f.dato} className={COLOR_EFECTO[f.efecto]}>
              {FLECHA[f.efecto]} {f.texto}
            </li>
          ))}
        </ul>
      </td>
      <td className="py-3 text-right">
        {s.alertaId ? (
          <Boton variante="secundario" disabled={ocupado} onClick={atender}>
            Registrar contacto
          </Boton>
        ) : (
          <span className="text-[13px] text-suave">{s.nivel === 'alto' ? 'Contactado' : '—'}</span>
        )}
        {error && <p className="mt-1 text-[12px] text-[#ffb4b6]">{error}</p>}
      </td>
    </tr>
  )
}

export function Riesgo({ clave }: { clave: number }) {
  const carga = useCarga(api.sociosRiesgo, clave)
  const [filtro, setFiltro] = useState<Nivel | 'todos'>('todos')
  return (
    <>
      <Titulo
        titulo="Riesgo de abandono"
        sub="Probabilidad de que el socio deje el gimnasio en los próximos 30 días (modelo Random Forest). ▲ rojo = ese dato aumenta el riesgo; ▼ verde = lo reduce."
      />
      <Estado carga={carga} vacio={(d) => (d.analizado ? null : 'Aún no hay análisis. Se calcula cada noche; un admin puede ejecutarlo ahora con el botón de arriba.')}>
        {(d) => {
          const filas = d.socios.filter((s) => filtro === 'todos' || s.nivel === filtro)
          return (
            <Tarjeta>
              <div className="mb-3 flex items-center gap-2">
                {(['todos', 'alto', 'medio', 'bajo'] as const).map((f) => (
                  <button
                    key={f}
                    type="button"
                    aria-pressed={filtro === f}
                    onClick={() => setFiltro(f)}
                    className={`rounded-full border px-4 py-1 text-[14px] font-semibold capitalize ${filtro === f ? 'border-naranja bg-naranja/20 text-naranja' : 'border-borde text-suave'}`}
                  >
                    {f}
                  </button>
                ))}
                <span className="ml-auto text-[13px] text-suave">
                  Mostrando {filas.length} de {d.totalSocios} socios (los de mayor riesgo primero)
                </span>
              </div>
              <table className="w-full text-left text-[15px]">
                <thead className="text-[13px] uppercase text-suave">
                  <tr>
                    <th className="pb-2">Socio</th>
                    <th className="pb-2">Probabilidad</th>
                    <th className="pb-2">Nivel</th>
                    <th className="pb-2">Lo que más pesa</th>
                    <th className="pb-2" />
                  </tr>
                </thead>
                <tbody>
                  {filas.map((s) => (
                    <Fila key={s.id} s={s} alAtender={carga.recargar} />
                  ))}
                </tbody>
              </table>
            </Tarjeta>
          )
        }}
      </Estado>
    </>
  )
}
