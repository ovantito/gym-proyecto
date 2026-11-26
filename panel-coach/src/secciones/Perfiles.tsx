import { Bar, BarChart, CartesianGrid, Cell, LabelList, ResponsiveContainer, XAxis, YAxis } from 'recharts'
import * as api from '../api/cliente'
import { Estado, PERFILES, Tarjeta, Titulo } from '../componentes/ui'
import { useCarga } from '../hooks'

const COLORES = ['#e8873f', '#20a898', '#9fb0cb']

export function Perfiles({ clave }: { clave: number }) {
  const carga = useCarga(api.perfiles, clave)
  return (
    <>
      <Titulo titulo="Perfiles de socio" sub="Los socios se agrupan solos según cómo entrenan (K-Means). Sirve para personalizar el mensaje de cada grupo." />
      <Estado carga={carga} vacio={(d) => (d.analizado ? null : 'Aún no hay perfiles. Se calculan con el análisis nocturno (un admin puede ejecutarlo ahora).')}>
        {(d) => {
          const datos = d.perfiles.map((p) => ({ ...p, nombre: PERFILES[p.segmento]?.nombre ?? p.segmento }))
          return (
            <>
              <div className="grid grid-cols-3 gap-4">
                {datos.map((p, i) => (
                  <Tarjeta key={p.segmento}>
                    <div className="h-1.5 w-12 rounded-full" style={{ background: COLORES[i % 3] }} />
                    <h3 className="mt-3 text-[20px] font-bold">{p.nombre}</h3>
                    <p className="mt-1 min-h-[42px] text-[14px] text-suave">{PERFILES[p.segmento]?.descripcion}</p>
                    <p className="mt-3 text-[36px] font-extrabold leading-none">{p.socios}</p>
                    <p className="text-[13px] text-suave">socios</p>
                    <p className="mt-3 text-[22px] font-bold text-naranja">{p.riesgoMedioPct}%</p>
                    <p className="text-[13px] text-suave">riesgo medio de abandono · {p.riesgoAlto} en riesgo alto</p>
                  </Tarjeta>
                ))}
              </div>
              <Tarjeta className="mt-4">
                <h3 className="mb-3 text-[16px] font-bold">Riesgo medio de abandono por perfil (%)</h3>
                <div className="h-[260px]" role="img" aria-label="Gráfico de barras del riesgo medio por perfil">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={datos} margin={{ top: 20, right: 10, left: 0, bottom: 0 }}>
                      <CartesianGrid stroke="#34476b" vertical={false} />
                      <XAxis dataKey="nombre" stroke="#9fb0cb" tick={{ fontSize: 13 }} />
                      <YAxis stroke="#9fb0cb" unit="%" domain={[0, 100]} />
                      <Bar dataKey="riesgoMedioPct" radius={[8, 8, 0, 0]}>
                        {datos.map((p, i) => (
                          <Cell key={p.segmento} fill={COLORES[i % 3]} />
                        ))}
                        <LabelList dataKey="riesgoMedioPct" position="top" fill="#f4f6fb" formatter={(v) => `${v}%`} />
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </Tarjeta>
            </>
          )
        }}
      </Estado>
    </>
  )
}
