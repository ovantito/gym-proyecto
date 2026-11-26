# Seguridad — explicada en simple

## 1. ¿Cómo sabe el backend que le habla una estación de verdad?
Cada estación tiene su **propia clave secreta** y la manda en la cabecera `X-Station-Key`. En la base de datos **no se guarda la clave**,
solo su **hash** (SHA-256, una "huella" que no se puede revertir). Si alguien roba la base, no puede usar las claves. Si una estación
se pierde o la roban, se desactiva (`activa = false`) y las demás siguen funcionando. Sin clave o con una falsa → **401**.
(Las claves son aleatorias de 256 bits; por eso basta un hash simple y no uno lento como el de las contraseñas humanas.)

## 2. ¿Y el coach y el administrador?
Entran con **Supabase Auth** y el backend recibe un **JWT** (un "pase" firmado con vencimiento). El backend **verifica la firma, la
audiencia y que no haya vencido** en cada petición. El rol (`socio`, `coach`, `admin`) viene dentro del pase, en `app_metadata`, que
solo el servidor puede escribir (el usuario no puede ponerse "admin" a sí mismo). Pase falso o vencido → **401**; rol insuficiente → **403**.
El rol `estacion` no existe en JWT: las estaciones usan su clave.

## 3. ¿Quién puede ver a quién?
- Un **coach solo ve a sus socios** (alertas, rutinas pendientes, fichas). Se hace cumplir **dos veces**: en el backend y en la base
  con **RLS (Row Level Security)**, que son reglas dentro de Postgres. Aunque alguien se saltara el backend, la base se niega.
- Una **estación solo trabaja con el socio que acaba de identificar** (sesión abierta en esa estación, máx. 30 min). No puede
  curiosear en otros socios, ni abrir sesiones en nombre de otra estación.
- El **socio** solo ve lo suyo.

## 4. Datos de salud (los más delicados)
- La **ficha de salud** (PAR-Q+, lesiones) está en su **propia tabla**, aparte de `socios`, con sus propias reglas RLS.
- **Los modelos de IA nunca reciben la ficha.** El modelo de abandono recibe solo variables de comportamiento y, de la salud, **únicamente
  el color del semáforo**. `var_grasa_pct` (dato de salud) se quitó del modelo y hay una **prueba automática** que falla si alguien la vuelve a meter.
- El semáforo es **reglas fijas** escritas en un archivo (`umbrales.py`), no IA: se puede explicar y auditar ("¿por qué rojo? porque la
  presión fue 165").
- Al abrir sesión, la estación recibe solo id, nombre y color; nunca la ficha.

## 5. Validación de lo que entra
**Pydantic** revisa cada dato antes de usarlo: el DNI son 8 dígitos, el peso está entre 20 y 300 kg, no se aceptan campos extra, etc.
Un dato raro → **422** y nunca llega a la lógica ni a la base. Los IDs de ejercicio de los videos siguen un patrón estricto (`E-M-01`),
así nadie puede pedir otro archivo del bucket con trucos como `../`.

## 6. Límite de peticiones
Con **slowapi** cada IP tiene un tope por minuto (120 en general, **10 para abrir sesión**, que es donde alguien podría probar DNIs
uno tras otro). Pasarse → **429**.

## 7. CORS
Solo los **dominios del frontend** listados en `CORS_ORIGINS` pueden llamar a la API desde un navegador. Si la lista está vacía, ninguno.

## 8. Ninguna clave en el código
Todo secreto (Supabase, JWT, Cloudflare R2) está en variables de entorno / `.env`. `.env` está en `.gitignore`; solo se sube
`.env.example` sin valores. La **secret key** de Supabase (`sb_secret_...`) solo vive en `backend/.env` y en las variables de entorno de Render; jamás en un frontend (estación o panel). La **publishable key** (`sb_publishable_...`) es pública por diseño y solo sirve para el login contra Supabase Auth. Si una clave se filtra se rota
en Supabase/Cloudflare y se cambia la variable, sin tocar código.

## 9. Videos (Cloudflare R2)
El backend no expone el bucket: entrega una **URL firmada que caduca en 15 minutos**. Pasado ese tiempo el enlace deja de servir,
así que compartirlo no da acceso permanente. Las credenciales de R2 solo las tiene el servidor.

## 10. Lecturas defectuosas
Si el sensor falla (p. ej. la báscula marca +6 kg de un día a otro), **Mean-Shift** marca la lectura como atípica: **no se usa** para
calcular nada y se **avisa a mantenimiento**. Así un sensor roto no genera un semáforo ni una rutina equivocados.

## 11. Cadena de desarrollo
El **CI** corre `ruff` y `pytest` en cada push y PR (si fallan las pruebas de seguridad, no se mezcla). Las dependencias críticas
(scikit-learn) están fijadas. Para el reentrenamiento mensual, los modelos nuevos salen como artefacto para revisarlos antes de desplegar.

## 12. Login del panel
`POST /v1/auth/login` valida correo y contraseña (las contraseñas se guardan con **scrypt + sal**, nunca en claro) y devuelve un JWT de 8 horas.
Tiene **límite de 5 intentos por minuto** y responde igual si el correo no existe o la contraseña está mal (no revela cuál usuario existe).
El panel guarda el token en `sessionStorage` (se borra al cerrar la pestaña) y, si el servidor responde 401, cierra la sesión sola.
Los usuarios demo solo existen en el modo en memoria; con contraseñas aleatorias impresas al arrancar.

## 13. QR permanente: una ruta pública, a propósito
`GET /v1/ejercicios/{id}/ver` **no pide credenciales** (el que escanea el QR es un socio sin cuenta) y redirige a una URL firmada nueva de 15 minutos.
Es seguro porque solo sirve videos de ejercicios (nada personal), el `id` tiene un patrón estricto (`E-M-01`) y tiene **límite de peticiones** (30/min por IP).
El QR del ticket nunca contiene una URL firmada, así que no caduca ni filtra acceso.

## 14. Aprobación de rutinas
Aprobar o rechazar exige ser el coach **dueño del socio** (o admin). La estación consulta el estado de la rutina (`GET /rutinas/{id}`) solo si tiene
una sesión abierta con ese socio. Rechazar guarda el motivo, que se muestra en la estación.

## 15. Claves de Supabase (nombres nuevos)
- `SUPABASE_PUBLISHABLE_KEY` (`sb_publishable_...`): pública por diseño (equivale a la antigua *anon*). El backend solo la usa en el login del panel.
- `SUPABASE_SECRET_KEY` (`sb_secret_...`): da acceso total a la base (equivale a *service_role*). Vive **solo** en `backend/.env` y en las variables de entorno de Render.
  Las claves `sb_secret_` no son JWT, por eso el backend las manda solo en la cabecera `apikey`.
- Hay una **prueba automática** que falla si `estacion/` o `panel-coach/` mencionan la secret key.
- Los frontends no hablan con Supabase: solo con el backend (`VITE_API_URL`). No necesitan `VITE_SUPABASE_*`.
- **JWT de Supabase con claves asimétricas (ES256):** el backend baja las claves públicas de `<SUPABASE_URL>/auth/v1/.well-known/jwks.json` (con caché) y verifica la firma con ellas;
  no necesita ningún secreto para validar tokens. HS256 solo se acepta si hay `SUPABASE_JWT_SECRET` (modo demo). El algoritmo se elige por lo que el servidor tiene configurado, no por lo que
  diga el token, y `alg: none` se rechaza (hay pruebas).

## Pendientes conocidos (fuera de esta fase)
HTTPS lo pone el despliegue (proxy/hosting). Rotación automática de claves de estación y auditoría de accesos a fichas de salud
quedan para una siguiente fase.
