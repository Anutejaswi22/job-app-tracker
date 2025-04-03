// ✅ Loader + Redirect Function (for Home Page)
function startScan() {
  const btn = document.getElementById('scan-btn');
  if (!btn) return;

  btn.disabled = true;
  btn.innerText = '🔄 Scanning...';
  document.getElementById('loader').style.display = 'block';

  setTimeout(() => {
    window.location.href = '/scan';
  }, 800);
}

function scanWithDates() {
  const from = document.getElementById('from-date').value;
  const to = document.getElementById('to-date').value;

  if (!from || !to) {
    alert('Please select both From and To dates!');
    return;
  }

  const scanBtn = document.getElementById("scan-btn");
  scanBtn.disabled = true;
  scanBtn.innerHTML = `<span class="spinner-orbit"></span> SCANNING...`;

  const loadingNote = document.createElement('p');
  loadingNote.id = "scanning-status";
  loadingNote.innerHTML = `
    <span class="dots-loading">Scanning emails from <b>${from}</b> to <b>${to}</b><span class="dots"></span></span>
  `;
  loadingNote.style.marginTop = "15px";
  loadingNote.style.fontSize = "0.9rem";
  loadingNote.style.color = "#ccc";
  document.querySelector('.button-panel').appendChild(loadingNote);

  window.location.href = `/scan?from=${from}&to=${to}`;
}

document.addEventListener("DOMContentLoaded", () => {
  // ✅ Home Page: Animate job count
  const countElement = document.querySelector('.glow-ball span');
  if (countElement) {
    function animateCount(target, element) {
      let current = 0;
      const interval = setInterval(() => {
        element.textContent = current;
        if (current >= target) {
          clearInterval(interval);
        } else {
          current++;
        }
      }, 50);
    }

    fetch("status.json")
      .then(response => response.json())
      .then(data => {
        const appliedCount = data.applied_count || 0;
        const rejectedCount = data.rejected_count || 0;
        const totalCount = appliedCount + rejectedCount;
        animateCount(totalCount, countElement);
      })
      .catch(error => {
        console.error("❌ Failed to load status.json:", error);
        countElement.textContent = "0";
      });
  }

  // ✅ Applied/Rejected Pages: Sort by clicking header
  const tableHeaders = document.querySelectorAll("th");
  if (tableHeaders.length > 0) {
    tableHeaders.forEach(header => {
      header.addEventListener("click", () => {
        const table = header.closest("table");
        const rows = Array.from(table.querySelectorAll("tr:nth-child(n+2)"));
        const idx = Array.from(header.parentNode.children).indexOf(header);
        const asc = !header.classList.contains("asc");

        rows.sort((a, b) => {
          const dateA = new Date(a.cells[idx].innerText);
          const dateB = new Date(b.cells[idx].innerText);
          return asc ? dateB - dateA : dateA - dateB;
        });

        rows.forEach(row => table.appendChild(row));
        header.classList.toggle("asc", asc);
        header.classList.toggle("desc", !asc);
      });
    });
  }
});