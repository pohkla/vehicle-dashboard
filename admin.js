
const $ = (id) => document.getElementById(id);
const excelFile = $('excelFile');
const textFile = $('textFile');
const rawText = $('raw_text');
const excelStatus = $('excelStatus');
const textStatus = $('textStatus');
const pretty = (d) => JSON.stringify(d, null, 2);

function setStatus(el, message, loading=false){
  el.classList.toggle('loading', loading);
  el.textContent = message;
}

document.querySelectorAll('.tab-btn').forEach((btn) => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab-btn').forEach((b) => b.classList.remove('active'));
    document.querySelectorAll('.tab-panel').forEach((p) => p.classList.remove('active'));
    btn.classList.add('active');
    $(btn.dataset.tab).classList.add('active');
  });
});

function bindDrop(zoneId, input, after){
  const zone = $(zoneId);
  zone.addEventListener('click', () => input.click());
  ['dragenter','dragover'].forEach((ev) => zone.addEventListener(ev, (e) => {
    e.preventDefault();
    zone.classList.add('dragover');
  }));
  ['dragleave','drop'].forEach((ev) => zone.addEventListener(ev, (e) => {
    e.preventDefault();
    zone.classList.remove('dragover');
  }));
  zone.addEventListener('drop', (e) => {
    const f = e.dataTransfer.files && e.dataTransfer.files[0];
    if(!f) return;
    const dt = new DataTransfer();
    dt.items.add(f);
    input.files = dt.files;
    after(f);
  });
  input.addEventListener('change', () => {
    const f = input.files && input.files[0];
    if(f) after(f);
  });
}

bindDrop('excelDrop', excelFile, (f) => { $('excelName').textContent = f.name; });
bindDrop('textDrop', textFile, async (f) => {
  $('textName').textContent = f.name;
  rawText.value = await f.text();
});

$('excelBtn').addEventListener('click', async () => {
  const file = excelFile.files && excelFile.files[0];
  if(!file){ setStatus(excelStatus, 'กรุณาเลือกไฟล์ Excel ก่อน'); return; }
  const fd = new FormData();
  fd.append('file', file);
  $('excelBtn').disabled = true;
  setStatus(excelStatus, 'กำลังอัปโหลด Excel → /api/import/excel ...', true);
  try{
    const res = await fetch('/api/import/excel', { method:'POST', body: fd });
    const data = await res.json();
    if(!res.ok){ setStatus(excelStatus, data.detail || pretty(data)); return; }
    setStatus(excelStatus, 'Import Excel สำเร็จ\n' + pretty(data));
  }catch(err){
    setStatus(excelStatus, 'Import Excel ล้มเหลว: ' + err.message);
  }finally{
    $('excelBtn').disabled = false;
    excelStatus.classList.remove('loading');
  }
});

$('textBtn').addEventListener('click', async () => {
  const txt = rawText.value.trim();
  if(!txt){ setStatus(textStatus, 'กรุณาวางข้อความ หรือเลือกไฟล์ .txt ก่อน'); return; }
  const fd = new FormData();
  fd.append('raw_text', txt);
  $('textBtn').disabled = true;
  setStatus(textStatus, 'กำลัง Import Text → /api/import/text ...', true);
  try{
    const res = await fetch('/api/import/text', { method:'POST', body: fd });
    const data = await res.json();
    if(!res.ok){ setStatus(textStatus, data.detail || pretty(data)); return; }
    setStatus(textStatus, 'Import Text สำเร็จ\n' + pretty(data));
  }catch(err){
    setStatus(textStatus, 'Import Text ล้มเหลว: ' + err.message);
  }finally{
    $('textBtn').disabled = false;
    textStatus.classList.remove('loading');
  }
});
