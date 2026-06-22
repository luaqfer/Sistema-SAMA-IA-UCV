// frontend_web/app.js

const API_URL = "http://localhost:8000"; // Reemplaza por tu IP si pruebas en celular
let inventarioGlobal = [];
let html5QrcodeScanner = null;
let usuarioActual = null;

// 1. CARGA INICIAL (Solo si hay sesión)
async function cargarActivos() {
    if (!usuarioActual) return;
    try {
        const response = await fetch(`${API_URL}/api/activos`);
        if (!response.ok) throw new Error("Fallo de red");
        const activos = await response.json();
        
        inventarioGlobal = activos; 
        document.getElementById('server-status').innerHTML = '<span class="w-3 h-3 rounded-full bg-green-400"></span> Servidor Conectado';
        document.getElementById('server-status').className = "flex items-center gap-2 text-sm font-semibold text-green-400";
        
        let tabla = document.getElementById('tabla-activos');
        tabla.innerHTML = '';
        let operativos = 0, observacion = 0, bloqueados = 0;

        activos.forEach(activo => {
            let badgeClass = "";
            let estado = activo.estado_operativo.toUpperCase();
            
            if(estado === "OPERATIVO") {
                badgeClass = "bg-green-100 text-green-800";
                operativos++;
            } else if (estado.includes("OBSERVACION") || estado.includes("MANTENIMIENTO")) {
                badgeClass = "bg-yellow-100 text-yellow-800 font-bold";
                observacion++;
            } else {
                badgeClass = "bg-red-100 text-red-800 font-black border border-red-300 pulse-red";
                bloqueados++;
            }

            tabla.innerHTML += `
                <tr class="hover:bg-slate-50">
                    <td class="p-4 font-mono text-slate-500 text-xs">${activo.codigo_qr}</td>
                    <td class="p-4 font-bold text-slate-800">${activo.nombre_activo}</td>
                    <td class="p-4 text-slate-600 font-mono text-xs">S/ ${activo.valor_adquisicion.toFixed(2)}</td>
                    <td class="p-4"><span class="px-3 py-1 rounded-full text-xs ${badgeClass}">${activo.estado_operativo}</span></td>
                    <td class="p-4 text-center space-x-2">
                        <button onclick="abrirModalDetalle(${activo.id_activo})" class="bg-slate-600 hover:bg-slate-700 text-white px-3 py-1.5 rounded-lg text-xs font-semibold transition shadow-sm inline-flex items-center gap-1">
                            📄 Detalles
                        </button>
                        <button onclick="abrirModalInspeccion(${activo.id_activo}, '${activo.nombre_activo}', '${activo.codigo_qr}')" class="bg-blue-600 hover:bg-blue-700 text-white px-3 py-1.5 rounded-lg text-xs font-semibold transition shadow-sm inline-flex items-center gap-1">
                            🔍 Inspeccionar
                        </button>
                    </td>
                </tr>
            `;
        });

        document.getElementById('stat-total').innerText = activos.length;
        document.getElementById('stat-operativos').innerText = operativos;
        document.getElementById('stat-observacion').innerText = observacion;
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

// 3. IA Y DIAGNÓSTICO
function abrirModalInspeccion(id_activo, nombre, qr) {
    document.getElementById('modal-activo-id').value = id_activo;
    document.getElementById('modal-activo-nombre').value = nombre;
    document.getElementById('modal-qr-label').innerText = "QR: " + qr;
    
    document.getElementById('form-ia').reset();
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
            id_usuario: usuarioActual ? usuarioActual.id_usuario : 1,
            anomalia_operativa: parseFloat(document.getElementById('select-anomalia').value),
            integridad_estructural: parseFloat(document.getElementById('select-integridad').value),
            temperatura_trabajo: parseFloat(document.getElementById('select-temperatura').value),
            fuga_fluidos: parseFloat(document.getElementById('select-fugas').value)
        };

        const response = await fetch(`${API_URL}/api/predict`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || "Error en la evaluación IA");
        }

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
        alert("Fallo crítico: " + error.message);
        console.error(error);
    } finally {
        btnSubmit.innerText = "🧠 Procesar con Inteligencia Artificial";
        btnSubmit.disabled = false;
    }
}

// 4. REGISTRO DE NUEVOS ACTIVOS
function abrirModalNuevoActivo() {
    document.getElementById('modal-nuevo-activo').classList.remove('hidden');
}

function cerrarModalNuevoActivo() {
    document.getElementById('modal-nuevo-activo').classList.add('hidden');
    document.getElementById('form-nuevo-activo').reset();
}

async function registrarNuevoActivo(event) {
    event.preventDefault();
    const btnSubmit = document.getElementById('btn-submit-nuevo');
    btnSubmit.innerText = "Guardando...";
    btnSubmit.disabled = true;

    try {
        const formData = new FormData();
        formData.append('codigo_qr', document.getElementById('nuevo-qr').value.trim());
        formData.append('nombre_activo', document.getElementById('nuevo-nombre').value.trim());
        formData.append('id_categoria', document.getElementById('nuevo-categoria').value);
        formData.append('valor_adquisicion', document.getElementById('nuevo-valor').value);
        formData.append('ubicacion', document.getElementById('nuevo-ubicacion').value.trim());
        formData.append('marca', document.getElementById('nuevo-marca').value.trim());
        formData.append('num_serie', document.getElementById('nuevo-serie').value.trim());
        formData.append('fecha_compra', document.getElementById('nuevo-fecha-compra').value);
        
        const fotoInput = document.getElementById('nuevo-foto');
        if (fotoInput.files.length > 0) {
            formData.append('foto', fotoInput.files[0]);
        }
        
        const manualInput = document.getElementById('nuevo-manual');
        if (manualInput.files.length > 0) {
            formData.append('manual', manualInput.files[0]);
        }

        const response = await fetch(`${API_URL}/api/activos`, {
            method: 'POST',
            body: formData
        });

        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.detail || "Error al registrar el activo.");
        }

        alert("✅ " + data.mensaje);
        cerrarModalNuevoActivo();
        cargarActivos(); // Refrescar la tabla automáticamente

    } catch (error) {
        alert("⚠️ Fallo en el registro: " + error.message);
    } finally {
        btnSubmit.innerText = "💾 Guardar Activo (Operativo)";
        btnSubmit.disabled = false;
    }
}

// 5. GESTIÓN DE USUARIOS Y SESIÓN
async function ejecutarLogin(event) {
    event.preventDefault();
    const btn = document.getElementById('btn-login');
    const prevText = btn.innerText;
    btn.innerText = "Validando...";
    btn.disabled = true;

    try {
        const response = await fetch(`${API_URL}/api/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                usuario: document.getElementById('login-user').value.trim(),
                pin: document.getElementById('login-pin').value.trim()
            })
        });

        const data = await response.json();
        if (!response.ok) throw new Error(data.detail);

        usuarioActual = data.usuario;
        
        // Actualizar UI
        document.getElementById('pantalla-login').classList.add('hidden');
        document.getElementById('body-main').classList.remove('overflow-hidden');
        document.getElementById('nav-user-name').innerText = usuarioActual.nombre_usuario.toUpperCase();
        document.getElementById('nav-user-role').innerText = usuarioActual.rol;

        // Aplicar permisos de Rol
        if (usuarioActual.rol === 'OPERARIO') {
            document.getElementById('btn-registrar-activo').classList.add('hidden');
            document.getElementById('btn-refrescar-bd').classList.add('hidden');
        } else {
            document.getElementById('btn-registrar-activo').classList.remove('hidden');
            document.getElementById('btn-refrescar-bd').classList.remove('hidden');
        }

        cargarActivos(); // Cargar datos ahora que hay sesión
    } catch (error) {
        alert("Acceso denegado: " + error.message);
    } finally {
        btn.innerText = prevText;
        btn.disabled = false;
    }
}

function cerrarSesion() {
    usuarioActual = null;
    inventarioGlobal = [];
    document.getElementById('tabla-activos').innerHTML = '';
    document.getElementById('pantalla-login').classList.remove('hidden');
    document.getElementById('body-main').classList.add('overflow-hidden');
    document.getElementById('form-login').reset();
}

// Inicializar al cargar la página (mostrará el login)
// window.onload = cargarActivos; (Ya no, ahora esperamos el login)

// --- MODAL DE DETALLES ---
function abrirModalDetalle(id_activo) {
    const activo = inventarioGlobal.find(a => a.id_activo === id_activo);
    if (!activo) return;

    document.getElementById('detalle-qr-label').innerText = "QR: " + activo.codigo_qr;
    document.getElementById('detalle-nombre').innerText = activo.nombre_activo;
    document.getElementById('detalle-categoria').innerText = activo.nombre_categoria || "Sin categoría";
    document.getElementById('detalle-estado').innerText = activo.estado_operativo;
    
    // Asignar color al estado
    const estadoElem = document.getElementById('detalle-estado');
    if (activo.estado_operativo === 'OPERATIVO') estadoElem.className = 'font-bold text-green-600';
    else if (activo.estado_operativo.includes('OBSERVACION') || activo.estado_operativo.includes('MANTENIMIENTO')) estadoElem.className = 'font-bold text-yellow-600';
    else estadoElem.className = 'font-bold text-red-600';

    document.getElementById('detalle-valor').innerText = "S/ " + (activo.valor_adquisicion || 0).toFixed(2);
    document.getElementById('detalle-ubicacion').innerText = activo.ubicacion || "No registrada";
    document.getElementById('detalle-marca').innerText = activo.marca || "No registrada";
    document.getElementById('detalle-serie').innerText = activo.num_serie || "No registrado";
    document.getElementById('detalle-fecha').innerText = activo.fecha_compra || "No registrada";

    // Generar QR dinámico
    const qrUrl = `https://api.qrserver.com/v1/create-qr-code/?size=150x150&data=${encodeURIComponent(activo.codigo_qr)}`;
    document.getElementById('detalle-qr-img').src = qrUrl;
    // Guardamos los datos para impresión
    window.activoActualQR = activo;

    // Manejar fotografía
    const imgElem = document.getElementById('detalle-foto');
    const sinImgElem = document.getElementById('detalle-sin-foto');
    if (activo.foto_path) {
        imgElem.src = API_URL + "/" + activo.foto_path;
        imgElem.classList.remove('hidden');
        sinImgElem.classList.add('hidden');
    } else {
        imgElem.classList.add('hidden');
        sinImgElem.classList.remove('hidden');
    }

    // Manejar manual
    const manualElem = document.getElementById('detalle-manual');
    const sinManualElem = document.getElementById('detalle-sin-manual');
    if (activo.manual_path) {
        manualElem.href = API_URL + "/" + activo.manual_path;
        manualElem.classList.remove('hidden');
        sinManualElem.classList.add('hidden');
    } else {
        manualElem.classList.add('hidden');
        sinManualElem.classList.remove('hidden');
    }

    document.getElementById('modal-detalle').classList.remove('hidden');
}

function cerrarDetalle() {
    document.getElementById('modal-detalle').classList.add('hidden');
}

function imprimirQR() {
    if (!window.activoActualQR) return;
    
    const qrUrl = document.getElementById('detalle-qr-img').src;
    const nombre = window.activoActualQR.nombre_activo;
    const codigo = window.activoActualQR.codigo_qr;
    
    const ventanaImpresion = window.open('', '_blank', 'width=400,height=500');
    ventanaImpresion.document.write(`
        <html>
        <head>
            <title>Imprimir QR - ${codigo}</title>
            <style>
                body { font-family: Arial, sans-serif; text-align: center; margin-top: 50px; }
                .card { border: 2px dashed #000; display: inline-block; padding: 20px; border-radius: 10px; }
                img { width: 150px; height: 150px; }
                h2 { margin: 10px 0 5px 0; font-size: 18px; }
                p { margin: 0; font-size: 14px; color: #555; }
            </style>
        </head>
        <body>
            <div class="card">
                <img src="${qrUrl}" alt="QR" onload="window.print(); window.close();" />
                <h2>${nombre}</h2>
                <p>ID: ${codigo}</p>
                <p style="font-size: 10px; margin-top: 10px;">Sistema EAM SAMA</p>
            </div>
        </body>
        </html>
    `);
    ventanaImpresion.document.close();
}