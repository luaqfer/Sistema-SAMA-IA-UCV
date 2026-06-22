// frontend_web/app.js

const API_URL = "http://localhost:8000"; // Reemplaza por tu IP si pruebas en celular
let inventarioGlobal = [];
let html5QrcodeScanner = null;

// 1. CARGA INICIAL
async function cargarActivos() {
    try {
        const response = await fetch(`${API_URL}/api/activos`);
        if (!response.ok) throw new Error("Fallo de red");
        const activos = await response.json();
        
        inventarioGlobal = activos; 
        document.getElementById('server-status').innerHTML = '<span class="w-3 h-3 rounded-full bg-green-400"></span> Servidor Conectado';
        document.getElementById('server-status').className = "flex items-center gap-2 text-sm font-semibold text-green-400";
        
        let tabla = document.getElementById('tabla-activos');
        tabla.innerHTML = '';
        let operativos = 0, bloqueados = 0;

        activos.forEach(activo => {
            let badgeClass = activo.estado_operativo === "OPERATIVO" ? "bg-green-100 text-green-800" : "bg-red-100 text-red-800 font-black border border-red-300 pulse-red";
            if(activo.estado_operativo === "OPERATIVO") operativos++; else bloqueados++;

            tabla.innerHTML += `
                <tr class="hover:bg-slate-50">
                    <td class="p-4 font-mono text-slate-500 text-xs">${activo.codigo_qr}</td>
                    <td class="p-4 font-bold text-slate-800">${activo.nombre_activo}</td>
                    <td class="p-4 text-slate-600 font-mono text-xs">S/ ${activo.valor_adquisicion.toFixed(2)}</td>
                    <td class="p-4"><span class="px-3 py-1 rounded-full text-xs ${badgeClass}">${activo.estado_operativo}</span></td>
                    <td class="p-4 text-center">
                        <button onclick="abrirModalInspeccion(${activo.id_activo}, '${activo.nombre_activo}', '${activo.codigo_qr}')" class="text-blue-600 hover:text-blue-800 font-bold text-xs underline">
                            Inspeccionar
                        </button>
                    </td>
                </tr>
            `;
        });

        document.getElementById('stat-total').innerText = activos.length;
        document.getElementById('stat-operativos').innerText = operativos;
        document.getElementById('stat-bloqueados').innerText = bloqueados;
        document.getElementById('card-bloqueados').className = bloqueados > 0 ? "bg-white p-6 rounded-xl shadow border-l-4 border-red-500 pulse-red" : "bg-white p-6 rounded-xl shadow border-l-4 border-red-500";
    } catch (error) {
        document.getElementById('tabla-activos').innerHTML = `<tr><td colspan="5" class="p-8 text-center text-red-500 font-bold">⚠️ Error: SAMA Backend desconectado.</td></tr>`;
    }
}

// 2. CONTROL DEL ESCÁNER QR Y BÚSQUEDA
function buscarActivoManual() {
    let qrBuscado = document.getElementById('input-qr-manual').value.trim();
    procesarCodigoEscaneado(qrBuscado);
}

function abrirEscaner() {
    document.getElementById('modal-scanner').classList.remove('hidden');
    html5QrcodeScanner = new Html5QrcodeScanner("reader", { fps: 10, qrbox: {width: 250, height: 250} }, false);
    html5QrcodeScanner.render(onScanSuccess, onScanFailure);
}

function cerrarEscaner() {
    document.getElementById('modal-scanner').classList.add('hidden');
    if(html5QrcodeScanner) { html5QrcodeScanner.clear(); }
}

function onScanSuccess(decodedText, decodedResult) {
    cerrarEscaner();
    procesarCodigoEscaneado(decodedText);
}

function onScanFailure(error) { /* Ignorar errores de enfoque */ }

function procesarCodigoEscaneado(codigoQR) {
    const maquina = inventarioGlobal.find(a => a.codigo_qr === codigoQR);
    if (maquina) {
        abrirModalInspeccion(maquina.id_activo, maquina.nombre_activo, maquina.codigo_qr);
        document.getElementById('input-qr-manual').value = ''; 
    } else {
        alert(`SAMA Alerta: El código [${codigoQR}] no está registrado.`);
    }
}

// 3. COMUNICACIÓN CON EL MOTOR DE IA EN PYTHON
function abrirModalInspeccion(id, nombre, qr) {
    document.getElementById('modal-activo-id').value = id;
    document.getElementById('modal-activo-nombre').value = nombre;
    document.getElementById('modal-qr-label').innerText = `QR: ${qr}`;
    document.getElementById('form-ia').classList.remove('hidden');
    document.getElementById('panel-resultado-ia').classList.add('hidden');
    document.getElementById('modal-inspeccion').classList.remove('hidden');
}

function cerrarModal() {
    document.getElementById('modal-inspeccion').classList.add('hidden');
}

function resetearInspeccion() {
    cerrarModal();
    cargarActivos();
}

async function ejecutarDiagnosticoIA(event) {
    event.preventDefault();
    const btnSubmit = document.getElementById('btn-submit-ia');
    btnSubmit.innerText = "Calculando Centroide Difuso...";
    btnSubmit.disabled = true;

    try {
        const payload = {
            id_activo: parseInt(document.getElementById('modal-activo-id').value),
            id_usuario: 1,
            anomalia_operativa: parseFloat(document.getElementById('select-anomalia').value),
            integridad_estructural: parseFloat(document.getElementById('select-integridad').value)
        };

        const response = await fetch(`${API_URL}/api/predict`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const data = await response.json();

        document.getElementById('form-ia').classList.add('hidden');
        const panelResultados = document.getElementById('panel-resultado-ia');
        const semaforoHeader = document.getElementById('semaforo-header');
        panelResultados.classList.remove('hidden');
        
        document.getElementById('res-salud').innerText = `${data.indice_salud_pct}%`;
        document.getElementById('res-uso').innerText = data.frecuencia_uso_detectada;
        document.getElementById('resultado-mensaje').innerText = data.mensaje;

        if (data.alerta_bloqueo_disparada) {
            semaforoHeader.className = "rounded-xl p-5 border bg-red-600 border-red-700 text-white pulse-red animate-bounce";
            document.getElementById('resultado-titulo').innerText = "⚠️ BLOQUEO ACTIVADO";
        } else {
            semaforoHeader.className = "rounded-xl p-5 border bg-green-500 border-green-600 text-white";
            document.getElementById('resultado-titulo').innerText = "✅ ESTADO SEGURO";
        }
    } catch (error) {
        alert("Error conectando con el motor Python.");
    } finally {
        btnSubmit.innerText = "🧠 Procesar con Inteligencia Artificial";
        btnSubmit.disabled = false;
    }
}

// Inicializar al cargar la página
window.onload = cargarActivos;