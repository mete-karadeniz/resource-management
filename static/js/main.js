// ============ THEME ============
function getTheme(){return localStorage.getItem('theme')||'light'}
function setTheme(t){document.documentElement.setAttribute('data-theme',t);localStorage.setItem('theme',t);var i=document.getElementById('theme-icon'),tx=document.getElementById('theme-text');if(i)i.className=t==='dark'?'fas fa-sun':'fas fa-moon';if(tx)tx.textContent=t==='dark'?'Aydınlık Mod':'Gece Modu'}
function toggleTheme(){setTheme(getTheme()==='light'?'dark':'light')}
(function(){document.documentElement.setAttribute('data-theme',getTheme())})();
document.addEventListener('DOMContentLoaded',function(){setTheme(getTheme())});

// ============ SIDEBAR ============
function toggleSidebar(){var sb=document.getElementById('sidebar');if(!sb)return;if(window.innerWidth<=768)sb.classList.toggle('mobile-open');else sb.classList.toggle('collapsed')}
document.addEventListener('click',function(e){var sb=document.getElementById('sidebar');if(sb&&window.innerWidth<=768&&sb.classList.contains('mobile-open')&&!sb.contains(e.target)&&!e.target.closest('.mobile-menu-btn'))sb.classList.remove('mobile-open')});

// ============ MULTI-SELECT CELL EDIT ============
var currentCell = null;
var selectedColor = 'green';
var selectedCells = [];
var isDragging = false;
var dragStartCell = null;

function initGanttDrag() {
    var cells = document.querySelectorAll('.gantt-cell[data-person-id]');
    for (var i = 0; i < cells.length; i++) {
        cells[i].addEventListener('mousedown', onCellMouseDown);
        cells[i].addEventListener('mouseenter', onCellMouseEnter);
    }
    document.addEventListener('mouseup', onCellMouseUp);
}

function onCellMouseDown(e) {
    if (typeof IS_ADMIN === 'undefined' || !IS_ADMIN) return;
    if (!this.dataset.personId || !this.dataset.engagementId) return;

    e.preventDefault();
    isDragging = true;
    dragStartCell = this;
    clearSelection();
    addToSelection(this);
}

function onCellMouseEnter(e) {
    if (!isDragging || !IS_ADMIN) return;
    if (!this.dataset.personId || !this.dataset.engagementId) return;

    // Aynı satırda (aynı person + engagement) olmalı
    if (this.dataset.personId === dragStartCell.dataset.personId &&
        this.dataset.engagementId === dragStartCell.dataset.engagementId) {
        addToSelection(this);
    }
}

function onCellMouseUp(e) {
    if (!isDragging) return;
    isDragging = false;

    if (selectedCells.length > 0) {
        openMultiCellEdit();
    }
}

function addToSelection(cell) {
    if (selectedCells.indexOf(cell) === -1) {
        selectedCells.push(cell);
        cell.classList.add('cell-selected');
    }
}

function clearSelection() {
    for (var i = 0; i < selectedCells.length; i++) {
        selectedCells[i].classList.remove('cell-selected');
    }
    selectedCells = [];
}

function openMultiCellEdit() {
    if (selectedCells.length === 0) return;

    // İlk hücrenin değerlerini al
    var first = selectedCells[0];
    var hours = parseFloat(first.dataset.hours) || 0;
    var color = first.dataset.color || 'green';

    var hoursInput = document.getElementById('cell-hours');
    if (hoursInput) hoursInput.value = hours;
    selectColor(color, null);

    // Popup title güncelle
    var titleEl = document.querySelector('#cell-popup .cell-popup-header span');
    if (titleEl) {
        titleEl.textContent = selectedCells.length > 1
            ? selectedCells.length + ' hücre seçili'
            : 'Hücre Düzenle';
    }

    var popup = document.getElementById('cell-popup');
    if (!popup) return;

    var last = selectedCells[selectedCells.length - 1];
    var r = last.getBoundingClientRect();
    var l = r.right + 8, t = r.top;
    if (l + 220 > window.innerWidth) l = r.left - 218;
    if (l < 10) l = 10;
    if (t + 240 > window.innerHeight) t = window.innerHeight - 250;
    if (t < 10) t = 10;

    popup.style.left = l + 'px';
    popup.style.top = t + 'px';
    popup.style.display = 'block';

    setTimeout(function() { if (hoursInput) hoursInput.focus(); }, 50);
}

function closeCellPopup() {
    var popup = document.getElementById('cell-popup');
    if (popup) popup.style.display = 'none';
    clearSelection();
    currentCell = null;
}

function selectColor(c, btn) {
    selectedColor = c;
    var all = document.querySelectorAll('.color-btn');
    for (var i = 0; i < all.length; i++) all[i].classList.remove('active');
    var target = btn || document.querySelector('.color-btn.color-' + c);
    if (target) target.classList.add('active');
}

function saveCellEdit() {
    if (selectedCells.length === 0) return;

    var hoursInput = document.getElementById('cell-hours');
    var hours = parseFloat(hoursInput ? hoursInput.value : 0) || 0;

    if (selectedCells.length === 1) {
        // Tek hücre
        var cell = selectedCells[0];
        fetch('/api/booking', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                person_id: parseInt(cell.dataset.personId),
                engagement_id: parseInt(cell.dataset.engagementId),
                week_start: cell.dataset.week,
                hours: hours,
                color: selectedColor
            })
        }).then(function(r) {
            if (r.status === 401 || r.status === 403) { showToast('Yetkiniz yok!'); closeCellPopup(); return null; }
            return r.json();
        }).then(function(res) {
            if (!res) return;
            if (res.success) {
                updateCellVisual(cell, hours, selectedColor);
                updateTotalCell(res.category, cell.dataset.week, res.cat_total);
                closeCellPopup();
                showToast('Kaydedildi ✓');
            }
        });
    } else {
        // Çoklu hücre - bulk API
        var bookings = [];
        for (var i = 0; i < selectedCells.length; i++) {
            var c = selectedCells[i];
            bookings.push({
                person_id: parseInt(c.dataset.personId),
                engagement_id: parseInt(c.dataset.engagementId),
                week_start: c.dataset.week,
                hours: hours,
                color: selectedColor
            });
        }

        fetch('/api/booking/bulk', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ bookings: bookings })
        }).then(function(r) {
            if (r.status === 401 || r.status === 403) { showToast('Yetkiniz yok!'); closeCellPopup(); return null; }
            return r.json();
        }).then(function(res) {
            if (!res) return;
            if (res.success) {
                for (var i = 0; i < selectedCells.length; i++) {
                    updateCellVisual(selectedCells[i], hours, selectedColor);
                }
                closeCellPopup();
                showToast(selectedCells.length + ' hücre güncellendi ✓');
            }
        });
    }
}

function clearCell() {
    var h = document.getElementById('cell-hours');
    if (h) h.value = 0;
    saveCellEdit();
}

function updateCellVisual(cell, hours, color) {
    cell.classList.remove('booked', 'cell-green', 'cell-yellow', 'cell-red', 'cell-selected');
    if (hours > 0) {
        cell.classList.add('booked', 'cell-' + color);
        cell.textContent = Math.round(hours);
    } else {
        cell.textContent = '';
    }
    cell.dataset.hours = hours;
    cell.dataset.color = color;
}

function updateTotalCell(category, week, total) {
    if (!category || total === undefined) return;
    var tc = document.querySelector('.week-total-cell[data-cat="' + category + '"][data-week="' + week + '"]');
    if (tc) {
        var v = Math.round(total);
        tc.textContent = v > 0 ? v : '';
        if (v > 0) tc.classList.add('has-hours');
        else tc.classList.remove('has-hours');
    }
}

// ESC ile kapat, dışarı tıklayınca kapat
document.addEventListener('mousedown', function(e) {
    var popup = document.getElementById('cell-popup');
    if (popup && popup.style.display === 'block' && !popup.contains(e.target) && !e.target.closest('.gantt-cell')) {
        closeCellPopup();
    }
});

document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') closeCellPopup();
    var popup = document.getElementById('cell-popup');
    if (e.key === 'Enter' && popup && popup.style.display === 'block') { e.preventDefault(); saveCellEdit(); }
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') { e.preventDefault(); var s = document.getElementById('quick-search'); if (s) s.focus(); }
});

// Sayfa yüklendiğinde drag'ı başlat
document.addEventListener('DOMContentLoaded', function() {
    initGanttDrag();
});

// ============ FILTER ============
function filterManageList(q, listId) {
    var list = document.getElementById(listId);
    if (!list) return;
    q = q.toLowerCase().trim();
    var items = list.querySelectorAll('.manage-item');
    for (var i = 0; i < items.length; i++) {
        items[i].style.display = items[i].textContent.toLowerCase().indexOf(q) >= 0 ? '' : 'none';
    }
}

// ============ TOAST ============
function showToast(msg, dur) {
    dur = dur || 2200;
    var old = document.querySelector('.toast');
    if (old) old.remove();
    var t = document.createElement('div');
    t.className = 'toast';
    t.textContent = msg;
    document.body.appendChild(t);
    setTimeout(function() {
        t.style.opacity = '0'; t.style.transform = 'translateX(100%)'; t.style.transition = 'all 0.3s';
        setTimeout(function() { t.remove(); }, 300);
    }, dur);
}