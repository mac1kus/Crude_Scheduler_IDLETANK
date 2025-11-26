let currentResults = null;

const ALERT_TYPES = {
    SUCCESS: 'success',
    WARNING: 'warning',
    DANGER: 'danger',
    INFO: 'info'
};

const TANK_STATUS_COLORS = {
    READY: '#28a745',
    FEEDING: '#28a745',
    SETTLING: '#ffc107',
    LAB_TESTING: '#ffd700',
    FILLING: '#007bff',
    FILLED: '#007bff',
    EMPTY: '#6c757d'
};

const API_ENDPOINTS = {
    SIMULATE: '/api/simulate',
    BUFFER_ANALYSIS: '/api/buffer_analysis',
    CARGO_OPTIMIZATION: '/api/cargo_optimization',
    SAVE_INPUTS: '/api/save_inputs',
    LOAD_INPUTS: '/api/load_inputs',
    EXPORT_DATA: '/api/export_data',
    EXPORT_TANK_STATUS: '/api/export_tank_status'
};

const Utils = {
    formatNumber: (num) => {
        if (num === null || num === undefined) return '0';
        return Math.round(num).toLocaleString();
    },

    showLoading: (show = true) => {
        const loading = document.getElementById('loading');
        if (loading) loading.style.display = show ? 'block' : 'none';
        
        document.querySelectorAll('.btn-group button').forEach(btn => {
            const onclickText = btn.getAttribute('onclick');
            if (onclickText && (
                onclickText.startsWith('scrollTo') ||
                onclickText.startsWith('autoSaveInputs') || 
                onclickText.startsWith('autoLoadInputs')
            )) {
            } else {
                btn.disabled = show;
            }
        });
    },

    showResults: () => {
        const results = document.getElementById('results');
        if (results) results.style.display = 'block';
    },

    getTankLevelColor: (volume, deadBottom) => {
        if (volume <= deadBottom) return '#dc3545';
        if (volume < deadBottom * 3) return '#ffc107';
        return '#28a745';
    },

    getStatusColor: (status) => TANK_STATUS_COLORS[status] || '#000',

    createAlert: (type, message) =>
        `<div class="alert alert-${type}">${message}</div>`,

    createMetricCard: (title, value, label, extraContent = '') => `
        <div class="metric-card">
            <h4>${title}</h4>
            <div class="metric-value">${value}</div>
            <div class="metric-label">${label}</div>
            ${extraContent}
        </div>
    `
};

function scrollToTop() {
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

function scrollToBottom() {
    window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' });
}

function scrollToSimulation() {
    const element = document.querySelector('.btn-group');
    if (element) {
        element.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
}

function scrollToCargoReport() {
    const element = document.getElementById('cargoReportContainer'); 
    const fallbackElement = document.querySelector('.btn-group');

    if (element) {
        element.scrollIntoView({ behavior: 'smooth', block: 'center' });
    } else if (fallbackElement) {
        fallbackElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
}

function autoCalculatePumpingDays() {
    console.log("Pumping parameters updated and saved.");
    autoSaveInputs();
}

function autoCalculateLeadTime() {
    console.log("Lead time parameters updated and saved.");
    autoSaveInputs();
}

function addCrudeRow() {
    const tableBody = document.getElementById('crudeMixTableBody');
    const newRow = document.createElement('tr');
    newRow.className = 'crude-mix-row';
    newRow.innerHTML = `
        <td style="padding: 5px;"><input type="text" class="crude-name-input" value="" placeholder="Enter crude name" style="width: 90%;" onchange="updateCrudeMix()"></td>
        <td style="padding: 5px; text-align: center;"><input type="number" class="crude-percentage-input" value="0" min="0" max="100" step="0.1" style="width: 80px;" onchange="updateCrudeMix()"></td>
        <td style="padding: 5px; text-align: center;"><span class="crude-volume-display">0</span></td>
        <td style="padding: 5px; text-align: center;"><button class="remove-crude-btn" onclick="removeCrudeRow(this)" style="background-color: #dc3545; color: white; border: none; padding: 3px 8px; cursor: pointer;">✕</button></td>
    `;
    tableBody.appendChild(newRow);
    updateCrudeMix(); 
}

function removeCrudeRow(button) {
    button.closest('tr').remove();
    updateCrudeMix(); 
}

function updateCrudeMix() {
    const processingRate = parseFloat(document.getElementById('processingRate').value) || 0;
    const rows = document.querySelectorAll('.crude-mix-row');
    let totalPercentage = 0;

    rows.forEach(row => {
        const percentageInput = row.querySelector('.crude-percentage-input');
        const percentage = parseFloat(percentageInput.value) || 0;
        totalPercentage += percentage;

        const volumeDisplay = row.querySelector('.crude-volume-display');
        const dailyVolume = (processingRate * percentage) / 100;
        volumeDisplay.textContent = dailyVolume.toLocaleString(undefined, { maximumFractionDigits: 0 });
    });

    document.getElementById('totalPercentage').textContent = totalPercentage.toFixed(1);
    document.getElementById('totalVolume').textContent = ((processingRate * totalPercentage) / 100).toLocaleString(undefined, { maximumFractionDigits: 0 });

    const warningDiv = document.getElementById('crudeMixWarning');
    const warningPercentageSpan = document.getElementById('warningPercentage');
    if (Math.abs(totalPercentage - 100) > 0.01) {
        warningPercentageSpan.textContent = totalPercentage.toFixed(1);
        warningDiv.style.display = 'block';
    } else {
        warningDiv.style.display = 'none';
    }
    autoSaveInputs(); 
}

function resetCrudeMix() {
    const tableBody = document.getElementById('crudeMixTableBody');
    tableBody.innerHTML = ''; 
    tableBody.innerHTML = `
        <tr class="crude-mix-row">
            <td style="padding: 5px;"><input type="text" class="crude-name-input" value="Bonny Light" placeholder="Enter crude name" style="width: 90%;" onchange="updateCrudeMix()"></td>
            <td style="padding: 5px; text-align: center;"><input type="number" class="crude-percentage-input" value="50" min="0" max="100" step="0.1" style="width: 80px;" onchange="updateCrudeMix()"></td>
            <td style="padding: 5px; text-align: center;"><span class="crude-volume-display">20,000</span></td>
            <td style="padding: 5px; text-align: center;"><button class="remove-crude-btn" onclick="removeCrudeRow(this)" style="background-color: #dc3545; color: white; border: none; padding: 3px 8px; cursor: pointer;">✕</button></td>
        </tr>
        <tr class="crude-mix-row">
            <td style="padding: 5px;"><input type="text" class="crude-name-input" value="Forcados" placeholder="Enter crude name" style="width: 90%;" onchange="updateCrudeMix()"></td>
            <td style="padding: 5px; text-align: center;"><input type="number" class="crude-percentage-input" value="30" min="0" max="100" step="0.1" style="width: 80px;" onchange="updateCrudeMix()"></td>
            <td style="padding: 5px; text-align: center;"><span class="crude-volume-display">15,000</span></td>
            <td style="padding: 5px; text-align: center;"><button class="remove-crude-btn" onclick="removeCrudeRow(this)" style="background-color: #dc3545; color: white; border: none; padding: 3px 8px; cursor: pointer;">✕</button></td>
        </tr>
        <tr class="crude-mix-row">
            <td style="padding: 5px;"><input type="text" class="crude-name-input" value="Quaiboe" placeholder="Enter crude name" style="width: 90%;" onchange="updateCrudeMix()"></td>
            <td style="padding: 5px; text-align: center;"><input type="number" class="crude-percentage-input" value="10" min="0" max="100" step="0.1" style="width: 80px;" onchange="updateCrudeMix()"></td>
            <td style="padding: 5px; text-align: center;"><span class="crude-volume-display">15,000</span></td>
            <td style="padding: 5px; text-align: center;"><button class="remove-crude-btn" onclick="removeCrudeRow(this)" style="background-color: #dc3545; color: white; border: none; padding: 3px 8px; cursor: pointer;">✕</button></td>
        </tr>
        <tr class="crude-mix-row">
            <td style="padding: 5px;"><input type="text" class="crude-name-input" value="Erha" placeholder="Enter crude name" style="width: 90%;" onchange="updateCrudeMix()"></td>
            <td style="padding: 5px; text-align: center;"><input type="number" class="crude-percentage-input" value="10" min="0" max="100" step="0.1" style="width: 80px;" onchange="updateCrudeMix()"></td>
            <td style="padding: 5px; text-align: center;"><span class="crude-volume-display">0</span></td>
            <td style="padding: 5px; text-align: center;"><button class="remove-crude-btn" onclick="removeCrudeRow(this)" style="background-color: #dc3545; color: white; border: none; padding: 3px 8px; cursor: pointer;">✕</button></td>
        </tr>
    `;
    updateCrudeMix(); 
}

function createFilledTankBoxHTML(sequentialId, tankCapacity, customName = `Tank ${sequentialId}`, customLevel = null) {
    
    const valueToShow = (customLevel !== null && customLevel !== undefined) ? customLevel : tankCapacity;

    return `
        <div class="tank-box" data-sequential-id="${sequentialId}">
            <h4>${customName}</h4>
            <div class="tank-input-row">
                <label>Name:</label>
                <input type="text" id="tank${sequentialId}Name" value="${customName}" onchange="autoSaveInputs()">
            </div>
            <div class="tank-input-row">
                <label>Current Level:</label>
                <input type="number" id="tank${sequentialId}Level" value="${valueToShow}" class="tank-level-input" onchange="autoSaveInputs()">
                <span>bbl</span>
            </div>
            <input type="hidden" id="deadBottom${sequentialId}" value="0">
            <input type="hidden" id="buffer${sequentialId}" value="0">
        </div>
    `;
}

function createEmptyTankBoxHTML(sequentialId, tankCapacity, defaultDeadBottom, defaultBuffer, customName = `Tank ${sequentialId}`) {
    const operationalFloor = parseFloat(defaultDeadBottom) + (parseFloat(defaultBuffer) / 2);
    return `
        <div class="tank-box" data-sequential-id="${sequentialId}">
            <h4>${customName}</h4>
            <div class="tank-input-row">
                <label>Name:</label>
                <input type="text" id="tank${sequentialId}Name" value="${customName}" onchange="autoSaveInputs()">
            </div>
            <div class="tank-input-row">
                <label>Current Level:</label>
                <input type="number" id="tank${sequentialId}Level" value="${operationalFloor.toFixed(0)}" class="tank-level-input" onchange="autoSaveInputs()">
                <span>bbl (Floor)</span>
            </div>
            <div class="input-row" style="font-size: 0.85em; color: #666;">
                <label>Dead Bottom:</label>
                <input type="number" id="deadBottom${sequentialId}" value="${defaultDeadBottom}" readonly style="background-color: #eee; width: 80px;">
                <span>bbl</span>
            </div>
            <div class="input-row" style="font-size: 0.85em; color: #666;">
                <label>Buffer:</label>
                <input type="number" id="buffer${sequentialId}" value="${defaultBuffer}" readonly style="background-color: #eee; width: 80px;">
                <span>bbl</span>
            </div>
        </div>
    `;
}

function createIdleTankBoxHTML(sequentialId, tankCapacity, defaultDeadBottom, defaultBuffer, customName = `Tank ${sequentialId}`) {
    const tankId = `idle-tank-${sequentialId}`;
    return `
        <div class="uncorrected-tank-box" id="${tankId}" data-sequential-id="${sequentialId}">
            <h4>IDLE - ${customName}</h4>
            <div class="tank-input-row">
                <label>Name:</label>
                <input type="text" id="tank${sequentialId}Name" value="${customName}" onchange="autoSaveInputs()">
            </div>
            <p style="font-size: 0.85em; margin: 0 0 10px 0; color: #666;">
                Using Globals: Cap=${Utils.formatNumber(tankCapacity)}, DB=${Utils.formatNumber(defaultDeadBottom)}, Buf=${Utils.formatNumber(defaultBuffer)}
            </p>

            <input type="hidden" id="tank${sequentialId}Level" value="0"> 
            <input type="hidden" id="deadBottom${sequentialId}" value="${defaultDeadBottom}">
            <input type="hidden" id="buffer${sequentialId}" value="${defaultBuffer}">

            <table class="crude-table" id="crude-table-${sequentialId}">
                <thead>
                    <tr>
                        <th style="width: 50%;">Initial Crude Name</th>
                        <th style="width: 40%;">Volume (bbl)</th>
                        <th style="width: 10%;"></th>
                    </tr>
                </thead>
                <tbody id="crude-tbody-${sequentialId}">
                </tbody>
            </table>
            <button type="button" onclick="addIdleCrudeRow(${sequentialId})" style="font-size: 0.8em; margin-top: 5px;">+ Add Crude</button>

            <div class="uncorrected-summary" id="summary-${sequentialId}">
                <p>Operational Floor: <strong>...</strong></p>
                <p>Initial Pumpable: <strong>...</strong></p>
                <p>Total Usable Space: <strong>...</strong></p>
                <p><strong>Vacant Space to Fill:</strong> <strong style="color: #28a745;">... bbl</strong></p>
            </div>
        </div>
    `;
}

function addIdleCrudeRow(sequentialId, crudeName = "", crudeVolume = 0) {
    const tableBody = document.getElementById(`crude-tbody-${sequentialId}`);
    if (!tableBody) return;

    const newRow = document.createElement('tr');
    newRow.innerHTML = `
        <td><input type="text" class="idle-crude-name" value="${crudeName}" placeholder="e.g., Crude E" onchange="updateIdleTankSummary(${sequentialId}); autoSaveInputs();"></td>
        <td><input type="number" class="idle-crude-volume" value="${crudeVolume}" min="0" step="1000" oninput="updateIdleTankSummary(${sequentialId}); autoSaveInputs();"></td>
        <td><button type="button" onclick="this.closest('tr').remove(); updateIdleTankSummary(${sequentialId}); autoSaveInputs();">✕</button></td>
    `;
    tableBody.appendChild(newRow);

    newRow.querySelector('.idle-crude-volume').addEventListener('input', () => {
        updateIdleTankSummary(sequentialId);
        autoSaveInputs();
    });
}

function updateIdleTankSummary(sequentialId) {
    const tankBox = document.getElementById(`idle-tank-${sequentialId}`);
    if (!tankBox) return;

    const tankCapacity = parseFloat(document.getElementById('tankCapacity').value) || 0;
    const deadBottom = parseFloat(document.getElementById('deadBottom' + sequentialId).value) || 0;
    const buffer = parseFloat(document.getElementById('buffer' + sequentialId).value) || 0;

    const operationalFloor = deadBottom + (buffer / 2);
    const totalUsableSpace = tankCapacity - operationalFloor;

    let initialPumpable = 0;
    const volumeInputs = tankBox.querySelectorAll('.idle-crude-volume');
    volumeInputs.forEach(input => {
        initialPumpable += parseFloat(input.value) || 0;
    });

    const vacantSpace = totalUsableSpace - initialPumpable;

    document.getElementById(`tank${sequentialId}Level`).value = operationalFloor + initialPumpable;

    const summaryBox = document.getElementById(`summary-${sequentialId}`);
    if (summaryBox) {
        summaryBox.innerHTML = `
            <p>Operational Floor: <strong>${Utils.formatNumber(operationalFloor)} bbl</strong></p>
            <p>Initial Pumpable: <strong>${Utils.formatNumber(initialPumpable)} bbl</strong></p>
            <p>Total Usable Space: <strong>${Utils.formatNumber(totalUsableSpace)} bbl</strong></p>
            <p><strong>Vacant Space to Fill:</strong> <strong style="color: ${vacantSpace < 0 ? '#dc3545' : '#28a745'};">${Utils.formatNumber(vacantSpace)} bbl</strong></p>
        `;
    }
}

function regenerateTankBoxes(tankCustomNames = {}, tankCustomLevels = {}, savedIdleData = {}) {
    const filledGrid = document.getElementById('filledTanksGrid');
    const emptyGrid = document.getElementById('emptyTanksGrid');
    const idleGrid = document.getElementById('idleTanksGrid') || document.getElementById('uncorrectedTanksGrid');

    filledGrid.innerHTML = '';
    emptyGrid.innerHTML = '';
    idleGrid.innerHTML = '';

    const numTanks = parseInt(document.getElementById('numTanks').value) || 0;
    const numFilled = parseInt(document.getElementById('numFilledTanks').value) || 0;
    const numEmpty = parseInt(document.getElementById('numEmptyTanks').value) || 0;

    const specificIdleInput = document.getElementById('specificIdleTanks');
    
    const specificIdleList = (specificIdleInput?.value || "")
        .split(',')
        .map(s => parseInt(s.trim()))
        .filter(n => !isNaN(n) && n >= 1);

    const tankCapacity = document.getElementById('tankCapacity').value;
    const defaultDeadBottom = document.getElementById('deadBottom1').value;
    const defaultBuffer = document.getElementById('bufferVolume').value;
    
    const assignmentMap = new Map();
    
    // 1. Create a list of all tanks from 1 to numTanks
    const availableTanks = [];
    for (let i = 1; i <= numTanks; i++) { 
        availableTanks.push(i);
    }
    
    // 2. Assign FILLED tanks from the list
    const tanksRemainingAfterFilled = [];
    let filledCount = 0;
    for (const tankId of availableTanks) {
        if (filledCount < numFilled) {
            assignmentMap.set(tankId, 'FILLED');
            filledCount++;
        } else {
            tanksRemainingAfterFilled.push(tankId);
        }
    }

    // 3. Assign EMPTY tanks from the remainder
    const defaultIdleList = [];
    let emptyCount = 0;
    for (const tankId of tanksRemainingAfterFilled) {
        if (emptyCount < numEmpty) {
            assignmentMap.set(tankId, 'EMPTY');
            emptyCount++;
        } else {
            // Whatever is left over forms the default IDLE list (e.g., [14, 15])
            defaultIdleList.push(tankId);
        }
    }

    // 4. Create the final IDLE list by overriding defaults with specific IDs
    // e.g., specific=[17], default=[14, 15] -> final=[17, 15]
    // e.g., specific=[17, 18], default=[14, 15] -> final=[17, 18]
    const finalIdleList = specificIdleList.concat(defaultIdleList.slice(specificIdleList.length));

    // 5. Assign IDLE tanks to the map using the final list
    for (const tankId of finalIdleList) {
        assignmentMap.set(tankId, 'IDLE');
    }
    
    // 6. Determine the highest tank ID we need to render
    const maxIdFromIdle = finalIdleList.length > 0 ? Math.max(...finalIdleList) : 0;
    const maxTankToProcess = Math.max(numTanks, maxIdFromIdle);

    // 7. Loop up to the highest ID and render boxes based on the map
    for (let sequentialId = 1; sequentialId <= maxTankToProcess; sequentialId++) {
        const category = assignmentMap.get(sequentialId);
        const customName = tankCustomNames[sequentialId] || `Tank ${sequentialId}`;
        const customLevel = tankCustomLevels[sequentialId]; 

        if (category === 'FILLED') {
            filledGrid.innerHTML += createFilledTankBoxHTML(sequentialId, tankCapacity, customName, customLevel);
        } else if (category === 'EMPTY') {
            emptyGrid.innerHTML += createEmptyTankBoxHTML(sequentialId, tankCapacity, defaultDeadBottom, defaultBuffer, customName);
        } else if (category === 'IDLE') {
            // This will now correctly create boxes for 17, 18, etc.
            idleGrid.innerHTML += createIdleTankBoxHTML(sequentialId, tankCapacity, defaultDeadBottom, defaultBuffer, customName); 
            
            const idleData = savedIdleData[sequentialId];
            const tableBody = document.getElementById(`crude-tbody-${sequentialId}`);

            if (tableBody && idleData && idleData.length > 0) {
                idleData.forEach(crude => {
                    addIdleCrudeRow(sequentialId, crude.name, crude.volume);
                });
            } else if (tableBody && tableBody.rows.length === 0) {
                 addIdleCrudeRow(sequentialId, "Initial Crude", 0);
            }
            
            updateIdleTankSummary(sequentialId);
        }
        // If category is undefined (like for 14, 15 in your example), nothing is rendered, which is correct.
    }
}

function updateTankCategories(savedCustomNames = {}, savedCustomLevels = {}) {
    const numTanksInput = document.getElementById('numTanks');
    const numFilledInput = document.getElementById('numFilledTanks');
    const numEmptyInput = document.getElementById('numEmptyTanks');
    const numIdleInput = document.getElementById('numIdleTanks'); 
    const specificIdleInput = document.getElementById('specificIdleTanks'); 
    const tankCountDisplay = document.getElementById('tankCountDisplay');
    const idleErrorDiv = document.getElementById('idleValidationMessage'); 

    let numTanks = parseInt(numTanksInput.value) || 0;
    let numFilled = parseInt(numFilledInput.value) || 0;
    let numEmpty = parseInt(numEmptyInput.value) || 0;

    const tankCustomNames = {};
    const tankCustomLevels = {}; 
    const currentIdleData = {}; 
    
    const specificIdleList = (specificIdleInput.value || "")
        .split(',')
        .map(s => parseInt(s.trim()))
        .filter(n => !isNaN(n) && n >= 1);
    
    // --- FIX: Find the highest tank ID from *either* numTanks or the specific list ---
    const maxIdleId = Math.max(0, ...specificIdleList);
    let maxId = Math.max(numTanks, maxIdleId);
    // --- END FIX ---
    
    for (let i = 1; i <= maxId; i++) {
        const savedName = savedCustomNames[i];
        const uiNameEl = document.getElementById(`tank${i}Name`);
        
        const savedLevel = savedCustomLevels[i]; 
        const uiLevelEl = document.getElementById(`tank${i}Level`); 
        
        if (uiNameEl) {
            tankCustomNames[i] = uiNameEl.value || savedName || `Tank ${i}`;
        } else if (savedName) {
            tankCustomNames[i] = savedName;
        }

        if (uiLevelEl) {
            tankCustomLevels[i] = uiLevelEl.value !== undefined ? uiLevelEl.value : savedLevel;
        } else if (savedLevel !== undefined) {
            tankCustomLevels[i] = savedLevel;
        }

        const idleTankBox = document.getElementById(`idle-tank-${i}`);
        if (idleTankBox) {
            const crudeRows = idleTankBox.querySelectorAll(`#crude-tbody-${i} tr`);
            const initialCrudes = [];
            crudeRows.forEach(row => {
                const nameInput = row.querySelector('.idle-crude-name');
                const volumeInput = row.querySelector('.idle-crude-volume');
                if (nameInput && volumeInput) {
                    initialCrudes.push({
                        name: nameInput.value,
                        volume: parseFloat(volumeInput.value) || 0
                    });
                }
            });
            currentIdleData[i] = initialCrudes;
        }
    }

   

    const calculatedIdleCount = Math.max(0, numTanks - numFilled - numEmpty);
    numIdleInput.value = calculatedIdleCount; 
    
    const numSpecificIdle = new Set(specificIdleList).size;

    let isIdleValid = true;
    
    const invalidIdleTanks = specificIdleList.filter(id => id > numTanks);
    
    /* --- VALIDATION BLOCK REMOVED ---
    if (invalidIdleTanks.length > 0) {
        isIdleValid = false;
        if (idleErrorDiv) idleErrorDiv.textContent = `Error: Idle tank(s) ${invalidIdleTanks.join(', ')} are outside the "Number of Crude Tanks" (1-${numTanks}).`;
        if (idleErrorDiv) idleErrorDiv.style.display = 'block';
        specificIdleInput.disabled = false;
    }
    */
    
    if (calculatedIdleCount < 0) { 
        isIdleValid = false;
        if (idleErrorDiv) idleErrorDiv.textContent = `Error: Tanks over-allocated. (Filled + Empty > Total)`;
        if (idleErrorDiv) idleErrorDiv.style.display = 'block';
        specificIdleInput.disabled = true; 
    }
    else if (calculatedIdleCount === 0 && numSpecificIdle > 0) {
        isIdleValid = false;
        if (idleErrorDiv) idleErrorDiv.textContent = 'IDLE count is 0. Cannot assign specific IDLE tanks.';
        if (idleErrorDiv) idleErrorDiv.style.display = 'block';
        specificIdleInput.disabled = true; 
        specificIdleInput.value = ''; 
    } else if (numSpecificIdle > calculatedIdleCount) {
        isIdleValid = false;
        if (idleErrorDiv) idleErrorDiv.textContent = `Error: ${numSpecificIdle} tanks assigned, but only ${calculatedIdleCount} IDLE slot(s) available.`;
        if (idleErrorDiv) idleErrorDiv.style.display = 'block';
        specificIdleInput.disabled = false; 
    } else {
        isIdleValid = true;
        if (idleErrorDiv) idleErrorDiv.style.display = 'none';
        specificIdleInput.disabled = (calculatedIdleCount === 0); 
    }

    if (numTanks < 1) { numTanks = 1; numTanksInput.value = 1; }
    if (numFilled < 0) { numFilled = 0; numFilledInput.value = 0; }
    if (numEmpty < 0) { numEmpty = 0; numEmptyInput.value = 0; }
    
    tankCountDisplay.textContent = `tanks (${numTanks} tanks total)`;
    
    regenerateTankBoxes(tankCustomNames, tankCustomLevels, currentIdleData);
    
    if (isIdleValid) {
        autoSaveInputs();
    }
}


function addOneTank() {
    const numTanksInput = document.getElementById('numTanks');
    let currentCount = parseInt(numTanksInput.value);
    numTanksInput.value = currentCount + 1;
    updateTankCategories();
}

function removeOneTank() {
    const numTanksInput = document.getElementById('numTanks');
    let currentCount = parseInt(numTanksInput.value);
    if (currentCount > 1) {
        numTanksInput.value = currentCount - 1;
        updateTankCategories();
    }
}

function getCurrentTankCount() {
    const count = parseInt(document.getElementById('numTanks').value);
    return !isNaN(count) && count >= 0 ? count : 0;
}

function updateTankCapacities() {
    const tankCapacity = document.getElementById('tankCapacity').value;
    
    const allTankBoxes = document.querySelectorAll('.tank-box, .uncorrected-tank-box');
    let maxId = 0;
    allTankBoxes.forEach(box => {
        const id = parseInt(box.dataset.sequentialId);
        if (id > maxId) maxId = id;
    });

    const defaultDeadBottom = document.getElementById('deadBottom1').value;
    const defaultBuffer = document.getElementById('bufferVolume').value;

    if (tankCapacity && parseFloat(tankCapacity) > 0) {
        for (let i = 1; i <= maxId; i++) {
            const tankLevelInput = document.getElementById(`tank${i}Level`);
            if (tankLevelInput) {
                tankLevelInput.setAttribute('max', tankCapacity);
            }

            const idleTankBox = document.getElementById(`idle-tank-${i}`);
            if (idleTankBox) {
                const headerP = idleTankBox.querySelector('p'); 
                if (headerP) {
                    const customName = document.getElementById(`tank${i}Name`)?.value || `Tank ${i}`;
                    headerP.innerHTML = `Using Globals: Cap=${Utils.formatNumber(tankCapacity)}, DB=${Utils.formatNumber(defaultDeadBottom)}, Buf=${Utils.formatNumber(defaultBuffer)}`;
                }
            }
        }
    }
}

function populateTankLevels() {
    const tankCapacity = document.getElementById('tankCapacity').value;
    const globalBuffer = document.getElementById('bufferVolume').value;
    const defaultDeadBottom = document.getElementById('deadBottom1').value;

    if (tankCapacity && parseFloat(tankCapacity) > 0) {
        const allTankBoxes = document.querySelectorAll('.tank-box, .uncorrected-tank-box');
        let maxId = 0;
        allTankBoxes.forEach(box => {
            const id = parseInt(box.dataset.sequentialId);
            if (id > maxId) maxId = id;
        });

        for (let i = 1; i <= maxId; i++) {
            const tankLevelInput = document.getElementById(`tank${i}Level`);
            const bufferInput = document.getElementById(`buffer${i}`);
            const deadBottomInput = document.getElementById(`deadBottom${i}`);
            const idleTankBox = document.getElementById(`idle-tank-${i}`);
            
            if (bufferInput) bufferInput.value = globalBuffer;

            const tankBox = document.getElementById(`tank${i}Name`)?.closest('div[data-sequential-id]');

            if (tankBox) {
                if (tankBox.closest('#filledTanksGrid')) {
                    if (tankLevelInput) {
                        tankLevelInput.value = tankCapacity; // <-- ADD THIS LINE
                    }
                } else if (tankBox.closest('#emptyTanksGrid')) {
               
                    if (tankLevelInput && deadBottomInput) {
                        const operationalFloor = parseFloat(deadBottomInput.value) + (parseFloat(globalBuffer) / 2);
                        tankLevelInput.value = operationalFloor.toFixed(0);
                    }
                } else if (tankBox.closest('#idleTanksGrid')) {
                    if (idleTankBox) {
                        const headerP = idleTankBox.querySelector('p'); 
                        if (headerP) {
                            const customName = document.getElementById(`tank${i}Name`)?.value || `Tank ${i}`;
                            headerP.innerHTML = `Using Globals: Cap=${Utils.formatNumber(tankCapacity)}, DB=${Utils.formatNumber(defaultDeadBottom)}, Buf=${Utils.formatNumber(globalBuffer)}`;
                        }
                        updateIdleTankSummary(i); 
                    }
                }
            }
        }
        console.log(`Global values applied. Idle tanks recalculated.`);
        validateInventoryRange();
    }
}

function toggleDepartureMode() {
    const mode = document.getElementById('departureMode').value;
    const manualSection = document.getElementById('manualArrivalSection');
    const solverSection = document.getElementById('solverDepartureSection');

    if (mode === 'manual') {
        manualSection.style.display = 'block';
        if (solverSection) solverSection.style.display = 'none';
    } else {
        manualSection.style.display = 'none';
        if (solverSection) solverSection.style.display = 'block';
    }
}

function applyDefaultDeadBottom() {
    const defaultValue = document.getElementById('deadBottom1').value;
    
    const allTankBoxes = document.querySelectorAll('.tank-box, .uncorrected-tank-box');
    let maxId = 0;
    allTankBoxes.forEach(box => {
        const id = parseInt(box.dataset.sequentialId);
        if (id > maxId) maxId = id;
    });

    for (let i = 1; i <= maxId; i++) {
        const deadBottomInput = document.getElementById(`deadBottom${i}`);
        if (deadBottomInput) {
            deadBottomInput.value = defaultValue;
        }

        const idleTankBox = document.getElementById(`idle-tank-${i}`);
        if (idleTankBox) {
            updateIdleTankSummary(i); 
        }
        
        const tankLevelInput = document.getElementById(`tank${i}Level`);
        const bufferInput = document.getElementById(`buffer${i}`);
        const tankBox = document.getElementById(`tank${i}Name`)?.closest('div[data-sequential-id]');
        
        if (tankBox && tankBox.closest('#emptyTanksGrid')) {
             if (tankLevelInput && bufferInput) {
                const operationalFloor = parseFloat(defaultValue) + (parseFloat(bufferInput.value) / 2);
                tankLevelInput.value = operationalFloor.toFixed(0);
             }
        }
    }
    
    populateTankLevels();
    autoSaveInputs();
}

function applyGlobalTankCapacity() {
    updateTankCapacities();
    populateTankLevels();
    autoSaveInputs(); 
}

function applyGlobalBufferVolume() {
    populateTankLevels();
    autoSaveInputs(); 
}

function collectCrudeMixData() {
    const crudeData = [];
    const rows = document.querySelectorAll('.crude-mix-row');
    
    rows.forEach(row => {
        const nameInput = row.querySelector('.crude-name-input');
        const percentageInput = row.querySelector('.crude-percentage-input');
        
        if (nameInput && percentageInput) {
            crudeData.push({
                name: nameInput.value || '',
                percentage: parseFloat(percentageInput.value) || 0
            });
        }
    });
    
    return crudeData;
}
function recreateCrudeMixTable(crudeMixData) {
    if (!crudeMixData || crudeMixData.length === 0) {
        return; 
    }

    const tableBody = document.getElementById('crudeMixTableBody');
    tableBody.innerHTML = ''; 

    crudeMixData.forEach(crude => {
        const newRow = document.createElement('tr');
        newRow.className = 'crude-mix-row';
        newRow.innerHTML = `
            <td style="padding: 5px;"><input type="text" class="crude-name-input" value="${crude.name}" placeholder="Enter crude name" style="width: 90%;" onchange="updateCrudeMix()"></td>
            <td style="padding: 5px; text-align: center;"><input type="number" class="crude-percentage-input" value="${crude.percentage}" min="0" max="100" step="0.1" style="width: 80px;" onchange="updateCrudeMix()"></td>
            <td style="padding: 5px; text-align: center;"><span class="crude-volume-display">0</span></td>
            <td style="padding: 5px; text-align: center;"><button class="remove-crude-btn" onclick="removeCrudeRow(this)" style="background-color: #dc3545; color: white; border: none; padding: 3px 8px; cursor: pointer;">✕</button></td>
        `;
        tableBody.appendChild(newRow);
    });

    updateCrudeMix(); 
}


function collectFormData() {
    const data = {};

    const globalInputIds = [
        'processingRate', 'numTanks', 'numFilledTanks', 'numEmptyTanks', 'numIdleTanks',
        'specificIdleTanks', 'tankCapacity', 'pumpingRate', 'crudeMixTolerance',
        'minInventory', 'maxInventory',
        
        // NEW VESSELS ADDED HERE
        'ulccCapacity','minUlccRequired','ulccRateDay',
        'vlccCapacity', 'minVlccRequired', 'vlccRateDay',
        'suezmaxCapacity', 'suezmaxRateDay', 
        'aframaxCapacity', 'aframaxRateDay',
        'panamaxCapacity', 'panamaxRateDay', 
        'handymaxCapacity', 'handymaxRateDay',
        'handySizeCapacity', 'handySizeRateDay',

        'departureMode', 'manualArrivalBerth1', 'manualArrivalBerth2', 'berth_gap_hours_min', 'berth_gap_hours_max',
        'preDischargeDays', 'settlingTime', 'labTestingDays', 'tankFillGapHours', 'tankGapHours',
        'deadBottom1', 'bufferVolume', 'crudeProcessingDate', 'horizonDays', 'horizonHours',
        'horizonMinutes', 'snapshotIntervalMinutes', 'disruptionDuration', 'disruptionStart'
    ];

    const checkboxIds = [
        // NEW CHECKBOXES ADDED HERE
        'ulccIncludeReturn',
        'vlccIncludeReturn', 'suezmaxIncludeReturn', 'aframaxIncludeReturn',
        'panamaxIncludeReturn', 'handymaxIncludeReturn',
        'handySizeIncludeReturn'
    ];

    globalInputIds.forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            if (el.type === 'number') {
                data[id] = parseFloat(el.value) || 0;
            } else {
                data[id] = el.value || ''; 
            }
        }
    });

    checkboxIds.forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            data[id] = el.checked;
        }
    });

    const days = parseFloat(data.horizonDays) || 0;
    const hours = parseFloat(data.horizonHours) || 0;
    const minutes = parseFloat(data.horizonMinutes) || 0;
    data.schedulingWindow = days + (hours / 24) + (minutes / (24 * 60)); 

    data.crudeMixData = collectCrudeMixData();  

    data.idleTankData = [];
    const idleTanks = document.querySelectorAll('.uncorrected-tank-box');

    idleTanks.forEach(tankBox => {
        const sequentialId = tankBox.dataset.sequentialId; 
        const tankData = {
            sequentialId: sequentialId,
            initialCrudes: []
        };

        const crudeRows = tankBox.querySelectorAll(`#crude-tbody-${sequentialId} tr`);
        crudeRows.forEach(row => {
            const nameInput = row.querySelector('.idle-crude-name');
            const volumeInput = row.querySelector('.idle-crude-volume');
            if (nameInput && volumeInput) {
                tankData.initialCrudes.push({
                    name: nameInput.value,
                    volume: parseFloat(volumeInput.value) || 0
                });
            }
        });
        data.idleTankData.push(tankData);
    });

    const allTankBoxes = document.querySelectorAll('.tank-box, .uncorrected-tank-box');
    let maxId = 0;
    allTankBoxes.forEach(box => {
        const id = parseInt(box.dataset.sequentialId);
        if (id > maxId) maxId = id;
    });

    for (let i = 1; i <= maxId; i++) {
        const levelEl = document.getElementById(`tank${i}Level`);
        const deadBottomEl = document.getElementById(`deadBottom${i}`);
        const bufferEl = document.getElementById(`buffer${i}`);
        const nameEl = document.getElementById(`tank${i}Name`);

        if (levelEl) data[`tank${i}Level`] = parseFloat(levelEl.value) || 0;
        if (deadBottomEl) data[`deadBottom${i}`] = parseFloat(deadBottomEl.value) || 0;
        if (bufferEl) data[`buffer${i}`] = parseFloat(bufferEl.value) || 0;
        if (nameEl) data[`tank${i}Name`] = nameEl.value || `Tank ${i}`;
    }

    return data;
}

function validateTankNames(inputThatChanged = null) {
    const nameInputs = document.querySelectorAll('input[id^="tank"][id$="Name"]');
    const tankNameErrorMessage = document.getElementById('tankNameErrorMessage');
    const names = new Map();
    let hasDuplicates = false;

    nameInputs.forEach(input => input.style.border = '1px solid #ced4da');

    nameInputs.forEach(input => {
        const name = input.value.trim();
        if (name) {
            if (names.has(name)) {
                hasDuplicates = true;
                input.style.border = '2px solid #dc3545';
                const originalInput = document.getElementById(names.get(name));
                if (originalInput) originalInput.style.border = '2px solid #dc3545';
            } else {
                names.set(name, input.id);
            }
        }
    });

    if (hasDuplicates) {
        if (tankNameErrorMessage) {
            tankNameErrorMessage.textContent = 'Error: Duplicate tank names found. All tank names must be unique.';
            tankNameErrorMessage.style.display = 'block';
        }
        return false; 
    } else {
        if (tankNameErrorMessage) tankNameErrorMessage.style.display = 'none';
        return true; 
    }
}

let saveTimeout;
function autoSaveInputs() {
    clearTimeout(saveTimeout);
    saveTimeout = setTimeout(() => {
        const idleInput = document.getElementById('specificIdleTanks');
        const idleError = document.getElementById('idleValidationMessage');
        
        if (validateTankNames() && idleError.style.display === 'none') {
            saveInputsToStorage();
        } else if (idleError.style.display !== 'none') {
             console.log('Save prevented due to IDLE tank assignment error.');
        } else {
            console.log('Save prevented due to duplicate tank names.');
        }
    }, 500); 
}

async function saveInputsToStorage() {
    try {
        const inputs = collectFormData();
        localStorage.setItem('refineryInputs', JSON.stringify(inputs));
        console.log('Inputs saved to localStorage');
        
        try {
            const response = await fetch(API_ENDPOINTS.SAVE_INPUTS, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(inputs)
            });
            if (response.ok) {
                console.log('Inputs saved to server');
                showSaveStatus('saved');
            } else {
                console.log('Server save failed, but localStorage saved');
            }
        } catch (serverError) {
            console.log('Server unavailable, but localStorage saved');
        }
    } catch (e) {
        console.error('Save error:', e);
    }
}

async function autoLoadInputs() {
    let loadedFromStorage = false;
    try {
        // This is where localStorage is defined and loaded
        const saved = localStorage.getItem('refineryInputs');
        if (saved) {
            const savedInputs = JSON.parse(saved);
            applyInputValues(savedInputs);
            console.log('✅ Inputs loaded from localStorage');
            loadedFromStorage = true;
        } else {
            console.log('ℹ️ No inputs found in localStorage.');
        }
    } catch (e) {
        console.error('❌ Load error from localStorage:', e);
    }

    try {
        const response = await fetch(API_ENDPOINTS.LOAD_INPUTS);
        
        if (response.ok) {
            // This runs if the server load is successful (200 OK)
            const serverInputs = await response.json();
            if (Object.keys(serverInputs).length > 0) {
                applyInputValues(serverInputs);
                console.log('✅ Inputs loaded from server (overwriting localStorage)');
            } else {
                 console.log('ℹ️ Server returned no inputs. Using localStorage data.');
            }
        } else {
            // This block will now catch your 500 error and log it clearly
            console.warn(`⚠️ Server load failed with status: ${response.status}. Using data from localStorage (if any).`);
        }
    } catch (serverError) {
        // This catches network errors (e.g., server is completely offline)
        console.error('❌ Server network error. Using data from localStorage (if any).', serverError);
    }
}
function applyInputValues(inputValues) {
    Object.entries(inputValues).forEach(([id, value]) => {
        const element = document.getElementById(id);
        if (element) {
            if (element.type === 'checkbox') {
                element.checked = value;
            } else {
                element.value = value; 
            }
        }
    });

    if (inputValues.crudeMixData) {
        recreateCrudeMixTable(inputValues.crudeMixData);
    }

    const tankCustomNames = {};
    const tankCustomLevels = {}; 
    
    const maxSavedId = Object.keys(inputValues)
        .filter(k => k.startsWith('tank') && (k.endsWith('Name') || k.endsWith('Level'))) 
        .map(k => parseInt(k.replace('tank', '').replace('Name', '').replace('Level', ''))) 
        .reduce((max, id) => Math.max(max, id), 0);
    
    const numTanks = inputValues.numTanks || 0;
    const maxId = Math.max(numTanks, maxSavedId);

    for (let i = 1; i <= maxId; i++) {
        tankCustomNames[i] = inputValues[`tank${i}Name`]; 
        tankCustomLevels[i] = inputValues[`tank${i}Level`]; 
    }
    
    if (inputValues.numTanks || maxId > 0) {
        updateTankCategories(tankCustomNames, tankCustomLevels); 
    }

    if (inputValues.idleTankData) { 
        inputValues.idleTankData.forEach(tankData => {
            const sequentialId = tankData.sequentialId; 
            const tableBody = document.getElementById(`crude-tbody-${sequentialId}`);
            if (tableBody) {
                tableBody.innerHTML = ''; 
                tankData.initialCrudes.forEach(crude => {
                    addIdleCrudeRow(sequentialId, crude.name, crude.volume); 
                });
                updateIdleTankSummary(sequentialId); 
            }
        });
    }

    toggleDepartureMode();
    validateInventoryRange();
    validateTankNames(); 
}

async function runSimulation() {
    try {
        if (!validateTankNames()) {
            alert('❌ Simulation Canceled: Duplicate tank names found. Please fix the highlighted errors.');
            return;
        }
        const idleErrorDiv = document.getElementById('idleValidationMessage');
        if (idleErrorDiv && idleErrorDiv.style.display !== 'none') {
            alert('❌ Simulation Canceled: IDLE tank assignment error. Please fix the highlighted errors.');
            return;
        }

        Utils.showLoading(true);

        let params = collectFormData(); 

        if (currentResults && currentResults.parameters && currentResults.parameters.optimized_cargo_schedule) {
            console.log("Running simulation with the OPTIMIZED cargo schedule.");
            params = currentResults.parameters;
            params.cargo_schedule = currentResults.parameters.optimized_cargo_schedule;
         
        } else {
            console.log("Running a standard simulation from UI data.");
        }

        if (typeof params.schedulingWindow !== 'number' || isNaN(params.schedulingWindow)) {
             throw new Error('Simulation Horizon (schedulingWindow) is missing or invalid.');
        }

        const response = await fetch(API_ENDPOINTS.SIMULATE, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(params)
        });
        
        if (!response.ok) {
            throw new Error('Simulation request failed');
        }

        const simulationData = await response.json();
        if (simulationData.error) {
            alert('Simulation Error: ' + simulationData.error);
            return;
        }

        // Find the runSimulation function and locate the simulationData.simulation_data.map block
// Replace the map callback with this updated logic:

        if (simulationData.simulation_data) {
            simulationData.simulation_data = simulationData.simulation_data.map((row, index) => {
                const dateStr = row["Date"] || "";
                const openingStock = parseFloat((row["Opening Stock (bbl)"] || "0").replace(/,/g, ''));
                const closingStock = parseFloat((row["Closing Stock (bbl)"] || "0").replace(/,/g, ''));
                
                // 1. Default to the value provided in the row data
                let processing = parseFloat((row["Processing (bbl)"] || "0").replace(/,/g, ''));
                
                const readyTanks = parseInt(row["Ready Tanks"] || "0");
                const tankCapacity = parseFloat(params.tankCapacity || 600000);
                const numTanks = parseInt(params.numTanks || 12);
                const tankUtilization = (openingStock / (tankCapacity * numTanks)) * 100;
                
                let cargoTypes = [];
                let totalArrivals = 0;
                let certifiedStock = 0;
                
                // --- START FIX: Scrape Log for Accurate Processing Volume ---
                if (simulationData.simulation_log) {
                    const currentDate = dateStr.split(' ')[0];
                    
                    // We filter logs for this specific date once to be efficient
                    const dailyLogs = simulationData.simulation_log.filter(log => {
                        if (!log.Timestamp || !log.Event) return false;
                        return log.Timestamp.split(' ')[0] === currentDate;
                    });

                    let foundProcessingLog = false;
                    let logDerivedProcessing = 0;

                    dailyLogs.forEach(log => {
                        // 1. Logic for Certified Stock (Existing)
                        if (log.Event === 'DAILY_STATUS' && log.Message) {
                            const totalStockMatch = log.Message.match(/TOTAL:\s*([\d,]+)\s*bbl/);
                            if (totalStockMatch) {
                                certifiedStock = parseFloat(totalStockMatch[1].replace(/,/g, ''));
                            }
                        }

                        // 2. Logic for Cargo Arrivals (Existing)
                        if (log.Event === 'ARRIVAL') {
                            if (simulationData.cargo_report) {
                                const cargoMatch = simulationData.cargo_report.find(cargo => 
                                    cargo["Arrival Date"] === currentDate && 
                                    cargo["Vessel Name"] === log.Cargo
                                );
                                if (cargoMatch) {
                                    cargoTypes.push(cargoMatch["Cargo Type"]);
                                    totalArrivals += parseFloat((cargoMatch["Total Volume Discharged (bbl)"] || "0").replace(/,/g, ''));
                                }
                            }
                        }

                        // 3. NEW LOGIC: Robust Regex for Processed Volume
                        // Matches "Processed: 450,000" or "Processed 450,000", ignoring earlier numbers
                        if (log.Message) {
                            const procMatch = log.Message.match(/Processed[:\s]+\s*([0-9,]+(\.\d+)?)/i);
                            if (procMatch) {
                                foundProcessingLog = true;
                                const val = parseFloat(procMatch[1].replace(/,/g, ''));
                                // If multiple logs exist, take the max (assuming it's the daily total)
                                if (val > logDerivedProcessing) logDerivedProcessing = val;
                            }
                        }
                    });

                    // Apply the fix:
                    if (foundProcessingLog) {
                        processing = logDerivedProcessing;
                    } else {
                        // Fallback: if no log found, but certified stock is 0, force processing to 0
                        if (certifiedStock <= 0) {
                            processing = 0;
                        }
                    }
                }
                // --- END FIX ---
                
                return {
                    day: index + 1,
                    date: dateStr,
                    start_inventory: openingStock,
                    end_inventory: closingStock,
                    processing: processing, // This now holds the corrected value
                    ready_tanks: readyTanks,
                    tank_utilization: tankUtilization,
                    cargo_type: cargoTypes.length > 0 ? cargoTypes.join(' + ') : null,
                    arrivals: totalArrivals,
                    certified_stock: certifiedStock,
                    ...Object.keys(row)
                        .filter(key => key.startsWith('Tank') && key.length <= 6)
                        .reduce((acc, key) => ({ ...acc, [key]: row[key] }), {})
                };
            });
        }

        const optimizationSummary = currentResults ? currentResults.optimization_results : null;
        
        simulationData.parameters = params;
        
        currentResults = simulationData;
        if (optimizationSummary) {
            currentResults.optimization_results = optimizationSummary;
        }

        displayResults(currentResults);
        displayInventoryTracking(currentResults.simulation_data); 

        Utils.showResults();
        showTab('simulation', document.querySelector('.tab'));
        
    } catch (error) {
        console.error('Simulation error:', error);
        alert('Simulation failed: ' + error.message);
    } finally {
        Utils.showLoading(false);
    }
}

function triggerCSVDownload(csv_files) {
    if (!csv_files || Object.keys(csv_files).length === 0) {
        alert('No CSV files are available for download. Please run a simulation first.');
        return;
    }
    
    console.log('Attempting sequential download of CSV files to avoid browser block.');

    const filesToDownload = Object.entries(csv_files);
    
    const delay = ms => new Promise(resolve => setTimeout(resolve, ms));

    (async () => {
        for (const [filename, url] of filesToDownload) {
            const link = document.createElement('a');
            link.href = url;
            link.download = filename;
            link.style.display = 'none';
            document.body.appendChild(link);
            
            link.click();
            document.body.removeChild(link);

            await delay(250); 
        }
        
        const fileCount = filesToDownload.length;
        console.log(`✅ Download process initiated for ${fileCount} CSV files.`);
        alert(`✅ Download initiated for ${fileCount} CSV files. Check your downloads folder.`);
    })();
}

function downloadCSVs() {
    if (currentResults && currentResults.csv_files) {
        triggerCSVDownload(currentResults.csv_files);
    } else {
        alert('No simulation results found. Please run a simulation first.');
    }
}

function displayResults(data) {
    const now = new Date();
    const timestampElement = document.getElementById('reportTimestamp');
    if (timestampElement) {
        timestampElement.textContent = `Report generated on: ${now.toLocaleString()}`;
    }
   
    const metricsContainer = document.getElementById('metricsContainer');
    metricsContainer.innerHTML = '<h3> Performance Metrics</h3>';

    if (data.metrics) {
        const metricsDiv = document.createElement('div');
        metricsDiv.className = 'metrics-grid';
        const processingEfficiency = data.metrics.processing_efficiency ? data.metrics.processing_efficiency.toFixed(1) : 'N/A';
        const avgUtilization = data.metrics.avg_utilization ? data.metrics.avg_utilization.toFixed(1) : 'N/A';

        metricsDiv.innerHTML = `
            <div class="metric-card">
                <h4>Processing Efficiency</h4>
                <p class="metric-value">${processingEfficiency}%</p>
            </div>
            <div class="metric-card">
                <h4>Total Processed</h4>
                <p class="metric-value">${data.metrics.total_processed ? data.metrics.total_processed.toLocaleString() : 'N/A'} bbl</p>
            </div>
            <div class="metric-card">
                <h4>Critical Days</h4>
                <p class="metric-value">${data.metrics.critical_days} days</p>
            </div>
            <div class="metric-card">
                <h4>Tank Utilization</h4>
                <p class="metric-value">${avgUtilization}%</p>
            </div>
            <div class="metric-card">
                <h4>Clash Days</h4>
                <p class="metric-value">${data.metrics.clash_days} days</p>
            </div>
            <div class="metric-card">
                <h4>Sustainable</h4>
                <p class="metric-value">${data.metrics.sustainable_processing ? '✅ Yes' : '❌ No'}</p>
            </div>
        `;
        metricsContainer.appendChild(metricsDiv);
    }

    if (data.simulation_log) {
        displaySimulationLog(data);
    }

    if (data.simulation_data) {
        displayDailyReport(data);
    }
}

function safeParseDate(dateStr) {
    if (!dateStr) return null;
    try {
        const parts = dateStr.match(/(\d{2})\/(\d{2})\/(\d{4})\s+(\d{2}):(\d{2})/);
        if (parts) {
            return new Date(parts[3], parts[2] - 1, parts[1], parts[4], parts[5]);
        }
    } catch (e) {
        console.error("Error parsing date:", dateStr, e);
    }
    return null;
}

function displayDailyReport(results) {
    const container = document.getElementById('dailyReportContainer');

    if (!results.simulation_data || results.simulation_data.length === 0) {
        container.innerHTML = '<p>No daily report data available</p>';
        return;
    }

    let tableHTML = `
        <h3>📊 Daily Operations Report</h3>
        <table class="schedule-table">
            <thead>
                <tr>
                    <th>Day</th>
                    <th>Date / Time Range</th>
                    <th>Open Inventory</th>
                    <th style="background-color: #d4edda;">Cert Stk</th>
                    <th style="background-color: #fff3cd;">Uncert Stk</th>
                    <th>Processing</th>
                    <th>Closing Inventory</th>
                    <th>Tank Util %</th>
                    <th>Cargo Arrival</th>
                </tr>
            </thead>
            <tbody>
    `;

    results.simulation_data.forEach((dayData, dayIndex) => {
        let dateToDisplay = dayData.date;
        const dayStartsAt = safeParseDate(dayData.date); 
        
        if (dayIndex === results.simulation_data.length - 1 && dayStartsAt) {
            const lastLogEntry = results.simulation_log
                .filter(log => log.Event === 'DAILY_END')
                .sort((a, b) => safeParseDate(b.Timestamp) - safeParseDate(a.Timestamp))[0]; 
            
            if (lastLogEntry) {
                const endDateTime = safeParseDate(lastLogEntry.Timestamp);
                if (endDateTime) {
                    const startDayMonth = dayStartsAt.toLocaleDateString('en-GB', {day: '2-digit', month: '2-digit'});
                    const startTime = dayStartsAt.toLocaleTimeString('en-GB', {hour: '2-digit', minute: '2-digit', hour12: false});
                    const endDayMonth = endDateTime.toLocaleDateString('en-GB', {day: '2-digit', month: '2-digit'});
                    const endTime = endDateTime.toLocaleTimeString('en-GB', {hour: '2-digit', minute: '2-digit', hour12: false});
                    dateToDisplay = `${startDayMonth} ${startTime} to ${endDayMonth} ${endTime}`;
                }
            }
        }
        
        let certStock = dayData.certified_stock || 0;
        const uncertStock = Math.max(0, dayData.start_inventory - certStock);
        const cargoInfo = dayData.cargo_type ? `${dayData.cargo_type} (${Utils.formatNumber(dayData.arrivals)})` : '-';
        
        const tankUtilization = dayData.tank_utilization ? dayData.tank_utilization.toFixed(1) + '%' : 'N/A';
        
        let processingToShow = dayData.processing;
        if (dayData.expected_processing_resumed && dayData.expected_processing_resumed > 0) {
            processingToShow = dayData.expected_processing_resumed;
        }

        tableHTML += `
            <tr>
                <td><strong>${dayData.day}</strong></td>
                <td>${dateToDisplay}</td>
                <td style="color: #007bff;">${Utils.formatNumber(dayData.start_inventory)}</td>
                <td style="color: #28a745; font-weight: bold;">${Utils.formatNumber(certStock)}</td>
                <td style="color: #856404; font-weight: bold;">${Utils.formatNumber(uncertStock)}</td>
                <td style="color: #dc3545;">${Utils.formatNumber(processingToShow)}</td>
                <td style="color: #28a745;">${Utils.formatNumber(dayData.end_inventory)}</td>
                <td style="color: #6f42c1;">${tankUtilization}</td>
                <td>${cargoInfo}</td>
            </tr>
        `;
    });

    tableHTML += '</tbody></table>';
    container.innerHTML = tableHTML;
}

function displaySimulationLog(results) {
    const container = document.getElementById('simulationLogContainer');
    
    if (!container) {
        const logContainer = document.createElement('div');
        logContainer.id = 'simulationLogContainer';
        const dailyReport = document.getElementById('dailyReportContainer');
        if (dailyReport && dailyReport.parentNode) {
            dailyReport.parentNode.insertBefore(logContainer, dailyReport);
        }
        return displaySimulationLog(results);
    }

    if (!results.simulation_log || results.simulation_log.length === 0) {
        container.innerHTML = '<p>No simulation log available</p>';
        return;
    }
    const tankNameMap = new Map();
    if (results.parameters && results.parameters.numTanks) {
        const numTanks = parseInt(results.parameters.numTanks) || 0;
        for (let i = 1; i <= numTanks; i++) {
            const defaultName = `Tank ${i}`; 
            const customName = results.parameters[`tank${i}Name`]; 
            
            if (customName) {
                tankNameMap.set(defaultName, customName);
            }
        }
    }
    const getCustomName = (defaultName) => tankNameMap.get(defaultName) || defaultName;

    const tankColumns = Object.keys(results.simulation_log[0]).filter(key => /^Tank\d+$/.test(key));

    let tableHTML = `
        <h3> Detailed Simulation Log</h3>
        <table class="schedule-table" style="font-size: 0.85em; table-layout: fixed; width: 100%;">
            <thead>
                <tr>
                    <th style="width: 13%;">Timestamp</th>
                    <th style="width: 8%;">Level</th>
                    <th style="width: 11%;">Event</th>

                    <th style="width: 10%;">Tank</th>
                    
                    <th style="width: 10%;">Cargo</th>
                    
                    <th style="text-align: left; width: 48%;">Message</th>
                </tr>
            </thead>
            <tbody>
    `;

    results.simulation_log.forEach((logEntry, index) => {
        let levelColor = '#000';
        if (logEntry.Level === 'Success') levelColor = '#28a745';
        else if (logEntry.Level === 'Warning') levelColor = '#ffc107';
        else if (logEntry.Level === 'Danger') levelColor = '#dc3545';
        else if (logEntry.Level === 'Info') levelColor = '#007bff';

        let message = logEntry.Message;
        
        if (logEntry.Event && logEntry.Event.startsWith('READY')) {
            let readyCount = 0;
            if (index + 1 < results.simulation_log.length) {
                const nextRow = results.simulation_log[index + 1];
                readyCount = tankColumns.filter(col => nextRow[col] === 'READY').length;
            } else {
                readyCount = tankColumns.filter(col => logEntry[col] === 'READY').length;
            }
            if (readyCount > 0) {
                message = `${message} No of READY tanks : ${readyCount}`;
            }
        }

        tableHTML += `
            <tr>
                <td style="word-wrap: break-word;">${logEntry.Timestamp}</td>
                <td style="color: ${levelColor}; font-weight: bold; word-wrap: break-word;">${logEntry.Level}</td>
                <td style="word-wrap: break-word;">${logEntry.Event}</td>
                
                <td style="word-wrap: break-word; white-space: nowrap;">${getCustomName(logEntry.Tank) || '-'}</td>
                
                <td style="word-wrap: break-word; white-space: nowrap;">${logEntry.Cargo || '-'}</td>
                <td style="text-align: left; word-wrap: break-word;">${message}</td>
            </tr>
        `;
    });

    tableHTML += '</tbody></table></div>';
   container.innerHTML = tableHTML;
}

async function calculateBuffer() {
    try {
        Utils.showLoading(true);
        const params = collectFormData();
        const response = await fetch(API_ENDPOINTS.BUFFER_ANALYSIS, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(params)
        });
        if (!response.ok) {
            throw new Error('Buffer analysis request failed');
        }
        const bufferResults = await response.json();
        displayBufferAnalysis(bufferResults);
        Utils.showResults();
        showTab('buffer', document.querySelectorAll('.tab')[1]);
    } catch (error) {
        console.error('Buffer analysis error:', error);
        alert('Buffer analysis failed: ' + error.message);
    } finally {
        Utils.showLoading(false);
    }
}

function displayBufferAnalysis(bufferResults) {
    const container = document.getElementById('bufferResults');
    let html = '<h3>🛡️ Buffer Analysis Report</h3>';

    if (bufferResults && Object.keys(bufferResults).length > 0) {
        html += '<div class="buffer-scenarios">';
        Object.entries(bufferResults).forEach(([scenarioKey, scenario]) => {
            const adequateText = scenario.adequate_current ? '✅ Adequate' : '❌ Insufficient';
            const adequateColor = scenario.adequate_current ? '#28a745' : '#dc3545';
            html += `
                <div class="scenario-card" style="border: 1px solid #ddd; margin: 10px 0; padding: 15px; border-radius: 5px;">
                    <h4>${scenario.description}</h4>
                    <div class="scenario-details">
                        <p><strong>Lead Time:</strong> ${scenario.lead_time.toFixed(1)} days</p>
                        <p><strong>Buffer Needed:</strong> ${Utils.formatNumber(scenario.buffer_needed)} barrels</p>
                        <p><strong>Tanks Required:</strong> ${scenario.tanks_needed} tanks</p>
                        <p><strong>Current Capacity:</strong> <span style="color: ${adequateColor}; font-weight: bold;">${adequateText}</span></p>
                        ${scenario.additional_tanks > 0 ?
                            `<p style="color: #dc3545;"><strong>Additional Tanks Needed:</strong> ${scenario.additional_tanks}</p>` :
                            '<p style="color: #28a745;"><strong>No additional tanks needed</strong></p>'
                        }
                    </div>
                </div>
            `;
        });
        html += '</div>';
    } else {
        html += '<p>No buffer analysis data available</p>';
    }
    container.innerHTML = html;
}

async function optimizeTanks() {
    try {
        Utils.showLoading(true);
        const params = collectFormData();
        const response = await fetch(API_ENDPOINTS.CARGO_OPTIMIZATION, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(params)
        });
        if (!response.ok) {
            throw new Error('Optimization request failed');
        }
        const optimizationResults = await response.json();
        displayCargoOptimizationResults(optimizationResults); 
        Utils.showResults();
        showTab('optimization', document.querySelectorAll('.tab')[2]);
    } catch (error) {
        console.error('Cargo optimization error:', error);
        alert('Optimization failed: ' + error.message);
    } finally {
        Utils.showLoading(false);
    }
}

function displayCargoOptimizationResults(results) {
    const container = document.getElementById('optimizationResults');
    if (results) {
        container.innerHTML = `<h3>⚡ Cargo Optimization Results</h3><pre>${JSON.stringify(results, null, 2)}</pre>`;
    } else {
        container.innerHTML = '<h3>⚡ Cargo Optimization Results</h3><p>No results returned.</p>';
    }
}

function displayCargoReport(data) {
    let container = document.getElementById('cargoReportContainer');
    if (!container) {
        container = document.createElement('div');
        container.id = 'cargoReportContainer';
        const metricsContainer = document.getElementById('metricsContainer');
        if (metricsContainer) {
            metricsContainer.parentNode.insertBefore(container, metricsContainer.nextSibling);
        }
    }

    if (!data.cargo_report || data.cargo_report.length === 0) {
        container.innerHTML = '<h3>🚢 Cargo Schedule Report</h3><p><em>No cargo schedule available</em></p>';
        return;
    }

    const cargoReport = data.cargo_report;
    let html = '<h3>🚢 Cargo Schedule Report</h3>';
    html += '<p><em>Detailed cargo timeline with load port, departure, arrival, and discharge times</em></p>';
    html += '<div class="cargo-schedule-table"><table class="data-table">';
    html += '<thead><tr><th>BERTH</th><th>CARGO NAME</th><th>CARGO TYPE</th><th>SIZE</th><th>L.PORT TIME</th><th>ARRIVAL</th><th>PUMPING</th><th>DEP.TIME</th></tr></thead><tbody>';

    cargoReport.forEach(cargo => {
        html += '<tr>';
        html += `<td>${cargo.berth || 'N/A'}</td>`;
        html += `<td>${cargo.vessel_name || 'N/A'}</td>`;
        html += `<td>${cargo.type || 'N/A'}</td>`;
        html += `<td>${Utils.formatNumber(cargo.size) || '0'}</td>`;
        html += `<td>${cargo.load_port_time || 'N/A'}</td>`;
        html += `<td>${cargo.arrival_time || 'N/A'}</td>`;
        html += `<td>${cargo.pumping_days ? cargo.pumping_days.toFixed(1) : 'N/A'}</td>`;
        html += `<td>${cargo.dep_unload_port || 'N/A'}</td>`;
        html += '</tr>';
    });

    html += '</tbody></table></div>';
    container.innerHTML = html;
}

function showTab(tabId, tabButton) {
    document.querySelectorAll('.tab-content').forEach(content => {
        content.classList.remove('active');
    });
    document.querySelectorAll('.tab').forEach(tab => {
        tab.classList.remove('active');
    });
    document.getElementById(tabId).classList.add('active');
    if (tabButton) tabButton.classList.add('active');
}

function validateInventoryRange() {
    const minInventory = parseFloat(document.getElementById('minInventory').value) || 0;
    const maxInventory = parseFloat(document.getElementById('maxInventory').value) || 0;
    const messageDiv = document.getElementById('inventoryValidationMessage');
    const actualTankCount = getCurrentTankCount();

    let isValid = true;
    let message = '';
    let messageType = 'success';

    if (minInventory >= maxInventory) {
        isValid = false;
        message = '❌ Minimum inventory must be less than maximum inventory';
        messageType = 'error';
    } else if (minInventory < 0 || maxInventory < 0) {
        isValid = false;
        message = '❌ Inventory values cannot be negative';
        messageType = 'error';
    } else {
        let currentInventory = 0;
        const allTankBoxes = document.querySelectorAll('.tank-box, .uncorrected-tank-box');
        let activeTankCount = 0;
        allTankBoxes.forEach(box => {
            const id = box.dataset.sequentialId;
            const tankLevel = parseFloat(document.getElementById(`tank${id}Level`)?.value) || 0;
            const deadBottom = parseFloat(document.getElementById(`deadBottom${id}`)?.value || document.getElementById('deadBottom1')?.value) || 10000;
            currentInventory += Math.max(0, tankLevel - deadBottom);
            activeTankCount++;
        });


        if (currentInventory < minInventory) {
            isValid = false;
            message = `⚠️ Current inventory (${currentInventory.toLocaleString()} bbl) is below minimum (${minInventory.toLocaleString()} bbl)`;
            messageType = 'warning';
        } else if (currentInventory > maxInventory) {
            isValid = false;
            message = `⚠️ Current inventory (${currentInventory.toLocaleString()} bbl) is above maximum (${maxInventory.toLocaleString()} bbl)`;
            messageType = 'warning';
        } else {
            message = `✅ Current inventory: ${currentInventory.toLocaleString()} bbl (Range: ${minInventory.toLocaleString()} - ${maxInventory.toLocaleString()} bbl) - ${activeTankCount} tanks`;
            messageType = 'success';
        }
    }

    if (messageDiv) {
        messageDiv.style.display = 'block';
        messageDiv.innerHTML = message;
        messageDiv.style.backgroundColor = messageType === 'error' ? '#f8d7da' : (messageType === 'warning' ? '#fff3cd' : '#d1edff');
        messageDiv.style.color = messageType === 'error' ? '#721c24' : (messageType === 'warning' ? '#856404' : '#0c5460');
        messageDiv.style.border = messageType === 'error' ? '1px solid #f5c6cb' : (messageType === 'warning' ? '1px solid #ffeaa7' : '1px solid #bee5eb');
    }
    return isValid;
}

function checkInventoryRange() {
    Utils.showLoading(true);
    const params = collectFormData();
    fetch('/api/validate_inventory_range', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(params)
        })
        .then(response => response.json())
        .then(data => {
            Utils.showLoading(false);
            if (data.success) {
                alert(`✅ INVENTORY RANGE VALIDATION PASSED\n\n${data.message}`);
            } else {
                alert(`❌ INVENTORY RANGE VALIDATION FAILED\n\n${data.message}`);
            }
        })
        .catch(error => {
            Utils.showLoading(false);
            console.error('Inventory validation error:', error);
            alert('❌ Error validating inventory range.');
        });
}

function displayInventoryTracking(inventoryData) {
    const container = document.getElementById('inventoryResults');
    if (!container || !inventoryData || inventoryData.length === 0) {
        if (container) container.innerHTML = '<p>No inventory tracking data available.</p>';
        return;
    }
    
    const ctx = document.getElementById('inventoryChart').getContext('2d');
    const labels = inventoryData.map(d => `Day ${d.day}`);
    const dataPoints = inventoryData.map(d => d.end_inventory);

    if (window.myInventoryChart) {
        window.myInventoryChart.destroy();
    }

    window.myInventoryChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'End of Day Inventory (bbl)',
                data: dataPoints,
                borderColor: '#007bff',
                backgroundColor: 'rgba(0, 123, 255, 0.1)',
                fill: true,
                tension: 0.1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: { callback: value => value.toLocaleString() + ' bbl' }
                }
            }
        }
    });
}

function initializeAutoSave() {
    const inputs = document.querySelectorAll('input, select, textarea');
    inputs.forEach(input => {
        const onchangeAttr = input.getAttribute('onchange');
        
        if (onchangeAttr && onchangeAttr.includes('autoSaveInputs()')) {
        } else {
            if (input.type === 'number' || input.type === 'text' || input.type === 'datetime-local' || input.tagName.toLowerCase() === 'textarea') {
                let timeout;
                input.addEventListener('input', () => {
                    clearTimeout(timeout);
                    timeout = setTimeout(autoSaveInputs, 1000); 
                });
                input.addEventListener('blur', autoSaveInputs);
            } else {
                input.addEventListener('change', autoSaveInputs);
            }
        }
    });
    console.log(`Auto-save initialized for ${inputs.length} inputs`);
}


function showSaveStatus(status) {
    let indicator = document.getElementById('saveIndicator');
    if (!indicator) {
        indicator = document.createElement('div');
        indicator.id = 'saveIndicator';
        indicator.style.cssText = `
            position: fixed; top: 10px; right: 10px; padding: 8px 12px;
            background: #28a745; color: white; border-radius: 4px;
            font-size: 12px; z-index: 1000; transition: opacity 0.3s;
        `;
        document.body.appendChild(indicator);
    }
    
    if (status === 'saved') {
        indicator.textContent = '✓ Saved';
        indicator.style.opacity = '1';
        setTimeout(() => { indicator.style.opacity = '0'; }, 2000);
    }
}

document.addEventListener('DOMContentLoaded', async () => { // Make async
    await autoLoadInputs(); // Await for the inputs to finish loading
    
    // Now run these functions *after* loading is complete
    applyGlobalTankCapacity(); // <-- ADDED: Applies the loaded global capacity
    initializeAutoSave(); 
    validateInventoryRange();
    
    console.log("Application initialized, inputs loaded, auto-save enabled.");
});

async function handleFileDownload(response, defaultFilename) {
    const contentType = response.headers.get('content-type');
    
    if (contentType && contentType.includes('application/json')) {
        const result = await response.json();
        if (result.filename) {
            alert(`✅ Report exported: ${result.filename}`);
        } else {
            alert(`❌ Export failed: ${result.error || 'Unknown server error'}`);
        }
    } else {
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.style.display = 'none';
        a.href = url;
        
        const disposition = response.headers.get('Content-Disposition');
        let filename = defaultFilename;
        if (disposition) {
            const matches = /filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/.exec(disposition);
            if (matches != null && matches[1]) {
                filename = matches[1].replace(/['"]/g, '');
            }
        }
        
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
        
        alert(`✅ Report downloaded: ${filename}`);
    }
}

async function showTankStatus() {
    if (!currentResults) {
        alert('Please run a simulation first');
        return;
    }
    try {
        Utils.showLoading(true);
        const response = await fetch(API_ENDPOINTS.EXPORT_TANK_STATUS, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(currentResults)
        });
        if (!response.ok) throw new Error('Tank status export failed');
        await handleFileDownload(response, 'tank_status_export.xlsx');
    } catch (error) {
        console.error('Tank status error:', error);
        alert('Tank status export failed: ' + error.message);
    } finally {
        Utils.showLoading(false);
    }
}

async function exportCharts() {
    if (!currentResults) {
        alert('⚠️ Please run a simulation first to generate charts data.');
        return;
    }
    try {
        Utils.showLoading(true);
        document.getElementById('loading').querySelector('p').textContent = 'Generating charts...';
        
        const response = await fetch('/api/export_charts', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(currentResults)
        });
        if (!response.ok) throw new Error('Charts export failed');
        await handleFileDownload(response, 'charts_export.xlsx');
    } catch (error) {
        console.error('Charts export error:', error);
        alert(`❌ Charts export error: ${error.message}`);
    } finally {
        Utils.showLoading(false);
        document.getElementById('loading').querySelector('p').textContent = 'Running simulation...';
    }
}

async function optimizeCrudeMix() {
    try {
        if (!validateTankNames()) {
            alert('❌ Optimization Canceled: Duplicate tank names found. Please fix the highlighted errors.');
            return;
        }
        const idleErrorDiv = document.getElementById('idleValidationMessage');
        if (idleErrorDiv && idleErrorDiv.style.display !== 'none') {
            alert('❌ Optimization Canceled: IDLE tank assignment error. Please fix the highlighted errors.');
            return;
        }

        Utils.showLoading(true);
        document.getElementById('loading').querySelector('p').textContent = 'Optimizing crude mix...';

        const params = collectFormData();
        const crudeNames = [];
        const crudePercentages = [];
        
        document.querySelectorAll('.crude-mix-row').forEach(row => {
            const nameInput = row.querySelector('.crude-name-input');
            const percentageInput = row.querySelector('.crude-percentage-input');
            if (nameInput && percentageInput) {
                const name = nameInput.value.trim();
                const percentage = parseFloat(percentageInput.value) || 0;
                if (name && percentage > 0) {
                    crudeNames.push(name);
                    crudePercentages.push(percentage);
                }
            }
        });

        params.crude_names = crudeNames;
        params.crude_percentages = crudePercentages;

        const response = await fetch('/api/optimize_crude_mix', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(params)
        });

        const results = await response.json();
        if (!response.ok || !results.success) {
            const errorMessage = results.error || 'Optimization request failed';
            const errorDetails = results.details ? `\n\nDetails: ${results.details}` : '';
            throw new Error(errorMessage + errorDetails);
        }

        if (!currentResults) {
            currentResults = {};
        }
        currentResults.parameters = params;
        currentResults.parameters.use_optimized_schedule = true;
        currentResults.parameters.optimized_cargo_schedule = results.optimization_results.cargo_schedule;
        currentResults.optimization_results = results.optimization_results;
        
        displayOptimizationResults(results);
        Utils.showResults();
        showTab('simulation', document.querySelector('.tab'));
        
        alert('✅ Crude mix optimization successful! Click "Run Simulation" to see it in action.');

    } catch (error) {
        console.error('Crude mix optimization error:', error);
        alert('Optimization Failed:\n' + error.message);
    } finally {
        Utils.showLoading(false);
        document.getElementById('loading').querySelector('p').textContent = 'Running simulation...';
    }
}

async function exportSolverReport() {
    if (!currentResults || !currentResults.optimization_results) {
        alert('⚠️ Please run a crude mix optimization first to generate a solver report.');
        return;
    }
    try {
        Utils.showLoading(true);
        document.getElementById('loading').querySelector('p').textContent = 'Generating solver report...';
        
        const response = await fetch('/api/export_solver_report', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(currentResults.optimization_results) 
        });
        if (!response.ok) throw new Error(`Server responded with status ${response.status}`);
        await handleFileDownload(response, 'solver_report.txt');
    } catch (error) {
        console.error('Solver report export error:', error);
        alert(`❌ Solver report export error: ${error.message}`);
    } finally {
        Utils.showLoading(false);
        document.getElementById('loading').querySelector('p').textContent = 'Running simulation...';
    }
}

function displayOptimizationResults(results) {
    const metricsContainer = document.getElementById('metricsContainer');
    
    if (results.success && results.optimization_results) {
        const opt = results.optimization_results;
        let html = '<h3>🧪 Crude Mix Optimization Summary</h3>';
        html += '<div class="metrics-grid">';
        html += Utils.createMetricCard('Total Charter Cost', opt.total_charter_cost, 'Based on vessel rates');
        html += Utils.createMetricCard('Cargoes Scheduled', opt.total_to_load_bbl ? `${opt.total_cargoes} (${Utils.formatNumber(opt.total_to_load_bbl)} bbl)` : `${opt.total_cargoes}`, 'To meet inventory and mix targets');
        html += Utils.createMetricCard('Solver Status', opt.solver_status, 'Result from the optimization engine');
        html += '</div>';
        metricsContainer.innerHTML = html;
    }
}

window.populateTankLevels = populateTankLevels;
window.toggleDepartureMode = toggleDepartureMode;
window.applyDefaultDeadBottom = applyDefaultDeadBottom;
window.autoSaveInputs = autoSaveInputs;
window.autoLoadInputs = autoLoadInputs;
window.runSimulation = runSimulation;
window.calculateBuffer = calculateBuffer;
window.optimizeTanks = optimizeTanks;
window.showTankStatus = showTankStatus;
window.showTab = showTab;
window.validateInventoryRange = validateInventoryRange;
window.checkInventoryRange = checkInventoryRange;

window.scrollToTop = scrollToTop;
window.scrollToBottom = scrollToBottom;
window.scrollToSimulation = scrollToSimulation;
window.updateTankCategories = updateTankCategories;
window.addOneTank = addOneTank;
window.removeOneTank = removeOneTank;
window.addIdleCrudeRow = addIdleCrudeRow;
window.updateIdleTankSummary = updateIdleTankSummary;
window.initializeAutoSave = initializeAutoSave;
window.showSaveStatus = showSaveStatus;
window.applyInputValues = applyInputValues;
window.getCurrentTankCount = getCurrentTankCount;
window.exportCharts = exportCharts;
window.optimizeCrudeMix = optimizeCrudeMix; 
window.addCrudeRow = addCrudeRow;
window.removeCrudeRow = removeCrudeRow;
window.updateCrudeMix = updateCrudeMix;
window.resetCrudeMix = resetCrudeMix;
window.updateTankCapacities = updateTankCapacities;
window.collectFormData = collectFormData;   
window.recreateCrudeMixTable = recreateCrudeMixTable;
window.exportSolverReport = exportSolverReport;
window.applyGlobalTankCapacity = applyGlobalTankCapacity;
window.applyGlobalBufferVolume = applyGlobalBufferVolume;
window.autoCalculatePumpingDays = autoCalculatePumpingDays;
window.autoCalculateLeadTime = autoCalculateLeadTime;
window.scrollToCargoReport = scrollToCargoReport;
window.triggerCSVDownload = triggerCSVDownload;
window.downloadCSVs = downloadCSVs;