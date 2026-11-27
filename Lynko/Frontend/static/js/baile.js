window.iniciarMediaPipeBaile = function(idActividad, idUsuario, yaCompletado) {
    const videoElement = document.getElementById(`webcam-${idActividad}`);
    const feedbackDiv = document.getElementById(`feedbackIcono-${idActividad}`);
    const btnCompletar = document.getElementById(`btn-completar-baile-${idActividad}`);

    if (!videoElement) return;

    const pose = new Pose({
        locateFile: (file) => `https://cdn.jsdelivr.net/npm/@mediapipe/pose/${file}`
    });

    pose.setOptions({
        modelComplexity: 1,
        smoothLandmarks: true,
        minDetectionConfidence: 0.5,
        minTrackingConfidence: 0.5
    });

    let aciertosContador = 0;
    let enviado = false;

    pose.onResults((results) => {
        if (!results.poseLandmarks) {
            if (feedbackDiv) {
                feedbackDiv.innerHTML = "❌ No se ve el cuerpo";
                feedbackDiv.style.background = "rgba(239, 68, 68, 0.8)";
            }
            return;
        }

        const muñecaIzq = results.poseLandmarks[15];
        const hombroIzq = results.poseLandmarks[11];
        const muñecaDer = results.poseLandmarks[16];
        const hombroDer = results.poseLandmarks[12];

        const brazoIzqArriba = muñecaIzq && hombroIzq && muñecaIzq.y < hombroIzq.y;
        const brazoDerArriba = muñecaDer && hombroDer && muñecaDer.y < hombroDer.y;

        if (brazoIzqArriba || brazoDerArriba) {
            if (feedbackDiv) {
                feedbackDiv.innerHTML = "⭐ ¡Excelente!";
                feedbackDiv.style.background = "rgba(16, 185, 129, 0.9)";
            }
            aciertosContador++;

            if (aciertosContador > 15 && btnCompletar && !yaCompletado) {
                btnCompletar.style.display = 'block';
                
                btnCompletar.onclick = async () => {
                    if (enviado) return;
                    enviado = true;
                    btnCompletar.disabled = true;
                    btnCompletar.innerText = "Guardando puntos...";

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
                            alert("¡Baile completado con éxito! Puntos reclamados 💃🕺");
                            location.reload();
                        } else {
                            alert(resultado.mensaje || "Error al registrar puntos.");
                            enviado = false;
                            btnCompletar.disabled = false;
                        }
                    } catch (err) {
                        console.error(err);
                        alert("Error de conexión al servidor.");
                        enviado = false;
                        btnCompletar.disabled = false;
                    }
                };
            }
        } else {
            if (feedbackDiv) {
                feedbackDiv.innerHTML = "⚠️ ¡Sube los brazos!";
                feedbackDiv.style.background = "rgba(245, 158, 11, 0.9)";
            }
        }
    });

    activePoseBaile = pose;

    const camera = new Camera(videoElement, {
        onFrame: async () => {
            if (activePoseBaile) {
                await activePoseBaile.send({ image: videoElement });
            }
        },
        width: 380,
        height: 280
    });
    camera.start();
    activeCameraBaile = camera;
}