
let report=null,allDays=[],filteredDays=[],viewDays=[],dailyChart=null,rangePickerInstance=null;let currentPage=1,pageSize=8,viewMode='detail',activeSelected='all';const box=id=>document.getElementById(id);const money=n=>Math.round(n||0).toLocaleString('th-TH');function destroy(){if(dailyChart)dailyChart.destroy()}function fmtDate(d){const y=d.getFullYear(),m=String(d.getMonth()+1).padStart(2,'0'),day=String(d.getDate()).padStart(2,'0');return `${y}-${m}-${day}`}function parseISODate(v){const parts=String(v||'').split('-').map(Number);return parts.length===3?new Date(parts[0],parts[1]-1,parts[2]):new Date()}function prettyRange(s,e){if(!s&&!e)return 'ข้อมูลสะสมทั้งหมด';const opt={day:'2-digit',month:'short',year:'numeric'};const a=s?parseISODate(s).toLocaleDateString('en-GB',opt):'เริ่มต้น';const b=e?parseISODate(e).toLocaleDateString('en-GB',opt):'สิ้นสุด';return `${a} → ${b}`}function updateRangeLabel(){const s=box('startDate')?.value||'',e=box('endDate')?.value||'';if(box('rangeDisplayText'))box('rangeDisplayText').textContent=prettyRange(s,e);if(rangePickerInstance&&s&&e)rangePickerInstance.setDate([s,e],false,'Y-m-d')}function setActiveQuick(id){['todayBtn','thisWeekBtn','thisMonthBtn'].forEach(x=>box(x)?.classList.remove('active'));if(id)box(id)?.classList.add('active')}function setRange(start,end,quickId){box('startDate').value=start||'';box('endDate').value=end||'';setActiveQuick(quickId);updateRangeLabel()}function setCurrentMonthDefault(){const now=new Date();setRange(fmtDate(new Date(now.getFullYear(),now.getMonth(),1)),fmtDate(new Date(now.getFullYear(),now.getMonth()+1,0)),'thisMonthBtn')}function setToday(){const now=new Date();setRange(fmtDate(now),fmtDate(now),'todayBtn')}function setThisWeek(){const now=new Date();const day=now.getDay();const diffToMonday=(day===0?-6:1-day);const start=new Date(now);start.setDate(now.getDate()+diffToMonday);const end=new Date(start);end.setDate(start.getDate()+6);setRange(fmtDate(start),fmtDate(end),'thisWeekBtn')}function setupRange(){const dates=allDays.map(d=>d.isoDate).filter(Boolean).sort();if(!box('startDate').value)box('startDate').value=dates[0]||'';if(!box('endDate').value)box('endDate').value=dates[dates.length-1]||'';updateRangeLabel()}function itemText(item){return (item&&typeof item==='object')?(item.text||''):String(item||'')}function itemNet(item){return Number((item&&typeof item==='object')?(item.net_amount||0):0)||0}function itemCollected(item){return Number((item&&typeof item==='object')?(item.collected_amount||0):0)||0}function flattenRows(days){const rows=[];days.forEach(day=>day.groups.forEach(g=>g.items.forEach(item=>rows.push({date:day.date,type:g.title,company:g.company||'',item:itemText(item),net_amount:itemNet(item),collected_amount:itemCollected(item)}))));return rows}
function animateNumber(el,target){const end=Number(target)||0;const start=Number((el.textContent||'0').replace(/,/g,''))||0;const duration=420;const t0=performance.now();function tick(now){const p=Math.min(1,(now-t0)/duration);const eased=1-Math.pow(1-p,3);el.textContent=money(start+(end-start)*eased);if(p<1)requestAnimationFrame(tick);else el.textContent=money(end)}requestAnimationFrame(tick)}
function colorWithAlpha(hex,alpha){const map={'#2563eb':'37,99,235','#dc2626':'220,38,38','#0ea5e9':'14,165,233','#111827':'17,24,39','#94a3b8':'148,163,184'};return `rgba(${map[hex]||'37,99,235'},${alpha})`}function applyChartHighlight(index){if(!dailyChart)return;const colors=['#2563eb','#dc2626','#0ea5e9'];dailyChart.data.datasets.forEach((ds,di)=>{if(ds.type==='line'){ds.borderColor=index==null?'#111827':colorWithAlpha('#111827',.95);ds.backgroundColor=ds.borderColor;ds.pointBackgroundColor=ds.data.map((_,i)=>index==null||i===index?'#111827':colorWithAlpha('#111827',.18));return}ds.backgroundColor=ds.data.map((_,i)=>index==null||i===index?colors[di]:colorWithAlpha(colors[di],.18))});dailyChart.update('none')}
function getCompanyData(){
 return filteredDays.map(day=>{
   let RVP=0, ERGO=0, TPB=0, UNKNOWN=0;
   (day.groups||[]).forEach(g=>{
     const company=(g.company||'').toLowerCase();
     const count=(g.items&&g.items.length)?g.items.length:(g.count||0);
     if(g.key==='motorcycle'){
       RVP += count;
     }else if(company.includes('ergo')){
       ERGO += count;
     }else if(company.includes('ไทยไพบูลย์') || company.includes('tpb')){
       TPB += count;
     }else{
       UNKNOWN += count;
     }
   });
   return {date:day.date,label:day.date.slice(0,5),RVP,ERGO,TPB,UNKNOWN,total:RVP+ERGO+TPB+UNKNOWN};
 });
}

function getCompanySummary(){
 const companyData=getCompanyData();
 return companyData.reduce((acc,d)=>{acc.RVP+=d.RVP;acc.ERGO+=d.ERGO;acc.TPB+=d.TPB;acc.UNKNOWN+=(d.UNKNOWN||0);acc.total+=d.total;return acc;},{RVP:0,ERGO:0,TPB:0,UNKNOWN:0,total:0});
}
function companyKeyFromName(name,key){const c=String(name||'').toLowerCase();if(key==='motorcycle'||c.includes('rvp')||c.includes('บริษัทกลาง'))return 'RVP';if(c.includes('ergo'))return 'ERGO';if(c.includes('ไทยไพบูลย์')||c.includes('tpb'))return 'TPB';return 'UNKNOWN'}
function emptyCompanySummary(){return {count:0,net:0,collected:0,types:{motorcycle:0,pickup:0,sedan:0,other:0}}}
function getCompanyDetailedSummary(){const out={RVP:emptyCompanySummary(),ERGO:emptyCompanySummary(),TPB:emptyCompanySummary(),TOTAL:emptyCompanySummary(),UNKNOWN:emptyCompanySummary()};filteredDays.forEach(day=>{(day.groups||[]).forEach(g=>{const key=companyKeyFromName(g.company,g.key);(g.items||[]).forEach(item=>{const target=out[key]||out.UNKNOWN;const type=(item&&typeof item==='object'&&item.vehicle_type)||g.key||'other';target.count++;target.net+=itemNet(item);target.collected+=itemCollected(item);if(target.types[type]!==undefined)target.types[type]++;else target.types.other++;out.TOTAL.count++;out.TOTAL.net+=itemNet(item);out.TOTAL.collected+=itemCollected(item);if(out.TOTAL.types[type]!==undefined)out.TOTAL.types[type]++;else out.TOTAL.types.other++;})})});return out}
function companyDetailHtml(d){return `<div class="line"><span>🏍 มอเตอร์ไซค์</span><b>${d.types.motorcycle||0} คัน</b></div><div class="line"><span>🚛 กระบะ</span><b>${d.types.pickup||0} คัน</b></div><div class="line"><span>🚗 เก๋ง</span><b>${d.types.sedan||0} คัน</b></div><div class="line"><span>ยอดสุทธิตามระบบ</span><b>${money(d.net)} บาท</b></div><div class="line"><span>ยอดเก็บจริง</span><b>${money(d.collected)} บาท</b></div>`}
function setCompanyKPI(){
 const detail=getCompanyDetailedSummary();
 const s={RVP:detail.RVP.count,ERGO:detail.ERGO.count,TPB:detail.TPB.count,total:detail.TOTAL.count};
 const pct=(v)=>s.total?Math.round((v/s.total)*100):0;
 animateNumber(box('rvpCount'),s.RVP);animateNumber(box('ergoCount'),s.ERGO);animateNumber(box('tpbCount'),s.TPB);animateNumber(box('companyTotalCount'),s.total);
 box('rvpPercent').textContent=pct(s.RVP)+'%';box('ergoPercent').textContent=pct(s.ERGO)+'%';box('tpbPercent').textContent=pct(s.TPB)+'%';
 box('rvpBar').style.width=pct(s.RVP)+'%';box('ergoBar').style.width=pct(s.ERGO)+'%';box('tpbBar').style.width=pct(s.TPB)+'%';
 if(box('rvpDetail'))box('rvpDetail').innerHTML=companyDetailHtml(detail.RVP);if(box('ergoDetail'))box('ergoDetail').innerHTML=companyDetailHtml(detail.ERGO);if(box('tpbDetail'))box('tpbDetail').innerHTML=companyDetailHtml(detail.TPB);if(box('totalDetail'))box('totalDetail').innerHTML=companyDetailHtml(detail.TOTAL);
}
function colorWithAlpha(hex,alpha){const map={'#2563eb':'37,99,235','#dc2626':'220,38,38','#0ea5e9':'14,165,233','#111827':'17,24,39','#94a3b8':'148,163,184'};return `rgba(${map[hex]||'37,99,235'},${alpha})`}
function setCompanyCardsState(company){document.querySelectorAll('.company-kpi').forEach(card=>{const c=card.dataset.company;card.classList.toggle('active',!!company&&c===company);card.classList.toggle('dim',!!company&&c!==company&&company!=='TOTAL')})}
function highlightCompany(company){
 setCompanyCardsState(company);
 if(!dailyChart)return;
 const colorMap={RVP:'#2563eb',ERGO:'#dc2626',TPB:'#0ea5e9',UNKNOWN:'#94a3b8'};
 dailyChart.data.datasets.forEach(ds=>{
   const label=ds.label||'';
   if(ds.type==='line'){const active=!company||company==='TOTAL';ds.borderColor=active?'#111827':colorWithAlpha('#111827',.18);ds.backgroundColor=ds.borderColor;ds.pointBackgroundColor=ds.data.map(()=>active?'#111827':colorWithAlpha('#111827',.18));return}
   let key='UNKNOWN';if(label.includes('RVP'))key='RVP';if(label.includes('ERGO'))key='ERGO';if(label.includes('TPB'))key='TPB';
   const active=!company||company==='TOTAL'||company===key;const base=colorMap[key]||'#94a3b8';ds.backgroundColor=ds.data.map(()=>active?base:colorWithAlpha(base,.16));
 });
 dailyChart.update('none');
}
function renderCharts(){return}
function renderBreakdown(motor,pickup,sedan,total){box('hybridTotal').textContent=money(total);const rows=[{icon:'🏍',label:'รถจักรยานยนต์',value:motor,cls:''},{icon:'🚛',label:'รถกระบะ',value:pickup,cls:'orange'},{icon:'🚗',label:'รถยนต์เก๋ง',value:sedan,cls:'green'}];box('breakdownList').innerHTML=rows.map(r=>{const pct=total?Math.round((r.value/total)*100):0;return `<div class="breakdown-row"><div class="break-left"><span>${r.icon}</span><span>${r.label}</span></div><div class="break-meta"><span>${money(r.value)}</span><span class="percent">${pct}%</span></div><div class="bar-track"><div class="bar-fill ${r.cls}" style="width:${pct}%"></div></div></div>`}).join('')}
function render(selected='all'){
 const t=report.totals||{};
 const motor=t.motorcycle||0,pickup=t.pickup||0,sedan=t.sedan||0,total=t.all||0;
 const net=report.amounts?.net||{};
 const collected=report.amounts?.collected||{};
 box('period').textContent=report.period||'📊 Dashboard ข้อมูลสะสมทั้งหมด';
 box('netTotalAmount').textContent=money(collected.total)+' บาท';
 box('collectedTotalAmount').textContent=money(net.total)+' บาท';
 box('pickupNetAmount').textContent=money(net.pickup)+' บาท';
 box('pickupCollectedAmount').textContent=money(collected.pickup)+' บาท';
 box('sedanNetAmount').textContent=money(net.sedan)+' บาท';
 box('sedanCollectedAmount').textContent=money(collected.sedan)+' บาท';
 box('carNetAmount').textContent=money(net.car)+' บาท';
 box('carCollectedAmount').textContent=money(collected.car)+' บาท';
 box('motorNetAmount').textContent=money(net.motorcycle)+' บาท';
 box('motorCollectedAmount').textContent=money(collected.motorcycle)+' บาท';
 box('dateFilter').innerHTML='<option value="all">ดูทั้งหมด</option>'+filteredDays.map(d=>`<option value="${d.date}">${d.date}</option>`).join('');
 renderCharts();
 setCompanyKPI();
 renderBreakdown(motor,pickup,sedan,total);
 currentPage=1;
 renderCards(selected);
 const sr=report.selectedRange||{};const rangeText=(sr.start&&sr.end)?`ช่วงวันที่ ${sr.start} ถึง ${sr.end}`:'ข้อมูลสะสมทั้งหมด';box('status').textContent=`${rangeText} • จำนวนรถ ${total} คัน • แสดง ${filteredDays.length}/${allDays.length} วัน`;
}
function getCardList(selected='all'){const base=selected==='all'?filteredDays:filteredDays.filter(d=>d.date===selected);const q=box('searchBox').value.trim().toLowerCase();if(!q)return base;return base.map(day=>{const groups=day.groups.map(g=>{const items=g.items.filter(i=>(day.date+' '+g.title+' '+(g.company||'')+' '+itemText(i)).toLowerCase().includes(q));return {...g,items,count:items.length}}).filter(g=>g.items.length);return {...day,groups,motorcycle:groups.filter(g=>g.key==='motorcycle').reduce((s,g)=>s+g.items.length,0),pickup:groups.filter(g=>g.key==='pickup').reduce((s,g)=>s+g.items.length,0),sedan:groups.filter(g=>g.key==='sedan').reduce((s,g)=>s+g.items.length,0)}}).filter(d=>d.groups.length)}
function getDayMeta(list,day){const totals=list.map(d=>d.motorcycle+d.pickup+d.sedan);const max=Math.max(...totals,0),min=Math.min(...totals,0);const total=day.motorcycle+day.pickup+day.sedan;let tags=[],cls=[];if(total===max&&max>0){tags.push('🔥 Peak');cls.push('peak','high')}else if(total>=max*.75&&max>0){tags.push('เด่น');cls.push('high')}if(total===min&&list.length>1){tags.push('Low');cls.push('low')}return {total,tags,cls:cls.join(' ')}}
function sumItems(items){return (items||[]).reduce((acc,item)=>{acc.net+=itemNet(item);acc.collected+=itemCollected(item);return acc},{net:0,collected:0})}
function sumDay(day){return (day.groups||[]).reduce((acc,g)=>{const s=sumItems(g.items);acc.net+=s.net;acc.collected+=s.collected;return acc},{net:0,collected:0})}
function amountLine(net,collected){return `<div class="item-money"><span class="net">ยอดสุทธิ ${money(net)} บาท</span><span class="collected">ยอดเก็บจริง ${money(collected)} บาท</span></div>`}
function buildDetails(day){const daySum=sumDay(day);return `<div class="day-money-summary"><div class="money-pill net"><span>ยอดสุทธิตามระบบ</span><strong>${money(daySum.net)} บาท</strong><small>รวมทุกคัน</small></div><div class="money-pill collected"><span>ยอดเงินรวมประจำวัน</span><strong>${money(daySum.collected)} บาท</strong><small>ยอดเก็บจริง</small></div></div>`+day.groups.map(g=>{const gSum=sumItems(g.items);return `<div class="vehicle-group"><div class="vehicle-title vehicle-title-row"><span>${g.icon} ${g.title} (${g.items.length} คัน)</span><span class="vehicle-money"><span class="money-chip net">สุทธิ ${money(gSum.net)} บาท</span><span class="money-chip collected">เก็บจริง ${money(gSum.collected)} บาท</span></span></div>${g.company?`<span class="company">${g.company}</span>`:''}<ul>${g.items.map(i=>`<li><div class="vehicle-item-row"><span>${itemText(i)}</span>${amountLine(itemNet(i),itemCollected(i))}</div></li>`).join('')}</ul></div>`}).join('')}
function toggleDay(btn,index){const card=btn.closest('.day-card');const body=card.querySelector('.day-body');if(card.classList.contains('open')){card.classList.remove('open');return}if(!body.dataset.loaded){const day=viewDays[index];body.innerHTML=buildDetails(day);body.dataset.loaded='1'}card.classList.add('open')}
function renderCards(selected='all'){activeSelected=selected;const list=getCardList(selected);viewDays=list;const totalPages=Math.max(1,Math.ceil(list.length/pageSize));if(currentPage>totalPages)currentPage=totalPages;const start=(currentPage-1)*pageSize;const pageItems=list.slice(start,start+pageSize);box('cards').classList.toggle('compact',viewMode==='compact');box('pageInfo').textContent=`หน้า ${currentPage}/${totalPages} • แสดง ${pageItems.length}/${list.length} วัน`;box('prevPageBtn').disabled=currentPage<=1;box('nextPageBtn').disabled=currentPage>=totalPages;if(!pageItems.length){box('cards').innerHTML='<article class="day-card"><button class="day-head"><span class="day-title">ไม่พบข้อมูล</span></button></article>';return}box('cards').innerHTML=pageItems.map((day,idx)=>{const globalIndex=start+idx;const meta=getDayMeta(list,day);const compact=viewMode==='compact';const open=!compact&&idx<2;const tags=meta.tags.map(t=>`<span class="badge ${t.includes('Peak')?'tag-peak':t.includes('Low')?'tag-low':'tag-high'}">${t}</span>`).join('');const summary=`<div class="quick-summary"><span class="mini-chip">🏍 ${day.motorcycle}</span><span class="mini-chip">🚛 ${day.pickup}</span><span class="mini-chip">🚗 ${day.sedan}</span></div>`;const bodyContent=open?buildDetails(day):'';return `<article class="day-card ${meta.cls} ${compact?'compact-card':''} ${open?'open':''}"><button class="day-head" onclick="toggleDay(this,${globalIndex})"><span class="day-main"><span class="day-title">📊 วันที่ ${day.date}</span>${summary}</span><span class="day-tags">${tags}<span class="badge">รวม ${meta.total} คัน</span><span class="chev">⌄</span></span></button><div class="day-body" data-loaded="${open?'1':''}">${bodyContent}</div></article>`}).join('')}
function exportExcel(){
 const safeText=(id,fallback='0')=>box(id)?.textContent?.replace(' บาท','')||fallback;
 const rows=flattenRows(viewDays.length?viewDays:filteredDays);
 const sourceDays=(viewDays.length?viewDays:filteredDays)||[];
 const counts=sourceDays.reduce((acc,day)=>{
   acc.motorcycle+=Number(day.motorcycle||0);
   acc.pickup+=Number(day.pickup||0);
   acc.sedan+=Number(day.sedan||0);
   return acc;
 },{motorcycle:0,pickup:0,sedan:0});
 counts.all=counts.motorcycle+counts.pickup+counts.sedan;
 const summaryRows=[
  {หมวด:'ยอดเก็บจริงรวมทั้งหมด',ยอด:safeText('netTotalAmount'),หน่วย:'บาท'},
  {หมวด:'ยอดสุทธิตามระบบรวมทั้งหมด',ยอด:safeText('collectedTotalAmount'),หน่วย:'บาท'},
  {หมวด:'รถกระบะ - ยอดสุทธิ',ยอด:safeText('pickupNetAmount'),หน่วย:'บาท'},
  {หมวด:'รถกระบะ - ยอดเก็บจริง',ยอด:safeText('pickupCollectedAmount'),หน่วย:'บาท'},
  {หมวด:'รถยนต์เก๋ง - ยอดสุทธิ',ยอด:safeText('sedanNetAmount'),หน่วย:'บาท'},
  {หมวด:'รถยนต์เก๋ง - ยอดเก็บจริง',ยอด:safeText('sedanCollectedAmount'),หน่วย:'บาท'},
  {หมวด:'รถยนต์รวม - ยอดสุทธิ',ยอด:safeText('carNetAmount'),หน่วย:'บาท'},
  {หมวด:'รถยนต์รวม - ยอดเก็บจริง',ยอด:safeText('carCollectedAmount'),หน่วย:'บาท'},
  {หมวด:'รถจักรยานยนต์ - ยอดสุทธิ',ยอด:safeText('motorNetAmount'),หน่วย:'บาท'},
  {หมวด:'รถจักรยานยนต์ - ยอดเก็บจริง',ยอด:safeText('motorCollectedAmount'),หน่วย:'บาท'},
  {หมวด:'รถจักรยานยนต์',ยอด:counts.motorcycle,หน่วย:'คัน'},
  {หมวด:'รถกระบะ',ยอด:counts.pickup,หน่วย:'คัน'},
  {หมวด:'รถยนต์เก๋ง',ยอด:counts.sedan,หน่วย:'คัน'},
  {หมวด:'จำนวนรถรวมทั้งหมด',ยอด:counts.all,หน่วย:'คัน'}
 ];
 const wsSummary=XLSX.utils.json_to_sheet(summaryRows);
 const wsDetail=XLSX.utils.json_to_sheet(rows.map(r=>({วันที่:r.date,ประเภทรถ:r.type,บริษัท:r.company,รายการ:r.item,ยอดสุทธิตามระบบ:r.net_amount,ยอดเก็บจริง:r.collected_amount})));
 const wb=XLSX.utils.book_new();
 XLSX.utils.book_append_sheet(wb,wsSummary,'Summary');
 XLSX.utils.book_append_sheet(wb,wsDetail,'Detail');
 XLSX.writeFile(wb,'vehicle-dashboard.xlsx')
}
function escapeHtml(text){return String(text||'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'","&#039;")}
function exportPDF(){
 const rows=flattenRows(viewDays.length?viewDays:filteredDays);
 const printedAt=new Date().toLocaleString('th-TH');
 const totalAmount=box('netTotalAmount')?.textContent||'0';
 const netAmount=box('collectedTotalAmount')?.textContent||'0';
 const html=`<!DOCTYPE html><html lang="th"><head><meta charset="UTF-8"><title>Vehicle Dashboard PDF</title><style>body{font-family:Arial,sans-serif;padding:24px;color:#172033}h1{margin:0 0 8px}table{width:100%;border-collapse:collapse;font-size:12px}th,td{border-bottom:1px solid #ddd;padding:8px;text-align:left}.summary{display:flex;gap:12px;margin:16px 0}.card{border:1px solid #ddd;border-radius:12px;padding:12px;min-width:160px}.value{font-size:24px;font-weight:800;color:#2563eb}</style></head><body><h1>Vehicle Dashboard</h1><div>Export: ${escapeHtml(printedAt)}</div><div class="summary"><div class="card">ยอดเก็บจริง<div class="value">${escapeHtml(totalAmount)}</div></div><div class="card">ยอดสุทธิตามระบบ<div class="value">${escapeHtml(netAmount)}</div></div></div><table><thead><tr><th>วันที่</th><th>ประเภทรถ</th><th>บริษัท</th><th>รายการ</th><th>ยอดสุทธิ</th><th>ยอดเก็บจริง</th></tr></thead><tbody>${rows.map(r=>`<tr><td>${escapeHtml(r.date)}</td><td>${escapeHtml(r.type)}</td><td>${escapeHtml(r.company)}</td><td>${escapeHtml(r.item)}</td><td>${escapeHtml(r.net_amount)}</td><td>${escapeHtml(r.collected_amount)}</td></tr>`).join('')}</tbody></table></body></html>`;
 const win=window.open('', '_blank');
 if(!win){alert('Browser บล็อก popup กรุณาอนุญาต popup แล้วลอง Export PDF อีกครั้ง');return}
 win.document.open();win.document.write(html);win.document.close();win.focus();setTimeout(()=>win.print(),700);
}
function showLoading(msg='กำลังโหลดข้อมูล...'){const t=box('loadingText'),o=box('loadingOverlay');if(t)t.textContent=msg;if(o)o.classList.add('show')}function hideLoading(){const o=box('loadingOverlay');if(o)o.classList.remove('show')}
async function load(){showLoading('กำลังค้นหาและอัปเดต Dashboard...');box('refreshStatus').textContent='กำลังโหลดข้อมูล...';try{const params=new URLSearchParams();const s=box('startDate').value,e=box('endDate').value,q=(box('searchBox')?box('searchBox').value.trim():'');if(s)params.set('start',s);if(e)params.set('end',e);if(q)params.set('q',q);const query=params.toString();const url='/api/dashboard'+(query?('?'+query+'&ts='+Date.now()):('?ts='+Date.now()));const res=await fetch(url).catch(()=>null);if(!res||!res.ok){box('status').textContent='ยังไม่มีข้อมูล';box('refreshStatus').textContent='ยังไม่มีข้อมูล';return}report=await res.json();allDays=report.dailyData;filteredDays=[...allDays];if(!s&&!e)setupRange();render(activeSelected);box('refreshStatus').textContent='ข้อมูลล่าสุดแล้ว • '+new Date().toLocaleTimeString('th-TH')+' • Auto refresh ทุก 15 นาที'}finally{hideLoading()}}
box('applyBtn').onclick=()=>load();box('resetBtn').onclick=()=>{setRange('','','');if(box('searchBox'))box('searchBox').value='';activeSelected='all';load()};box('showDateBtn').onclick=()=>{currentPage=1;renderCards(box('dateFilter').value)};box('showAllBtn').onclick=()=>{box('dateFilter').value='all';currentPage=1;renderCards('all')};box('dateFilter').onchange=()=>{currentPage=1;renderCards(box('dateFilter').value)};if(box('searchBox'))box('searchBox').oninput=()=>{currentPage=1;clearTimeout(window.searchTimer);window.searchTimer=setTimeout(()=>load(),450)};box('prevPageBtn').onclick=()=>{if(currentPage>1){currentPage--;renderCards(box('dateFilter').value)}};box('nextPageBtn').onclick=()=>{currentPage++;renderCards(box('dateFilter').value)};box('detailModeBtn').onclick=()=>{viewMode='detail';box('detailModeBtn').classList.add('active');box('compactModeBtn').classList.remove('active');renderCards(box('dateFilter').value)};box('compactModeBtn').onclick=()=>{viewMode='compact';box('compactModeBtn').classList.add('active');box('detailModeBtn').classList.remove('active');renderCards(box('dateFilter').value)};box('exportExcelBtn').onclick=exportExcel;box('exportPdfBtn').onclick=exportPDF;function initModernDatePicker(){if(window.flatpickr){rangePickerInstance=flatpickr('#rangePicker',{mode:'range',dateFormat:'Y-m-d',altInput:false,allowInput:false,disableMobile:true,onChange:(dates,txt,inst)=>{if(dates.length===2){setRange(fmtDate(dates[0]),fmtDate(dates[1]),'');load()}},onClose:(dates)=>{if(dates.length===1){setRange(fmtDate(dates[0]),fmtDate(dates[0]),'');load()}}});}}if(box('rangeOpenBtn'))box('rangeOpenBtn').onclick=()=>rangePickerInstance?.open();if(box('thisMonthBtn'))box('thisMonthBtn').onclick=()=>{setCurrentMonthDefault();load()};if(box('todayBtn'))box('todayBtn').onclick=()=>{setToday();load()};if(box('thisWeekBtn'))box('thisWeekBtn').onclick=()=>{setThisWeek();load()};initModernDatePicker();setCurrentMonthDefault();load();setInterval(()=>load(),900000);
