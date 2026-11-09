// Edge Function: recibe la orden del botón "Enviar reporte PDF por correo" de la app
// y arranca el flujo de GitHub Actions que genera el PDF y lo envía.
// Secretos necesarios (Supabase → Edge Functions → Secrets): GH_DISPATCH_TOKEN

const REPO = "geremic47/MisfinanzasPC";
const WORKFLOW = "reporte-mensual.yml";

const cors = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};
const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { ...cors, "Content-Type": "application/json" } });

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: cors });
  if (req.method !== "POST") return json({ error: "Método no permitido" }, 405);

  // La clave anon también es un JWT válido, así que se exige un usuario con sesión iniciada.
  const auth = req.headers.get("Authorization") ?? "";
  const user = await fetch(`${Deno.env.get("SUPABASE_URL")}/auth/v1/user`, {
    headers: { Authorization: auth, apikey: Deno.env.get("SUPABASE_ANON_KEY") ?? "" },
  });
  if (!user.ok) return json({ error: "No autorizado" }, 401);

  let anio = 0, mes = 0;
  try {
    const b = await req.json();
    anio = Number(b.anio);
    mes = Number(b.mes);
  } catch (_) { /* cuerpo inválido */ }
  if (!Number.isInteger(anio) || !Number.isInteger(mes) || anio < 2000 || anio > 2100 || mes < 1 || mes > 12) {
    return json({ error: "Año o mes inválido" }, 400);
  }

  const gh = await fetch(`https://api.github.com/repos/${REPO}/actions/workflows/${WORKFLOW}/dispatches`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${Deno.env.get("GH_DISPATCH_TOKEN")}`,
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      "User-Agent": "mis-finanzas-enviar-reporte",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ ref: "main", inputs: { anio: String(anio), mes: String(mes) } }),
  });
  if (gh.status !== 204) return json({ error: "GitHub respondió " + gh.status }, 502);
  return json({ ok: true });
});
