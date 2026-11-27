let cartasSeleccionadas = [];
let parejasEncontradas = 0;
let totalParejas = 0;

window.iniciarMemoramaDinamico = function(idActividad, elementosBaseDatos) {
    let cartasDuplicadas = [];
    if (!elementosBaseDatos || !Array.isArray(elementosBaseDatos)) return;
    if (typeof temporizadorIntervalo !== 'undefined' && temporizadorIntervalo) clearInterval(temporizadorIntervalo);
    elementosBaseDatos.forEach((item, index) => {
        cartasDuplicadas.push({ idUnico: `${index}-a`, idOriginal: item.id, imagen: item.imagen_url, titulo: item.titulo });
        cartasDuplicadas.push({ idUnico: `${index}-b`, idOriginal: item.id, imagen: item.imagen_url, titulo: item.titulo });
    });

    cartasDuplicadas.sort(() => Math.random() - 0.5);
    totalParejas = elementosBaseDatos.length;
    parejasEncontradas = 0;
    cartasSeleccionadas = [];

    const tablero = document.getElementById(`tablero-${idActividad}`);
    const areaJuego = document.getElementById(`area-juego-${idActividad}`);
    const areaCuriosidades = document.getElementById(`area-curiosidades-${idActividad}`);

    if (areaCuriosidades) areaCuriosidades.style.display = "none";
    if (areaJuego) areaJuego.style.display = "block";
    if (!tablero) return;

    tablero.innerHTML = "";

    cartasDuplicadas.forEach(carta => {
        const divCarta = document.createElement('div');
        divCarta.className = 'carta-memorama';
        divCarta.setAttribute('data-id', carta.idOriginal);
        divCarta.setAttribute('data-unico', carta.idUnico);

        divCarta.innerHTML = `
            <div class="carta-inner">
                <div class="carta-front">❓</div>
                <div class="carta-back"><img src="${carta.imagen}" alt="${carta.titulo}"></div>
            </div>
        `;

        divCarta.addEventListener('click', () => {
            voltearCartaDinamica(divCarta, idActividad);
        });

        tablero.appendChild(divCarta);
    });

    iniciarContadorRegresivo(60, idActividad);
}

function iniciarContadorRegresivo(segundosTotales, idActividad) {
    let tiempoRestante = segundosTotales;
    const spanReloj = document.getElementById(`temporizador-${idActividad}`);

    if (typeof temporizadorIntervalo !== 'undefined' && temporizadorIntervalo) clearInterval(temporizadorIntervalo);

    temporizadorIntervalo = setInterval(() => {
        let minutos = Math.floor(tiempoRestante / 60);
        let segundos = tiempoRestante % 60;
        let textoMinutos = minutos < 10 ? '0' + minutos : minutos;
        let textoSegundos = segundos < 10 ? '0' + segundos : segundos;

        if (spanReloj) {
            spanReloj.innerText = `⏱️ ${textoMinutos}:${textoSegundos}`;
            if (tiempoRestante <= 10) {
                spanReloj.style.background = '#fee2e2';
                spanReloj.style.color = '#dc2626';
            } else {
                spanReloj.style.background = '#f1f5f9';
                spanReloj.style.color = '#0f172a';
            }
        }

        if (tiempoRestante <= 0) {
            clearInterval(temporizadorIntervalo);
            alert("¡Se ha acabado el tiempo! ⌛ Inténtalo de nuevo.");
            location.reload();
        }

        tiempoRestante--;
    }, 1000);
}

function voltearCartaDinamica(elemento, idActividad) {
    if (elemento.classList.contains("volteada") || elemento.classList.contains("encontrada") || cartasSeleccionadas.length >= 2) {
        return;
    }

    elemento.classList.add("volteada");
    cartasSeleccionadas.push(elemento);

    if (cartasSeleccionadas.length === 2) {
        let carta1 = cartasSeleccionadas[0];
        let carta2 = cartasSeleccionadas[1];

        let id1 = carta1.getAttribute("data-id");
        let id2 = carta2.getAttribute("data-id");
        let unico1 = carta1.getAttribute("data-unico");
        let unico2 = carta2.getAttribute("data-unico");

        if (id1 === id2 && unico1 !== unico2) {
            carta1.classList.add("encontrada");
            carta2.classList.add("encontrada");
            parejasEncontradas++;
            cartasSeleccionadas = [];

            if (parejasEncontradas === totalParejas) {
                if (temporizadorIntervalo) clearInterval(temporizadorIntervalo);

                setTimeout(() => {
                    const areaJuego = document.getElementById(`area-juego-${idActividad}`);
                    const areaCuriosidades = document.getElementById(`area-curiosidades-${idActividad}`);
                    if (areaJuego) areaJuego.style.display = "none";
                    if (areaCuriosidades) areaCuriosidades.style.display = "block";
                }, 500);
            }
        } else {
            setTimeout(() => {
                carta1.classList.remove("volteada");
                carta2.classList.remove("volteada");
                cartasSeleccionadas = [];
            }, 1000);
        }
    }
}