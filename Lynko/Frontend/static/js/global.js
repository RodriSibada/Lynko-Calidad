let activeCameraBaile = null;
let activePoseBaile = null;
let temporizadorIntervalo = null;

document.addEventListener("DOMContentLoaded", () => {
    // --- 1. APERTURA DE MODALES DINÁMICOS ---
    const botonesAbrir = document.querySelectorAll('.btn-abrir-modal-examen');
    botonesAbrir.forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            const idActividad = btn.getAttribute('data-id-actividad');
            const tipoActividad = btn.getAttribute('data-tipo-actividad');
            const idUsuario = btn.getAttribute('data-id-usuario');

            const modal = document.getElementById(`modalExamen-${idActividad}`);
            if (modal) {
                modal.style.setProperty('display', 'flex', 'important');
                modal.style.zIndex = '9999';
                document.body.style.overflow = 'hidden';

                if (tipoActividad === 'memoria' || tipoActividad === 'minijuego') {
                    const jsonContainer = document.querySelector(`.elementos-data-json-${idActividad}`);
                    if (jsonContainer) {
                        try {
                            const elementos = JSON.parse(jsonContainer.textContent.trim());
                            if (typeof iniciarMemoramaDinamico === 'function') {
                                iniciarMemoramaDinamico(idActividad, elementos);
                            }
                        } catch (err) {
                            console.error("Error al parsear JSON de memorama:", err);
                        }
                    }
                } else if (tipoActividad === 'baile') {
                    if (typeof iniciarMediaPipeBaile === 'function') {
                        iniciarMediaPipeBaile(idActividad, idUsuario, btn.getAttribute('data-completado') === 'true');
                    }
                } else if (tipoActividad === 'completar_espacio') {
                    if (typeof iniciarCompletarEspacio === 'function') {
                        iniciarCompletarEspacio(idActividad);
                    }
                }
            }
        });
    });

    // --- 2. CERRAR MODALES ---
    document.querySelectorAll('.btn-cerrar-modal').forEach(btn => {
        btn.addEventListener('click', () => {
            const idActividad = btn.getAttribute('data-id-actividad');
            const modal = document.getElementById(`modalExamen-${idActividad}`);
            if (modal) modal.style.display = 'none';

            if (typeof activeCameraBaile !== 'undefined' && activeCameraBaile) {
                activeCameraBaile.stop();
                activeCameraBaile = null;
            }
            if (typeof activePoseBaile !== 'undefined' && activePoseBaile) {
                activePoseBaile.close();
                activePoseBaile = null;
            }
            if (temporizadorIntervalo) clearInterval(temporizadorIntervalo);

            document.body.style.overflow = 'auto';
        });
    });

    // --- 3. ENVÍO DE FORMULARIO DE MEMORAMA ---
    document.querySelectorAll('.formExamenDinamico').forEach(form => {
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const idActividad = form.getAttribute('data-id-actividad');
            const btnAbrir = document.querySelector(`.btn-abrir-modal-examen[data-id-actividad="${idActividad}"]`);
            const idUsuario = btnAbrir ? btnAbrir.getAttribute('data-id-usuario') : null;
            const yaCompletado = btnAbrir ? btnAbrir.getAttribute('data-completado') === 'true' : false;

            if (yaCompletado) {
                alert("Esta actividad ya fue completada antes. No se suman puntos adicionales.");
                location.reload();
                return;
            }

            try {
                const response = await fetch('/completar-minijuego', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        id_usuario: parseInt(idUsuario),
                        actividad_id: parseInt(idActividad),
                        puntos: 40
                    })
                });
                const resultado = await response.json();
                if (response.ok && resultado.status === "success") {
                    alert("¡Reto completado con éxito! Puntos ganados 💎");
                    location.reload();
                } else {
                    alert(resultado.mensaje || "Error al registrar puntos.");
                }
            } catch (err) {
                console.error(err);
                alert("Error de conexión con el servidor.");
            }
        });
    });
});