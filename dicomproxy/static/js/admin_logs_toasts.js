(function(){
  if(!location.pathname.match(/\/admin\/dashboard\/logs\/?$/)) return;

  // Toast infra
  (function ensureToastInfra(){
    if(!document.getElementById('toast-root')){
      const root = document.createElement('div'); root.id='toast-root'; document.body.appendChild(root);
    }
    const href = '/static/css/admin_toasts.css';
    const found = Array.from(document.styleSheets||[]).some(ss => (ss.href||'').includes(href));
    if(!found){ const link=document.createElement('link'); link.rel='stylesheet'; link.href=href; document.head.appendChild(link); }
  })();

  const root = document.getElementById('toast-root');
  function showToast(message, type, title, timeoutMs){
    type = type || 'info';
    title = title || (type==='success'?'Éxito': type==='error'?'Error': type==='warn'?'Atención':'Información');
    timeoutMs = timeoutMs || 2200;
    const el = document.createElement('div');
    el.className = 'toast '+type;
    el.innerHTML = '<div><p class="title">'+title+'</p><p class="msg">'+message+'</p></div><button class="close" aria-label="Cerrar">&times;</button>';
    root.appendChild(el);
    const closer = el.querySelector('.close');
    const remove = ()=>{ el.style.animation='toast-out .18s ease-in forwards'; setTimeout(()=>el.remove(),180); };
    closer.addEventListener('click', remove);
    setTimeout(remove, timeoutMs);
  }

  async function trace(event, field, value, context){
    try{
      await fetch('/admin/dashboard/logs/trace', {
        method:'POST',
        headers:{'Content-Type':'application/json','X-Requested-With':'fetch'},
        body: JSON.stringify({event, field, value, context: context||{}}),
        keepalive: true
      });
    }catch(e){}
  }

  // Controles reales del template original
  const form      = document.querySelector('form[action*="/admin/dashboard/logs"]') || document.querySelector('form');
  const selFile   = document.querySelector('select[name="file"], #log_file, [data-role="log-file"]');
  const selLevel  = document.querySelector('select[name="level"], #level, [data-role="log-level"]');
  const inSearch  = document.querySelector('input[name="search"], #q, [data-role="log-search"]');
  let   btnApply  = document.querySelector('form[action*="/admin/dashboard/logs"] button[type="submit"]');
  if(!btnApply){
    btnApply = Array.from(document.querySelectorAll('button, input[type="submit"], input[type="button"]'))
      .find(b => (b.textContent||b.value||'').trim().toLowerCase() === 'aplicar filtros');
  }
  let   btnGoCurrent = document.querySelector('#btn-go-current, [data-role="go-current"]');
  if(!btnGoCurrent){
    btnGoCurrent = Array.from(document.querySelectorAll('a,button'))
      .find(b => (b.textContent||'').trim().toLowerCase()==='ir al log actual');
  }

  // Utilidad: interceptar submit inmediato, mostrar toast y luego enviar
  function delayedSubmit(delay){
    if(!form) return;
    setTimeout(()=> form.submit(), delay||220);
  }

  // FILE: muchos templates auto-envían el form onChange; prevenimos y re-enviamos tras toast
  if(selFile){
    selFile.addEventListener('change', (e)=>{
      const v = e.target.value || '(vacío)';
      // Cancelar cualquier manejador de envío inmediato
      e.preventDefault(); e.stopImmediatePropagation();
      showToast('Archivo seleccionado: <strong>'+v+'</strong>', 'info', 'Filtro actualizado');
      trace('change','file',v,{ts:Date.now()});
      delayedSubmit(220);
    }, {capture:true});
  }

  // LEVEL: igual que FILE
  if(selLevel){
    selLevel.addEventListener('change', (e)=>{
      const v = e.target.value || '(Todos)';
      e.preventDefault(); e.stopImmediatePropagation();
      showToast('Nivel de log: <strong>'+v+'</strong>', 'info', 'Filtro actualizado');
      trace('change','level',v,{ts:Date.now()});
      delayedSubmit(220);
    }, {capture:true});
  }

  // SEARCH: Enter hace submit inmediato -> lo interceptamos
  if(inSearch){
    let last = inSearch.value||'';
    inSearch.addEventListener('keydown', (e)=>{
      if(e.key==='Enter'){
        e.preventDefault(); e.stopImmediatePropagation();
        const v = inSearch.value.trim();
        showToast('Búsqueda: “'+(v||'—')+'”', 'info', 'Filtro actualizado');
        trace('change','search',v,{ts:Date.now(), enter:true});
        delayedSubmit(200);
      }
    }, {capture:true});
    // blur sólo muestra toast, no envía
    inSearch.addEventListener('blur', ()=>{
      if(inSearch.value!==last){
        last = inSearch.value;
        const v = (last||'').trim();
        showToast('Búsqueda: “'+(v||'—')+'”', 'info', 'Filtro actualizado');
        trace('change','search',v,{ts:Date.now(), blur:true});
      }
    });
  }

  // APLICAR FILTROS: evitar recarga instantánea, mostrar toast, trazar y luego submit
  if(btnApply){
    btnApply.addEventListener('click', (e)=>{
      e.preventDefault(); e.stopImmediatePropagation();
      const payload = {
        file: selFile? selFile.value:null,
        level: selLevel? selLevel.value:null,
        search: inSearch? inSearch.value:null
      };
      showToast('Aplicando filtros…', 'success', 'Acción');
      trace('submit','apply', JSON.stringify(payload), {ts:Date.now()});
      delayedSubmit(180);
    }, {capture:true});
  }

  // IR AL LOG ACTUAL: sólo retrasamos la navegación para que se vea el toast
  if(btnGoCurrent){
    btnGoCurrent.addEventListener('click', (e)=>{
      showToast('Abriendo log actual…', 'success', 'Acción');
      trace('navigate','go_current', null, {ts:Date.now()});
      // si es <a>, dejamos que navegue; si es botón con data-href, retrasamos un poco
      const href = btnGoCurrent.getAttribute('href') || btnGoCurrent.getAttribute('data-href');
      if(href && !btnGoCurrent.matches('a')){
        e.preventDefault(); e.stopImmediatePropagation();
        setTimeout(()=>{ location.href = href; }, 220);
      }
    }, {capture:true});
  }

  // Avisos por querystring provenientes del backend (ya funcionaban en tu caso)
  const params = new URLSearchParams(location.search);
  const t = params.get('toast'); const tt = params.get('toast_type');
  if(t){ showToast(t, tt||'info'); trace('notice', tt||'info', t, {ts:Date.now()}); }
})();
