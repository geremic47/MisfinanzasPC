# Mis Finanzas

Dashboard web de finanzas personales: registra ingresos y gastos, filtra por periodo y entidad, y revisa en un vistazo cuánto ahorras.

Es una página estática (HTML + React + Recharts) que guarda tus movimientos en la nube con [Supabase](https://supabase.com): inicias sesión y ves los mismos datos desde cualquier dispositivo.

## Funciones

- **Indicadores principales:** Ingresos, Gastos, Ahorros y Porcentaje de ahorro, en soles y dólares.
  - Ahorros = Ingresos − Gastos
  - Porcentaje de ahorro = Ahorros ÷ Ingresos × 100
  - Si los gastos superan a los ingresos se marca como *Déficit*.
- **Filtros** por año, mes, tipo, entidad financiera y método de pago.
- **Gráficos:** distribución de gastos por categoría (con categoría, monto y porcentaje al pasar el cursor) y gastos por método de pago, filtrable por entidad.
- **Tabla de registros** ordenable de mayor a menor (y viceversa) por cualquier columna, también con teclado.
- **Historial** con búsqueda, orden y paginación; **análisis por categorías**.
- **Registro de movimientos** con validación, edición y eliminación.
- **Importar y exportar CSV / respaldo JSON.**
- Tema claro y oscuro.

## Diseño

Paleta azul marino, tipografía IBM Plex Sans, estilo minimalista. Accesibilidad: foco visible, controles con `aria-pressed`, el estado de déficit no depende solo del color y se respeta `prefers-reduced-motion`.

## Uso

Despliega la carpeta como sitio estático (Vercel, GitHub Pages, etc.) y abre `index.html`. Se necesita conexión a internet para cargar React, Recharts, Supabase y la tipografía desde CDN, e iniciar sesión.

## Reporte mensual por correo

- Cada **día 3 a las 6:00 a. m. (hora de Lima)** un flujo de GitHub Actions (`.github/workflows/reporte-mensual.yml`) lee tus movimientos de Supabase, genera un PDF de 2 páginas (resumen del mes y cómo vamos en el año) y lo envía por correo con Resend.
- Meta de ahorro mensual: 30 % de los ingresos (variable `META_AHORRO_PCT` del flujo).
- En la app, *Configuración → Generar PDF → Enviar reporte PDF por correo* lanza el mismo envío para el mes elegido, mediante la función `supabase/functions/enviar-reporte`.
- Secretos (nunca en el código): `SUPABASE_SERVICE_ROLE_KEY`, `RESEND_API_KEY`, `REPORT_TO_EMAIL` en *GitHub → Settings → Secrets → Actions*, y `GH_DISPATCH_TOKEN` en los secretos de la función de Supabase. Variable opcional: `APP_USER_EMAIL`.
- Prueba local sin enviar: `python reporte/generar_reporte.py --csv mis-finanzas.csv --anio 2026 --mes 8`.

## Estructura

| Archivo | Descripción |
|---|---|
| `index.html` | Aplicación completa |
| `FinanzasPersonalesPC` | Misma aplicación (copia con el nombre original) |
| `reporte/generar_reporte.py` | Genera el PDF mensual y lo envía |
| `.github/workflows/reporte-mensual.yml` | Programación del envío |
| `supabase/functions/enviar-reporte` | Función que activa el envío desde el botón de la app |

## Flujo de ramas

- `main`: versión oficial publicada.
- `mejoras-dashboard`: pruebas y mejoras; se copia a `main` al terminar.

## Datos y privacidad

- Los movimientos viven en una tabla `movements` de Supabase protegida con Row Level Security: cada usuario solo accede a sus propias filas.
- El registro público está desactivado; solo entra el usuario creado en el panel de Supabase.
- La clave `anon` incluida en el código es pública por diseño; no hay claves secretas en el repositorio.
- El código solo trae datos de ejemplo. Al primer inicio de sesión en un dispositivo, los movimientos que ya tenía guardados el navegador se suben una sola vez a la nube.
- Respaldo: *Configuración → Exportar CSV / JSON*.
