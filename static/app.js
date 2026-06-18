// ============================================================
// LOGISTICS DISPATCH SIMULATOR — Frontend Controller
// Mengelola interaksi peta Leaflet dan komunikasi dengan backend
// ============================================================

// --- Inisialisasi Peta Leaflet ---
const map = L.map('map', {
    zoomControl: true,
    preferCanvas: true  // Canvas renderer untuk performa lebih baik (banyak marker)
}).setView([-7.2504, 109.5240], 6);

// Dark mode tile layer
L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    maxZoom: 19
}).addTo(map);


// ============================================================
// STATE
// ============================================================
let waypoints = []; // array of { id, lat, lng }
let waypointMarkers = []; // array of L.circleMarker
let dijkstraLine = null;   // Polyline rute Dijkstra
let fwLine = null;         // Polyline rute Floyd-Warshall (overlay)
let allNodeMarkers = {};   // { nodeId: L.circleMarker }
let nodesData = {};        // { nodeId: { lat, lng } }
let fwPollTimer = null;    // Timer polling FW status

let fuelPrices = {};
let lastDistanceMeters = null;
let lastTimeMinutes = null;
let lastFerryCrossings = 0;


// ============================================================
// DOM ELEMENTS
// ============================================================
const $waypointsList = document.getElementById('waypointsList');
const $emptyWaypointsText = document.getElementById('emptyWaypointsText');
const $btnSolve = document.getElementById('btnSolve');
const $btnSolveText = document.getElementById('btnSolveText');
const $iconSolve = document.getElementById('iconSolve');
const $spinnerSolve = document.getElementById('spinnerSolve');
const $btnClearMap = document.getElementById('btnClearMap');
const $resultsPanel = document.getElementById('resultsPanel');
const $instructionText = document.getElementById('instructionText');
const $badgeNodes = document.getElementById('badgeNodes');
const $badgeEdges = document.getElementById('badgeEdges');

// Kalkulator
const $selVehicle = document.getElementById('selVehicle');
const $selFuel = document.getElementById('selFuel');
const $statTimeMinutes = document.getElementById('statTimeMinutes');


const $statTotalCost = document.getElementById('statTotalCost');

// FW Status
const $fwStatusCard = document.getElementById('fwStatusCard');
const $fwStatusIcon = document.getElementById('fwStatusIcon');
const $fwStatusLabel = document.getElementById('fwStatusLabel');
const $fwProgressBar = document.getElementById('fwProgressBar');
const $fwProgressText = document.getElementById('fwProgressText');

// Results
const $statDijCost = document.getElementById('statDijCost');
const $statDijTime = document.getElementById('statDijTime');
const $statFWCost = document.getElementById('statFWCost');
const $statFWTime = document.getElementById('statFWTime');
const $consistencyIcon = document.getElementById('consistencyIcon');
const $consistencyLabel = document.getElementById('consistencyLabel');
const $consistencyDetail = document.getElementById('consistencyDetail');
const $consistencyCard = document.getElementById('consistencyCard');
const $statNodeCount = document.getElementById('statNodeCount');
const $statCoordCount = document.getElementById('statCoordCount');


// ============================================================
// LANGKAH 1: MUAT GRAF DARI BACKEND
// ============================================================
async function loadGraph() {
    try {
        const res = await fetch('/api/graph-info');
        const data = await res.json();

        nodesData = data.nodes;
        const nodeCount = data.node_count;
        const edgeCount = data.edge_count;

        $badgeNodes.textContent = `${nodeCount.toLocaleString()} nodes`;
        $badgeEdges.textContent = `${edgeCount.toLocaleString()} edges`;

        console.log(`[GRAPH] Dimuat: ${nodeCount} nodes, ${edgeCount} edges`);

        // Jangan lagi merender 50.000 titik biru ke peta untuk menghemat memori & mengatasi FPS drop.
        // Data nodesData tetap disimpan untuk kalkulasi pencarian node terdekat (nearest node) saat map diklik.

        // Sesuaikan view agar semua node terlihat
        const allLatLngs = Object.values(nodesData).map(c => [c.lat, c.lng]);
        if (allLatLngs.length > 0) {
            map.fitBounds(allLatLngs, { padding: [30, 30] });
        }

    } catch (err) {
        console.error('[GRAPH] Error memuat graf:', err);
    }
}

async function loadFuelPrices() {
    try {
        const res = await fetch('/api/fuel-prices');
        const data = await res.json();
        fuelPrices = data.prices;
        
        // Render initial options based on currently selected vehicle
        renderFuelOptions();
        
        updateEstimations();
    } catch (e) {
        console.error("[FUEL] Gagal load fuel prices", e);
        $selFuel.innerHTML = '<option value="0">Gagal memuat harga</option>';
    }
}

function renderFuelOptions() {
    // Get allowed fuel type from the selected vehicle option
    const allowedFuelType = $selVehicle.options[$selVehicle.selectedIndex].getAttribute('data-fuel');
    
    // Save current selection to restore it if possible
    const currentSelection = $selFuel.value;
    
    $selFuel.innerHTML = '';
    
    let hasMatchingOption = false;
    
    for (const [name, fuelData] of Object.entries(fuelPrices)) {
        // filter out fuels that don't match the vehicle type
        if (allowedFuelType !== 'both' && fuelData.type !== allowedFuelType) {
            continue; 
        }
        
        const opt = document.createElement('option');
        opt.value = fuelData.price;
        opt.textContent = `${name} (Rp ${fuelData.price.toLocaleString('id-ID')}/L)`;
        $selFuel.appendChild(opt);
        
        if (fuelData.price == currentSelection) {
            hasMatchingOption = true;
        }
    }
    
    // Restore selection if still valid in the new list
    if (hasMatchingOption) {
        $selFuel.value = currentSelection;
    }
}

function updateEstimations() {
    if (lastDistanceMeters === null || lastDistanceMeters === undefined) return;
    
    // Waktu Tempuh
    if (lastTimeMinutes !== null) {
        let mins = parseFloat(lastTimeMinutes);
        if (mins >= 60) {
            let hours = Math.floor(mins / 60);
            let remMins = Math.round(mins % 60);
            $statTimeMinutes.textContent = `${hours} jam ${remMins} mnt`;
        } else {
            $statTimeMinutes.textContent = `${lastTimeMinutes} mnt`;
        }
    }
    
    // Biaya Bensin
    const kmPerLiter = parseFloat($selVehicle.value) || 12;
    const pricePerLiter = parseFloat($selFuel.value) || 0;
    
    // Biaya Feri
    const selectedOption = $selVehicle.options[$selVehicle.selectedIndex];
    const ferryPricePerTrip = parseFloat(selectedOption.getAttribute('data-ferry')) || 0;
    
    const distanceKm = lastDistanceMeters / 1000;
    const requiredLiters = distanceKm / kmPerLiter;
    const fuelCost = Math.round(requiredLiters * pricePerLiter);
    
    const ferryCost = Math.round(lastFerryCrossings * ferryPricePerTrip);
    const totalCost = fuelCost + ferryCost;
    


    $statTotalCost.textContent = totalCost.toLocaleString('id-ID');
}

$selVehicle.addEventListener('change', () => {
    renderFuelOptions();
    updateEstimations();
});

$selFuel.addEventListener('change', updateEstimations);


// ============================================================
// LANGKAH 2: INTERAKSI KLIK — PILIH SOURCE & TARGET
// ============================================================
// Map click handler untuk mencari node terdekat jika area kosong diklik
map.on('click', (e) => {
    // Batasi maksimum 8 titik (agar TSP tidak terlalu berat / O(N!))
    if (waypoints.length >= 8) {
        alert("Maksimal 8 titik untuk simulasi TSP ini.");
        return;
    }
    
    // Pastikan graf sudah diload
    if (!nodesData || Object.keys(nodesData).length === 0) return;

    const clickedLatLng = e.latlng;
    let nearestNodeId = null;
    let minDistance = Infinity;

    for (const [nodeId, coords] of Object.entries(nodesData)) {
        // Optimasi: bounding box kasar (~2km)
        const latDiff = Math.abs(coords.lat - clickedLatLng.lat);
        const lngDiff = Math.abs(coords.lng - clickedLatLng.lng);
        if (latDiff > 0.02 || lngDiff > 0.02) continue;

        // Hitung jarak akurat dengan haversine
        const dist = clickedLatLng.distanceTo(L.latLng(coords.lat, coords.lng));
        if (dist < minDistance) {
            minDistance = dist;
            nearestNodeId = nodeId;
        }
    }

    if (nearestNodeId) {
        onNodeClicked(nearestNodeId, { 
            lat: clickedLatLng.lat, 
            lng: clickedLatLng.lng,
            actualNodeLat: nodesData[nearestNodeId].lat,
            actualNodeLng: nodesData[nearestNodeId].lng
        });
    }
});

function onNodeClicked(nodeId, coords) {
    // Cek apakah node sudah ada di waypoints
    if (waypoints.find(w => w.id === nodeId)) {
        return; // Jangan tambahkan titik yang sama dua kali
    }

    const index = waypoints.length;
    const isSource = index === 0;
    const color = isSource ? '#ef4444' : '#4edea3'; // Merah untuk awal, Hijau untuk tujuan
    const title = isSource ? 'KIRIM (A)' : `TUJUAN ${index}`;

    waypoints.push({ id: nodeId, lat: coords.lat, lng: coords.lng });

    // Buat marker
    const marker = L.circleMarker([coords.lat, coords.lng], {
        radius: 9, color: color, fillColor: color,
        fillOpacity: 0.9, weight: 3, opacity: 1
    }).addTo(map);
    
    marker.bindTooltip(title, { permanent: true, direction: 'top', offset: [0, -12], className: 'target-tooltip' });
    waypointMarkers.push(marker);

    renderWaypointsList();
    updateInstruction();
    updateSolveButton();
}

function renderWaypointsList() {
    if (waypoints.length === 0) {
        $emptyWaypointsText.classList.remove('hidden');
        $waypointsList.innerHTML = '';
        $waypointsList.appendChild($emptyWaypointsText);
        return;
    }
    
    $emptyWaypointsText.classList.add('hidden');
    $waypointsList.innerHTML = '';
    
    waypoints.forEach((wp, idx) => {
        const isSource = idx === 0;
        const colorClass = isSource ? 'bg-error/20 text-error border-error/30' : 'bg-tertiary/20 text-tertiary border-tertiary/30';
        const label = isSource ? 'Awal' : `Tujuan ${idx}`;
        
        const chip = document.createElement('div');
        chip.className = `px-2 py-1 rounded text-[11px] font-mono-data border ${colorClass} flex items-center gap-1`;
        chip.innerHTML = `<span>${label}</span> <span class="opacity-50 text-[9px]">(ID:${wp.id})</span>`;
        $waypointsList.appendChild(chip);
    });
}

function updateInstruction() {
    if (waypoints.length === 0) {
        $instructionText.innerHTML = `Klik pada peta untuk memilih titik <strong>Keberangkatan</strong>.`;
    } else if (waypoints.length === 1) {
        $instructionText.innerHTML = `<strong class="text-error">✓ Titik keberangkatan dipilih!</strong> Sekarang klik peta untuk memilih <strong class="text-tertiary">Titik Tujuan</strong>. Anda bisa memilih hingga 8 titik.`;
    } else {
        $instructionText.innerHTML = `<strong class="text-tertiary">✓ ${waypoints.length} titik dipilih!</strong> Tekan <strong class="text-on-surface">Cari Rute Optimal (TSP)</strong> atau tambah titik lagi.`;
    }
}

function updateSolveButton() {
    $btnSolve.disabled = waypoints.length < 2;
}


// ============================================================
// LANGKAH 3: SOLVE — JALANKAN KEDUA ALGORITMA
// ============================================================
$btnSolve.addEventListener('click', async () => {
    if (waypoints.length < 2) return;

    // UI: loading state
    $spinnerSolve.classList.remove('hidden');
    $iconSolve.classList.add('hidden');
    $btnSolveText.textContent = 'Menghitung...';
    $btnSolve.disabled = true;

    try {
        const res = await fetch('/api/solve', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                waypoints: waypoints.map(w => parseInt(w.id))
            })
        });
        const data = await res.json();

        // Hapus rute sebelumnya
        if (dijkstraLine) {
            if (dijkstraLine._glowLine) map.removeLayer(dijkstraLine._glowLine);
            map.removeLayer(dijkstraLine);
        }
        if (fwLine) map.removeLayer(fwLine);

        // --- Gambar Rute Dijkstra (garis utama) ---
        const dijCoords = data.dijkstra.path_coords;
        if (dijCoords && dijCoords.length > 1) {
            const latlngs = dijCoords.map(c => [c.lat, c.lng]);

            // Garis bayangan (glow effect)
            const glowLine = L.polyline(latlngs, {
                color: '#0ea5e9', weight: 10, opacity: 0.2 // Sky blue glow
            }).addTo(map);

            // Garis utama (Dijkstra) -> Biru Terang (Solid)
            dijkstraLine = L.polyline(latlngs, {
                color: '#0ea5e9', weight: 6, opacity: 0.9,
                lineCap: 'round', lineJoin: 'round'
            }).addTo(map);

            // Simpan glow line agar bisa dihapus nanti
            dijkstraLine._glowLine = glowLine;

            // Zoom ke rute
            map.fitBounds(dijkstraLine.getBounds(), { padding: [60, 60] });
        }

        // --- Gambar Rute Floyd-Warshall (garis overlay, dashed) ---
        if (data.floyd_warshall?.ready && data.floyd_warshall.path_coords) {
            const fwCoords = data.floyd_warshall.path_coords;
            if (fwCoords.length > 1) {
                const latlngs = fwCoords.map(c => [c.lat, c.lng]);
                // Garis kuning putus-putus tebal untuk FW
                fwLine = L.polyline(latlngs, {
                    color: '#f59e0b', weight: 5, opacity: 1, // Amber/Orange solid
                    dashArray: '12 12', lineCap: 'square'
                }).addTo(map);
            }
        }

        // --- Update Stats Panel ---
        displayResults(data);

    } catch (err) {
        console.error('[SOLVE] Error:', err);
        alert('Gagal menghitung rute. Cek konsol untuk detail.');
    } finally {
        // Reset button
        $spinnerSolve.classList.add('hidden');
        $iconSolve.classList.remove('hidden');
        $btnSolveText.textContent = 'Cari Rute Optimal (TSP)';
        $btnSolve.disabled = false;
    }
});


// ============================================================
// LANGKAH 4: TAMPILKAN HASIL PERBANDINGAN
// ============================================================
function displayResults(data) {
    // Show results panel with animation
    $resultsPanel.classList.add('visible');

    const dij = data.dijkstra;
    const fw = data.floyd_warshall;

    // Simpan jarak dan waktu untuk reaktivitas kalkulator bensin
    if (dij.cost_meters != null && dij.cost_meters !== "Unreachable") {
        lastDistanceMeters = dij.cost_meters;
        lastTimeMinutes = dij.est_time_minutes;
        lastFerryCrossings = dij.ferry_crossings || 0;
    } else {
        lastDistanceMeters = null;
        lastTimeMinutes = null;
        lastFerryCrossings = 0;
        $statTimeMinutes.textContent = '—';


        $statTotalCost.textContent = '—';
    }
    updateEstimations();

    // Dijkstra stats
    if (dij.cost_meters != null) {
        $statDijCost.textContent = formatDistance(dij.cost_meters);
        $statDijTime.textContent = `${dij.time_ms} ms (query)`;
    } else {
        $statDijCost.textContent = 'Unreachable';
        $statDijCost.classList.add('text-error');
        $statDijTime.textContent = '—';
    }

    // Floyd-Warshall stats
    if (fw.ready) {
        if (fw.cost_meters != null) {
            $statFWCost.textContent = formatDistance(fw.cost_meters);
            if (fw.subgraph_mode) {
                $statFWTime.textContent = `${fw.time_ms} ms (O(V³) on ${fw.subgraph_size} nodes)`;
            } else {
                $statFWTime.textContent = `${fw.time_ms} ms (lookup) • Pre: ${(fw.precompute_time_ms / 1000).toFixed(1)}s`;
            }
        } else {
            $statFWCost.textContent = 'Unreachable';
            $statFWCost.classList.add('text-error');
            $statFWTime.textContent = '—';
        }
    } else {
        $statFWCost.textContent = 'Computing...';
        $statFWCost.classList.add('text-amber');
        $statFWTime.textContent = `Progress: ${fw.progress_pct || 0}%`;
    }

    // Consistency check
    if (data.identical === true) {
        $consistencyIcon.textContent = 'check_circle';
        $consistencyIcon.className = 'material-symbols-outlined text-[20px] text-tertiary icon-fill';
        if (fw.subgraph_mode) {
            $consistencyLabel.textContent = 'IDENTIK ✓ (Subgraph)';
            $consistencyDetail.textContent = `FW dijalankan on-demand pada ${fw.subgraph_size} node lokal. Hasil sama persis.`;
        } else {
            $consistencyLabel.textContent = 'IDENTIK ✓';
            $consistencyDetail.textContent = 'Kedua algoritma menghasilkan jarak yang sama persis.';
        }
        $consistencyLabel.className = 'font-label-md text-sm text-tertiary';
        $consistencyCard.className = 'bg-tertiary/10 border border-tertiary/30 rounded-lg p-3 flex items-center justify-between';
    } else if (data.identical === false) {
        $consistencyIcon.textContent = 'error';
        $consistencyIcon.className = 'material-symbols-outlined text-[20px] text-error icon-fill';
        $consistencyLabel.textContent = 'BERBEDA ✗';
        $consistencyLabel.className = 'font-label-md text-sm text-error';
        $consistencyDetail.textContent = 'Peringatan: hasil kedua algoritma tidak cocok!';
        $consistencyCard.className = 'bg-error/10 border border-error/30 rounded-lg p-3 flex items-center justify-between';
    } else {
        $consistencyIcon.textContent = 'hourglass_top';
        $consistencyIcon.className = 'material-symbols-outlined text-[20px] text-amber';
        $consistencyLabel.textContent = 'MENUNGGU FW';
        $consistencyLabel.className = 'font-label-md text-sm text-amber';
        $consistencyDetail.textContent = 'Floyd-Warshall masih pre-computing. Coba lagi nanti.';
        $consistencyCard.className = 'bg-amber/10 border border-amber/30 rounded-lg p-3 flex items-center justify-between';
    }

    // Path detail
    $statNodeCount.textContent = dij.node_count_in_path || '—';
    $statCoordCount.textContent = dij.path_coords?.length || '—';
}

function formatDistance(meters) {
    if (meters >= 1000) {
        return `${(meters / 1000).toFixed(2)} km`;
    }
    return `${meters.toFixed(1)} m`;
}


// ============================================================
// LANGKAH 5: CLEAR MAP
// ============================================================
$btnClearMap.addEventListener('click', () => {
    // Hapus semua marker waypoint
    waypointMarkers.forEach(m => map.removeLayer(m));
    waypointMarkers = [];
    waypoints = [];

    // Hapus garis rute
    if (dijkstraLine) {
        if (dijkstraLine._glowLine) map.removeLayer(dijkstraLine._glowLine);
        map.removeLayer(dijkstraLine);
    }
    if (fwLine) map.removeLayer(fwLine);
    dijkstraLine = null;
    fwLine = null;

    // Reset UI
    renderWaypointsList();
    updateSolveButton();
    $resultsPanel.classList.remove('visible');
    updateInstruction();

    // Reset stats
    $statDijCost.textContent = '—';
    $statDijTime.textContent = '—';
    $statFWCost.textContent = '—';
    $statFWTime.textContent = '—';
    $statDijCost.className = 'font-mono-data text-xl text-tertiary';
    $statFWCost.className = 'font-mono-data text-xl text-primary';

    // Reset kalkulator bensin & jarak
    lastDistanceMeters = null;
    lastTimeMinutes = null;
    $statTimeMinutes.textContent = '—';

});


// ============================================================
// LANGKAH 6: POLLING STATUS FLOYD-WARSHALL
// ============================================================
async function pollFWStatus() {
    try {
        const res = await fetch('/api/fw-status');
        const data = await res.json();

        if (data.too_large) {
            $fwStatusIcon.textContent = 'layers';
            $fwStatusIcon.className = 'material-symbols-outlined text-tertiary text-[20px] icon-fill';
            $fwStatusLabel.textContent = `Floyd-Warshall: Mode Subgraph Lokal (${data.node_count} nodes terlalu besar)`;
            $fwStatusLabel.className = 'font-label-md text-tertiary text-xs uppercase tracking-wide';
            $fwProgressBar.style.width = '100%';
            $fwProgressBar.className = 'h-full bg-tertiary rounded-full transition-all duration-500';
            $fwProgressText.textContent = 'Standby';
            $fwProgressText.className = 'font-mono-data text-tertiary text-xs';
            $fwStatusCard.className = 'bg-tertiary/10 border border-tertiary/30 rounded-lg p-3 flex items-center gap-3 transition-all duration-500';

            // Hentikan polling
            clearInterval(fwPollTimer);
            fwPollTimer = null;
        } else if (data.ready) {
            // FW selesai!
            $fwStatusIcon.textContent = 'check_circle';
            $fwStatusIcon.className = 'material-symbols-outlined text-tertiary text-[20px] icon-fill';
            $fwStatusLabel.textContent = `Floyd-Warshall Siap! (${(data.compute_time_ms / 1000).toFixed(1)}s untuk ${data.node_count} nodes)`;
            $fwStatusLabel.className = 'font-label-md text-tertiary text-xs uppercase tracking-wide';
            $fwProgressBar.style.width = '100%';
            $fwProgressBar.className = 'h-full bg-tertiary rounded-full transition-all duration-500';
            $fwProgressText.textContent = '100%';
            $fwProgressText.className = 'font-mono-data text-tertiary text-xs';
            $fwStatusCard.className = 'bg-tertiary/10 border border-tertiary/30 rounded-lg p-3 flex items-center gap-3 transition-all duration-500';

            // Hentikan polling
            clearInterval(fwPollTimer);
            fwPollTimer = null;
        } else {
            // Update progress
            $fwProgressBar.style.width = `${data.progress_pct}%`;
            $fwProgressText.textContent = `${data.progress_pct}%`;
        }
    } catch (err) {
        console.error('[FW Status] Error:', err);
    }
}

// Mulai polling setiap 2 detik
fwPollTimer = setInterval(pollFWStatus, 2000);
// Cek pertama kali segera
pollFWStatus();
loadFuelPrices();


// ============================================================
// LANGKAH 7: MUAT GRAF SAAT HALAMAN SIAP
// ============================================================
loadGraph();


// ============================================================
// TOOLTIP STYLE (injeksi CSS tambahan untuk Leaflet tooltip)
// ============================================================
const tooltipStyle = document.createElement('style');
tooltipStyle.textContent = `
    .node-tooltip {
        background: rgba(32, 31, 35, 0.95) !important;
        border: 1px solid #47464f !important;
        color: #e5e1e6 !important;
        font-family: 'Geist', monospace !important;
        font-size: 11px !important;
        padding: 3px 8px !important;
        border-radius: 4px !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.4) !important;
    }
    .node-tooltip::before {
        border-top-color: #47464f !important;
    }
    .source-tooltip {
        background: rgba(239, 68, 68, 0.9) !important;
        border: 1px solid #ef4444 !important;
        color: white !important;
        font-family: 'Geist', monospace !important;
        font-size: 10px !important;
        font-weight: 600 !important;
        padding: 2px 8px !important;
        border-radius: 4px !important;
        letter-spacing: 0.05em;
    }
    .source-tooltip::before {
        border-top-color: rgba(239, 68, 68, 0.9) !important;
    }
    .target-tooltip {
        background: rgba(78, 222, 163, 0.9) !important;
        border: 1px solid #4edea3 !important;
        color: #002819 !important;
        font-family: 'Geist', monospace !important;
        font-size: 10px !important;
        font-weight: 600 !important;
        padding: 2px 8px !important;
        border-radius: 4px !important;
        letter-spacing: 0.05em;
    }
    .target-tooltip::before {
        border-top-color: rgba(78, 222, 163, 0.9) !important;
    }
    .leaflet-tooltip-top::before {
        margin-left: -6px;
    }
`;
document.head.appendChild(tooltipStyle);