import * as api from '../api/cliente'
import type { Falla } from '../api/cliente'
import { Estado, Tarjeta, Titulo } from '../componentes/ui'
import { useCarga } from '../hooks'

const FALLA: Record<Falla, { titulo: string; detalle: string }> = {
  báscula: { titulo: 'Báscula descalibrada', detalle: 'El peso saltó varios kilos de una visita a otra.' },
  electrodos: { titulo: 'Electrodos sucios', detalle: 'La grasa corporal cambió de forma imposible.' },
  duración: { titulo: 'Lector trabado', detalle: 'La medición duró mucho más o mucho menos de lo normal.' },
}

export function Mantenimiento({ clave }: { clave: number }) {
  const carga = useCarga(api.mantenimiento, clave, 10000)
  return (
    <>
      <Titulo
        titulo="Estaciones y mantenimiento"
        sub="Lecturas que el modelo Mean-Shift marcó como atípicas. No se usaron para ningún cálculo; si una estación repite la misma falla, hay que revisarla."
      />
      <Estado carga={carga} vacio={(d) => (d.length === 0 ? 'Sin lecturas atípicas. Todas las estaciones funcionan bien. ✓' : null)}>
        {(d) => (
          <div className="space-y-4">
            {d.map((g) => (
              <Tarjeta key={g.estacionId}>
                <div className="flex items-center justify-between">
                  <h3 className="text-[20px] font-bold">{g.estacion}</h3>
                  <span className="rounded-full bg-sem-amarillo/20 px-3 py-1 text-[13px] font-bold text-sem-amarillo">{g.lecturas.length} lecturas atípicas</span>
                </div>
                <table className="mt-3 w-full text-left text-[15px]">
                  <thead className="text-[13px] uppercase text-suave">
                    <tr>
                      <th className="pb-2">Fecha</th>
                      <th className="pb-2">Falla probable</th>
                      <th className="pb-2">Qué pasó</th>
                    </tr>
                  </thead>
                  <tbody>
                    {g.lecturas.map((l) => (
                      <tr key={l.fecha + l.falla} className="border-t border-borde">
                        <td className="py-2 pr-4">{new Date(l.fecha).toLocaleString('es-PE', { dateStyle: 'short', timeStyle: 'short' })}</td>
                        <td className="py-2 pr-4 font-bold">{FALLA[l.falla].titulo}</td>
                        <td className="py-2 text-suave">{FALLA[l.falla].detalle}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </Tarjeta>
            ))}
          </div>
        )}
      </Estado>
    </>
  )
}
