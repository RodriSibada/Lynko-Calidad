window.iniciarCompletarEspacio = function(idActividad) {
    const modal = document.getElementById(`modalExamen-${idActividad}`);
    if (!modal) return;

    const items = modal.querySelectorAll('.ejercicio-item');
    let currentIndex = 0;
    const totalEjercicios = items.length;

    function mostrarEjercicio(index) {
        items.forEach((item, idx) => {
            item.style.display = idx === index ? 'block' : 'none';
        });
    }

    const btnSiguiente = modal.querySelector('.btn-siguiente');
    if (btnSiguiente) {
        btnSiguiente.onclick = () => {
            if (currentIndex < totalEjercicios - 1) {
                currentIndex++;
                mostrarEjercicio(currentIndex);
            }
        };
    }

    const btnAnterior = modal.querySelector('.btn-anterior');
    if (btnAnterior) {
        btnAnterior.onclick = () => {
            if (currentIndex > 0) {
                currentIndex--;
                mostrarEjercicio(currentIndex);
            }
        };
    }

    const btnComprobar = modal.querySelector('.btn-comprobar');
    if (btnComprobar) {
        btnComprobar.onclick = async () => {
            const itemActual = items[currentIndex];
            if (!itemActual) return;

            const idCompletar = itemActual.getAttribute('data-id-completar');
            const input = itemActual.querySelector('.input-respuesta');
            const feedback = itemActual.querySelector('.feedback-msg');
            const respuestaUsuario = input.value.trim().toLowerCase();

            if (!respuestaUsuario) {
                feedback.style.color = '#e11d48';
                feedback.innerText = "Por favor escribe una respuesta.";
                return;
            }

            try {
                const response = await fetch('/actividades/completar-espacio/evaluar', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        id_completar_espacio: parseInt(idCompletar),
                        respuesta_usuario: respuestaUsuario
                    })
                });

                const resultado = await response.json();

                if (response.ok && resultado.es_correcta) {
                    feedback.style.color = '#10b981';
                    feedback.innerText = resultado.mensaje;
                    input.disabled = true;
                    itemActual.setAttribute('data-resuelto', 'true');

                    let todosResueltos = true;
                    items.forEach(it => {
                        if (it.getAttribute('data-resuelto') !== 'true') {
                            todosResueltos = false;
                        }
                    });

                    if (todosResueltos) {
                        const btnAbrir = document.querySelector(`.btn-abrir-modal-examen[data-id-actividad="${idActividad}"]`);
                        const idUsuario = btnAbrir ? btnAbrir.getAttribute('data-id-usuario') : null;
                        const yaCompletado = btnAbrir ? btnAbrir.getAttribute('data-completado') === 'true' : false;

                        if (!yaCompletado && idUsuario) {
                            try {
                                const respPuntos = await fetch('/completar-minijuego', {
                                    method: 'POST',
                                    headers: { 'Content-Type': 'application/json' },
                                    body: JSON.stringify({
                                        id_usuario: parseInt(idUsuario),
                                        actividad_id: parseInt(idActividad),
                                        puntos: 30
                                    })
                                });
                                const resPuntos = await respPuntos.json();
                                if (respPuntos.ok && resPuntos.status === "success") {
                                    alert("¡Felicidades! Has completado todos los ejercicios y ganado tus puntos 💎");
                                    location.reload();
                                }
                            } catch (e) {
                                console.error("Error al registrar puntos:", e);
                            }
                        } else {
                            alert("¡Excelente! Has terminado el repaso de esta actividad.");
                            location.reload();
                        }
                    } else {
                        setTimeout(() => {
                            if (currentIndex < totalEjercicios - 1) {
                                currentIndex++;
                                mostrarEjercicio(currentIndex);
                            }
                        }, 1200);
                    }

                } else {
                    feedback.style.color = '#e11d48';
                    feedback.innerText = resultado.mensaje || "Respuesta incorrecta.";
                }

            } catch (err) {
                console.error("Error al evaluar respuesta:", err);
                feedback.style.color = '#e11d48';
                feedback.innerText = "Error de conexión con el servidor.";
            }
        };
    }

    mostrarEjercicio(currentIndex);
}