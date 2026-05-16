type ApiResponse = {
  message: string;
};

async function getApiMessage(): Promise<ApiResponse> {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  const response = await fetch(`${apiUrl}/api/hello`, {
    cache: "no-store",
  });

  if (!response.ok) {
    throw new Error("No se pudo conectar con la API");
  }

  return response.json();
}

export default async function Home() {
  let apiMessage = "Esperando respuesta del backend";
  let isApiReady = false;

  try {
    const data = await getApiMessage();
    apiMessage = data.message;
    isApiReady = true;
  } catch {
    isApiReady = false;
  }

  return (
    <main className="shell">
      <section className="panel">
        <p className="eyebrow">FastAPI + Next.js</p>
        <h1>Indies esta listo.</h1>
        <p className="copy">
          Ya tienes un backend FastAPI y un frontend Next conectados por un
          endpoint inicial. Levanta ambos servidores y esta pantalla va a
          confirmar la conexion.
        </p>

        <div className="status" aria-label="Estado del proyecto">
          <div className="status-row">
            <span className="label">Frontend</span>
            <span className="pill">Next activo</span>
          </div>
          <div className="status-row">
            <span className="label">Backend</span>
            <span className={isApiReady ? "pill" : "pill error"}>
              {apiMessage}
            </span>
          </div>
        </div>
      </section>
    </main>
  );
}
