let previewRows = [];
const money = (n) => Number(n || 0).toLocaleString('th-TH', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + ' บาท';
const pct = (n) => `${Math.round(Number(n || 0))}%`;
const cls = (c) => c === 'RVP' ? 'rvp' : c === 'ERGO' ? 'ergo' : c === 'TPB' ? 'tpb' : 'total';

function renderCompanyGrid(summary){
  const grid = document.getElementById('companyGrid');
  const cards = summary.companies || [];
  grid.innerHTML = cards.map(card => {
    const vehicleItems = Object.entries(card.vehicle_types || {})
      .sort((a,b)=>b[1]-a[1])
      .map(([name,count])=>`<div class="vehicle-item"><span>${name}</span><strong>${count} คัน</strong></div>`)
      .join('') || '<div class="vehicle-item"><span>ไม่มีข้อมูล</span><strong>0 คัน</strong></div>';
    return `
      <article class="company-card ${cls(card.company)}">
        <div class="card-title"><span class="dot"></span><span>${card.company === 'TOTAL' ? 'รวม' : card.company}</span></div>
        <div class="main-number">${Number(card.vehicle_count || 0).toLocaleString('th-TH')}</div>
        <div class="label">${card.company === 'TOTAL' ? 'จำนวนรถรวมทั้งหมด' : card.label}</div>
        <div class="money">
          <div class="money-row net"><span>ยอดสุทธิรวม</span><strong>${money(card.net_total)}</strong></div>
          <div class="money-row collected"><span>ยอดเก็บจริงรวม</span><strong>${money(card.collected_total)}</strong></div>
        </div>
        <div class="vehicle-list">
          <div class="vehicle-list-title">จำนวนรถแยกตามประเภทรถ</div>
          ${vehicleItems}
        </div>
        <div class="share">
          <div class="share-head"><span>Share</span><span>${pct(card.share_percent)}</span></div>
          <div class="bar"><span style="width:${Math.min(100, Number(card.share_percent || 0))}%"></span></div>
        </div>
      </article>`;
  }).join('');
}

async function refreshSummary(){
  const res = await fetch('/api/summary');
  if(!res.ok) throw new Error(await res.text());
  renderCompanyGrid(await res.json());
}

async function previewImport(){
  const form = new FormData();
  const file = document.getElementById('fileInput').files[0];
  const text = document.getElementById('textInput').value;
  if(file) form.append('file', file);
  if(text) form.append('text', text);
  const res = await fetch('/api/import/preview', { method:'POST', body: form });
  const data = await res.json();
  if(!res.ok){ document.getElementById('previewBox').textContent = JSON.stringify(data, null, 2); return; }
  previewRows = data.rows || [];
  document.getElementById('previewBox').textContent = JSON.stringify({
    count: previewRows.length,
    errors: data.errors,
    skipped_sheets: data.skipped_sheets,
    summary: data.summary
  }, null, 2);
  if(data.summary) renderCompanyGrid(data.summary);
}

async function savePreview(){
  if(!previewRows.length){ alert('ยังไม่มีข้อมูล Preview'); return; }
  const res = await fetch('/api/import/save', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({ rows: previewRows, replace_all: true })
  });
  const data = await res.json();
  document.getElementById('previewBox').textContent = JSON.stringify(data, null, 2);
  if(data.summary) renderCompanyGrid(data.summary);
}

async function clearData(){
  if(!confirm('ล้างข้อมูลทั้งหมด?')) return;
  const res = await fetch('/api/data', { method:'DELETE' });
  document.getElementById('previewBox').textContent = JSON.stringify(await res.json(), null, 2);
  refreshSummary();
}

refreshSummary().catch(err => {
  document.getElementById('companyGrid').innerHTML = `<div class="panel">โหลดข้อมูลไม่ได้: ${err.message}</div>`;
});
