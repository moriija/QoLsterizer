(function(){

  var state = {
    rows: [],
    variables: [],
    variableMap: {},
    decisions: {},
    autoFlags: {},
    datasetKey: null,
    sourceNames: [],
    filter: 'all',
    search: '',
    onlyDistritos: true,
    thresholds: { minDistrictPct: 50, maxNullPct: 30 }
  };

  function loadThresholds(){
    var t = { minDistrictPct: 50, maxNullPct: 30 };
    try{
      var a = localStorage.getItem('observa_min_district_pct');
      var b = localStorage.getItem('observa_max_null_pct');
      if (a !== null && a !== '' && !isNaN(Number(a))) t.minDistrictPct = Number(a);
      if (b !== null && b !== '' && !isNaN(Number(b))) t.maxNullPct = Number(b);
    }catch(e){ /* ignore — defaults stand */ }
    return t;
  }

  function saveThresholds(t){
    try{
      localStorage.setItem('observa_min_district_pct', String(t.minDistrictPct));
      localStorage.setItem('observa_max_null_pct', String(t.maxNullPct));
    }catch(e){ /* storage unavailable — thresholds just won't persist */ }
  }

  function clampPct(n, fallback){
    n = Number(n);
    if (isNaN(n)) return fallback;
    return Math.min(100, Math.max(0, n));
  }

  (function initThresholds(){
    state.thresholds = loadThresholds();
    var minEl = document.getElementById('minDistrictPct');
    var maxEl = document.getElementById('maxNullPct');
    minEl.value = state.thresholds.minDistrictPct;
    maxEl.value = state.thresholds.maxNullPct;

    function onThresholdChange(){
      state.thresholds = {
        minDistrictPct: clampPct(minEl.value, state.thresholds.minDistrictPct),
        maxNullPct: clampPct(maxEl.value, state.thresholds.maxNullPct)
      };
      minEl.value = state.thresholds.minDistrictPct;
      maxEl.value = state.thresholds.maxNullPct;
      saveThresholds(state.thresholds);
      if (state.rows && state.rows.length) applyAutoMarking(false);
    }
    minEl.addEventListener('change', onThresholdChange);
    maxEl.addEventListener('change', onThresholdChange);

    document.getElementById('applyAutoBtn').addEventListener('click', function(){
      if (!state.rows || !state.rows.length){
        document.getElementById('autoNote').textContent = 'Carregue um conjunto de dados primeiro.';
        return;
      }
      applyAutoMarking(false);
    });
  })();

  (function initOnlyDistritosToggle(){
    try{
      var saved = localStorage.getItem('observa_only_distritos');
      if (saved !== null) state.onlyDistritos = saved === '1';
    }catch(e){ /* ignore — default stays true */ }
    var el = document.getElementById('onlyDistritosToggle');
    el.checked = state.onlyDistritos;
    el.addEventListener('change', function(){
      state.onlyDistritos = el.checked;
      try{ localStorage.setItem('observa_only_distritos', state.onlyDistritos ? '1' : '0'); }catch(e){}
      if (state.rows && state.rows.length) rebuildView();
    });
  })();

  var downloadsApi = null;
  (function initDownloads(){
    try{
      if (window.claude && typeof window.claude.use === 'function'){
        window.claude.use('downloads').then(function(ns){
          downloadsApi = ns;
          updateExportButtons();
        }).catch(function(){ downloadsApi = null; updateExportButtons(); });
      } else {
        updateExportButtons();
      }
    }catch(e){ downloadsApi = null; updateExportButtons(); }
  })();

  var COLUMN_HINTS = {
    nome: ['nome','variavel','variável','indicador'],
    regiao: ['regi'],
    periodo: ['per'],
    resultado: ['result','valor']
  };

  function norm(s){ return (s||'').trim().toLowerCase(); }

  function detectColumns(header){
    var normed = header.map(norm);
    var map = {};
    for (var logical in COLUMN_HINTS){
      var hints = COLUMN_HINTS[logical];
      var found = -1;
      for (var i=0;i<normed.length;i++){
        for (var j=0;j<hints.length;j++){
          if (normed[i].indexOf(hints[j]) !== -1){ found = i; break; }
        }
        if (found !== -1) break;
      }
      if (found === -1) return null;
      map[logical] = found;
    }
    return map;
  }

  // Small state-machine CSV parser: handles quotes, CRLF/LF, and either ; or , delimiter.
  function parseCSV(text, delimiter){
    var rows = [];
    var row = [];
    var field = '';
    var inQuotes = false;
    var i = 0, len = text.length;
    while (i < len){
      var c = text[i];
      if (inQuotes){
        if (c === '"'){
          if (text[i+1] === '"'){ field += '"'; i += 2; continue; }
          inQuotes = false; i++; continue;
        }
        field += c; i++; continue;
      } else {
        if (c === '"'){ inQuotes = true; i++; continue; }
        if (c === delimiter){ row.push(field); field=''; i++; continue; }
        if (c === '\r'){ i++; continue; }
        if (c === '\n'){ row.push(field); rows.push(row); row=[]; field=''; i++; continue; }
        field += c; i++; continue;
      }
    }
    if (field.length || row.length){ row.push(field); rows.push(row); }
    return rows;
  }

  function sniffDelimiter(sampleLine){
    var semi = (sampleLine.match(/;/g)||[]).length;
    var comma = (sampleLine.match(/,/g)||[]).length;
    return semi >= comma ? ';' : ',';
  }

  function stripBOM(text){
    if (text.charCodeAt(0) === 0xFEFF) return text.slice(1);
    return text;
  }

  // Loads a CSV in either format:
  //   long : Nome;Região;Período;Resultado
  //   wide : Período;tipo_regiao;Distrito;<indicador 1>;<indicador 2>;...
  // Wide files are pivoted into the same {nome, regiao, periodo, resultado}
  // records; empty cells (no data) are skipped.
  function rowsFromCSVText(text){
    text = stripBOM(text);
    var firstLineEnd = text.indexOf('\n');
    var sample = firstLineEnd === -1 ? text : text.slice(0, firstLineEnd);
    var delim = sniffDelimiter(sample);
    var table = parseCSV(text, delim);
    if (!table.length) return [];
    var header = table[0];
    // A long-format header has 4 columns; anything much wider is a wide file.
    var colmap = header.length > 6 ? null : detectColumns(header);
    if (!colmap) return rowsFromWideTable(table);

    var out = [];
    for (var i=1;i<table.length;i++){
      var r = table[i];
      if (!r || r.length===0 || (r.length===1 && r[0]==='')) continue;
      var nome = (r[colmap.nome]||'').trim();
      var regiao = (r[colmap.regiao]||'').trim();
      var periodoRaw = (r[colmap.periodo]||'').trim();
      var resultado = (r[colmap.resultado]||'').trim();
      var m = periodoRaw.match(/-?\d+/);
      if (!nome || !m) continue;
      out.push({ nome:nome, regiao:regiao, periodo:parseInt(m[0],10), resultado:resultado });
    }
    return out;
  }

  function rowsFromWideTable(table){
    var header = table[0];
    var normed = header.map(norm);
    var head = Math.min(5, normed.length);
    var per = -1, tipo = -1, nome = -1, i;

    for (i=0;i<head;i++){
      if (normed[i]==='período' || normed[i]==='periodo' || normed[i]==='ano'){ per = i; break; }
    }
    if (per === -1){
      for (i=0;i<head;i++){ if (normed[i].indexOf('per') === 0){ per = i; break; } }
    }
    if (per === -1){
      throw new Error('Não encontrei a coluna de período (Período/Ano) no cabeçalho.');
    }
    for (i=0;i<head;i++){
      if (i !== per && normed[i].indexOf('tipo') !== -1){ tipo = i; break; }
    }
    var nameHints = ['distrito','subprefeitura','munic','regi','nome'];
    for (i=0;i<head && nome === -1;i++){
      if (i === per || i === tipo) continue;
      if (nameHints.some(function(h){ return normed[i].indexOf(h) !== -1; })) nome = i;
    }
    if (nome === -1){
      for (i=0;i<head;i++){ if (i !== per && i !== tipo){ nome = i; break; } }
    }
    if (nome === -1){
      throw new Error('Não encontrei a coluna com o nome da região no cabeçalho.');
    }

    var indicators = [];
    for (i=0;i<header.length;i++){
      if (i === per || i === tipo || i === nome) continue;
      var nm = (header[i]||'').trim();
      if (nm) indicators.push({ idx:i, nome:nm });
    }

    var out = [];
    for (var ri=1; ri<table.length; ri++){
      var r = table[ri];
      if (!r || r.length===0 || (r.length===1 && r[0]==='')) continue;
      var m = (r[per]||'').match(/-?\d+/);
      var nomeRegiao = (r[nome]||'').trim();
      if (!m || !nomeRegiao) continue;
      var periodo = parseInt(m[0],10);
      var tipoRegiao = tipo === -1 ? '' : (r[tipo]||'').trim();
      var regiao = tipoRegiao ? nomeRegiao + ' (' + tipoRegiao + ')' : nomeRegiao;
      for (var k=0;k<indicators.length;k++){
        var val = (r[indicators[k].idx]||'').trim();
        if (!hasValue(val)) continue;
        out.push({ nome:indicators[k].nome, regiao:regiao, periodo:periodo, resultado:val });
      }
    }
    return out;
  }
  
  function rowsFromJSON(obj){
    var out = [];
    if (obj && obj.variables){
      obj.variables.forEach(function(v){
        var regions = v.regions || {};
        for (var regiao in regions){
          regions[regiao].forEach(function(pair){
            out.push({ nome:v.nome, regiao:regiao, periodo:pair[0], resultado:String(pair[1]) });
          });
        }
      });
    }
    return out;
  }

  function regionType(regiao){
    var m = regiao.match(/\(([^)]+)\)\s*$/);
    return m ? m[1] : 'Outro';
  }

  // Treats "Distrito" (any case/accent) as a district; Município, Subprefeitura
  // and anything else are not — used to filter dados_filtrados.csv.
  function isDistrito(regiao){
    return regionType(regiao).trim().toLowerCase() === 'distrito';
  }

  function formatYearRanges(years){
    var uniq = Array.from(new Set(years)).sort(function(a,b){return a-b;});
    if (!uniq.length) return 'sem dados';
    var parts = [];
    var start = uniq[0], prev = uniq[0];
    for (var i=1;i<uniq.length;i++){
      var y = uniq[i];
      if (y === prev+1){ prev = y; continue; }
      parts.push(start===prev ? (''+start) : (start+'-'+prev));
      start = prev = y;
    }
    parts.push(start===prev ? (''+start) : (start+'-'+prev));
    return parts.join(', ');
  }

  function mode(nums){
    var freq = {};
    var max = 0;
    nums.forEach(function(n){ freq[n]=(freq[n]||0)+1; if(freq[n]>max) max=freq[n]; });
    var modes = [];
    for (var k in freq){ if (freq[k]===max) modes.push(k); }
    return modes.map(Number).sort(function(a,b){return a-b;});
  }

  function mean(nums){
    var s = 0; for (var i=0;i<nums.length;i++) s += nums[i];
    return s / nums.length;
  }

  function median(nums){
    var s = nums.slice().sort(function(a,b){return a-b;});
    var n = s.length;
    if (n % 2) return s[(n-1)/2];
    return (s[n/2-1] + s[n/2]) / 2;
  }

  function minOf(nums){
    var m = nums[0];
    for (var i=1;i<nums.length;i++){ if (nums[i] < m) m = nums[i]; }
    return m;
  }

  function maxOf(nums){
    var m = nums[0];
    for (var i=1;i<nums.length;i++){ if (nums[i] > m) m = nums[i]; }
    return m;
  }

  function buildDataset(rows){
    var variableMap = {};
    var regionCounts = {};
    var periods = [];

    rows.forEach(function(r){
      periods.push(r.periodo);
      regionCounts[r.regiao] = (regionCounts[r.regiao]||0) + 1;
      if (!variableMap[r.nome]) variableMap[r.nome] = {};
      if (!variableMap[r.nome][r.regiao]) variableMap[r.nome][r.regiao] = [];
      variableMap[r.nome][r.regiao].push([r.periodo, r.resultado]);
    });

    var variables = Object.keys(variableMap).sort();
    variables.forEach(function(nome){
      var regions = variableMap[nome];
      for (var regiao in regions){
        regions[regiao].sort(function(a,b){ return a[0]-b[0]; });
      }
    });

    var variableList = variables.map(function(nome){
      var regions = variableMap[nome];
      var years = [];
      for (var regiao in regions){
        regions[regiao].forEach(function(pair){ years.push(pair[0]); });
      }
      return { nome:nome, yearRange: formatYearRanges(years), regions: regions };
    });

    return {
      rows: rows,
      variables: variableList,
      variableMap: variableMap,
      totalRows: rows.length,
      totalVariables: variables.length,
      totalRegions: Object.keys(regionCounts).length,
      regionCounts: regionCounts,
      periodStats: {
        moda: mode(periods),
        media: mean(periods),
        mediana: median(periods),
        min: minOf(periods),
        max: maxOf(periods)
      }
    };
  }

  // Recomputes everything that gets rendered (stats strip, region list,
  // variable list/bodies) from either all rows or, when "só Distritos" is
  // on, only rows whose região is a Distrito. Variables left with no
  // Distrito data at all simply disappear from the view — that's what
  // buildDataset() naturally does when handed a filtered row set.
  function rebuildView(){
    var filteredRows = state.onlyDistritos
      ? state.rows.filter(function(r){ return isDistrito(r.regiao); })
      : state.rows;
    var ds = buildDataset(filteredRows);
    state.variables = ds.variables;
    state.variableMap = ds.variableMap;
    renderStats(ds);
    renderRegionCounts(ds);
    renderVarList(ds); // renderVarList already calls applyFilters() + updateProgress()
    applyAutoMarking(true);
  }

  function loadDecisions(key){
    try{
      var raw = localStorage.getItem('observa_decisions::'+key);
      if (!raw) return {};
      return JSON.parse(raw);
    }catch(e){ return {}; }
  }

  function saveDecisions(key, decisions){
    try{
      localStorage.setItem('observa_decisions::'+key, JSON.stringify(decisions));
    }catch(e){ /* storage unavailable — decisions just won't persist across reloads */ }
  }

  // autoFlags[nome] === true means the current decision for that variable was
  // set by the auto-marking rule, not chosen by hand — so it's safe to
  // recompute/revert it later without clobbering a real user choice.
  function loadAutoFlags(key){
    try{
      var raw = localStorage.getItem('observa_autoflags::'+key);
      if (!raw) return {};
      return JSON.parse(raw);
    }catch(e){ return {}; }
  }

  function saveAutoFlags(key, flags){
    try{
      localStorage.setItem('observa_autoflags::'+key, JSON.stringify(flags));
    }catch(e){ /* storage unavailable — auto flags just won't persist across reloads */ }
  }

  function csvEscape(val){
    val = String(val === undefined || val === null ? '' : val);
    if (/[;"\n\r]/.test(val)){
      return '"' + val.replace(/"/g,'""') + '"';
    }
    return val;
  }

  function toCSV(rowsArr){
    return rowsArr.map(function(r){ return r.map(csvEscape).join(';'); }).join('\r\n') + '\r\n';
  }

  // ---------------------------------------------------------------------
  // Rendering
  // ---------------------------------------------------------------------

  function fmtNum(n, decimals){
    return n.toLocaleString('pt-BR', { minimumFractionDigits: decimals||0, maximumFractionDigits: decimals||2 });
  }

  function renderStats(ds){
    var s = ds.periodStats;
    var modaStr = s.moda.join(', ');
    var cards = [
      ['Linhas', fmtNum(ds.totalRows)],
      ['Variáveis', fmtNum(ds.totalVariables)],
      ['Regiões', fmtNum(ds.totalRegions)],
      ['Moda do período', modaStr],
      ['Média do período', fmtNum(s.media,2)],
      ['Mediana do período', fmtNum(s.mediana,1)],
      ['Intervalo total', s.min+'–'+s.max],
      ['Auto-descartadas', fmtNum(Object.keys(state.autoFlags||{}).length)]
    ];
    var html = cards.map(function(c){
      return '<div class="stat-card"><div class="label">'+c[0]+'</div><div class="value">'+c[1]+'</div></div>';
    }).join('');
    document.getElementById('statsStrip').innerHTML = html;
  }

  function renderRegionCounts(ds){
    var byType = {};
    Object.keys(ds.regionCounts).sort().forEach(function(regiao){
      var t = regionType(regiao);
      if (!byType[t]) byType[t] = [];
      byType[t].push([regiao, ds.regionCounts[regiao]]);
    });
    var html = '';
    Object.keys(byType).sort().forEach(function(t){
      html += '<div class="region-type-group"><h3>'+t+'</h3>';
      byType[t].forEach(function(pair){
        html += '<div class="region-row"><span>'+pair[0]+'</span><span class="cnt">'+fmtNum(pair[1])+'</span></div>';
      });
      html += '</div>';
    });
    document.getElementById('regionList').innerHTML = html;
  }

  // A row existing for a given year doesn't mean there's real data — many
  // open-data CSVs still emit a row with an empty or placeholder value
  // ("-", "SD", "N/D", "NA"...) for years with nothing recorded. Only count
  // it as present when the value itself is meaningful.
  var MISSING_VALUE_TOKENS = ['-','--','na','n/a','nd','n/d','sd','s/d','null','none','...','n.d.','indisponível','indisponivel'];
  function hasValue(val){
    if (val === undefined || val === null) return false;
    var s = String(val).trim();
    if (!s) return false;
    return MISSING_VALUE_TOKENS.indexOf(s.toLowerCase()) === -1;
  }

  function escHtml(s){
    return String(s == null ? '' : s)
      .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
      .replace(/"/g,'&quot;');
  }

  function decisionOf(nome){
    return state.decisions[nome] || 'undecided';
  }

  // For every variable that appears anywhere in the raw dataset (regardless
  // of the "só Distritos" toggle), works out whether it should be
  // auto-discarded, based on Distrito-only data:
  //   - coverage: dá com dado em quantos % dos distritos existentes no
  //     dataset. Abaixo de thresholds.minDistrictPct  -> descartar.
  //   - missing:  dos registros de Distrito dessa variável, quantos % têm
  //     valor vazio/placeholder (via hasValue). Acima de thresholds.maxNullPct
  //     -> descartar.
  // Returns { nome: true/false, ... }. If the dataset has zero Distrito rows
  // at all, no variable is auto-flagged (there's nothing to judge coverage
  // against).
  function computeAutoDiscardFlags(){
    var minPct = state.thresholds.minDistrictPct;
    var maxNullPct = state.thresholds.maxNullPct;

    var allDistricts = {};
    var totalDistricts = 0;
    var perVar = {};
    var allVarNames = {};

    state.rows.forEach(function(r){
      allVarNames[r.nome] = true;
      if (!isDistrito(r.regiao)) return;
      if (!allDistricts[r.regiao]){ allDistricts[r.regiao] = true; totalDistricts++; }
      if (!perVar[r.nome]) perVar[r.nome] = { covered: {}, coveredCount: 0, total: 0, nullCount: 0 };
      var entry = perVar[r.nome];
      entry.total++;
      if (hasValue(r.resultado)){
        if (!entry.covered[r.regiao]){ entry.covered[r.regiao] = true; entry.coveredCount++; }
      } else {
        entry.nullCount++;
      }
    });

    var flags = {};
    Object.keys(allVarNames).forEach(function(nome){
      if (totalDistricts === 0){ flags[nome] = false; return; }
      var entry = perVar[nome] || { coveredCount: 0, total: 0, nullCount: 0 };
      var coveragePct = (entry.coveredCount / totalDistricts) * 100;
      var belowCoverage = coveragePct < minPct;
      var nullPct = entry.total > 0 ? (entry.nullCount / entry.total) * 100 : 0;
      var aboveNull = entry.total > 0 && nullPct > maxNullPct;
      flags[nome] = belowCoverage || aboveNull;
    });
    return flags;
  }

  function removeAutoTag(row){
    var tag = row.querySelector('.auto-tag');
    if (tag) tag.remove();
  }

  // Applies computeAutoDiscardFlags() to state.decisions:
  //   - undecided + rule says discard          -> set 'not', flag as auto
  //   - was auto-flagged + rule still says yes -> stays 'not' (auto)
  //   - was auto-flagged + rule no longer says yes -> reverts to undecided
  //   - manually decided (keep or not, not auto) -> never touched
  // silent=true skips updating the on-screen note (used on routine
  // re-renders like toggling "só Distritos"); pass false for an explicit
  // user-triggered run so they see what changed.
  function applyAutoMarking(silent){
    if (!state.rows || !state.rows.length) return;
    var flags = computeAutoDiscardFlags();
    var changed = 0, reverted = 0;

    Object.keys(flags).forEach(function(nome){
      var shouldDiscard = flags[nome];
      var wasAuto = !!state.autoFlags[nome];
      var current = state.decisions[nome];

      if (wasAuto){
        if (!shouldDiscard){
          delete state.decisions[nome];
          delete state.autoFlags[nome];
          reverted++;
        }
        // else: still meets the rule, stays as-is
      } else if (!current && shouldDiscard){
        state.decisions[nome] = 'not';
        state.autoFlags[nome] = true;
        changed++;
      }
      // manual 'keep' / 'not' decisions are left alone either way
    });

    if (changed || reverted){
      saveDecisions(state.datasetKey, state.decisions);
      saveAutoFlags(state.datasetKey, state.autoFlags);
    }

    document.querySelectorAll('.var-row').forEach(function(row){
      var nome = row.dataset.nome;
      var d = decisionOf(nome);
      row.dataset.status = d;
      var actions = row.querySelector('.var-actions');
      if (actions){
        actions.querySelector('.btn-keep').classList.toggle('active', d==='keep');
        actions.querySelector('.btn-not').classList.toggle('active', d==='not');
      }
      var header = row.querySelector('.var-header');
      var existingTag = header.querySelector('.auto-tag');
      if (state.autoFlags[nome] && !existingTag){
        var span = document.createElement('span');
        span.className = 'auto-tag';
        span.textContent = 'auto';
        span.title = 'Marcado automaticamente: cobertura de distritos abaixo de ' + state.thresholds.minDistrictPct +
          '% ou dados ausentes acima de ' + state.thresholds.maxNullPct + '%.';
        header.insertBefore(span, header.querySelector('.var-range'));
      } else if (!state.autoFlags[nome] && existingTag){
        existingTag.remove();
      }
    });

    updateProgress();

    var note = document.getElementById('autoNote');
    if (note && !silent){
      note.textContent = (changed || reverted)
        ? (changed + ' variável(is) marcada(s) automaticamente como "não manter"' +
           (reverted ? '; ' + reverted + ' revertida(s) para indefinida.' : '.'))
        : 'Nenhuma alteração necessária com os limites atuais.';
    }
  }

  function renderVarBody(v){
    var allYears = [];
    Object.keys(v.regions).forEach(function(regiao){
      v.regions[regiao].forEach(function(pair){ allYears.push(pair[0]); });
    });
    if (!allYears.length){
      return '<p style="font-size:.8rem;color:var(--ink-soft);margin:0;">Sem dados.</p>';
    }
    // Only the years that actually occur somewhere in this variable's data —
    // no filling in gaps between them (a range can be non-contiguous).
    var years = Array.from(new Set(allYears)).sort(function(a,b){ return a-b; });

    var byType = {};
    Object.keys(v.regions).sort().forEach(function(regiao){
      var t = regionType(regiao);
      if (!byType[t]) byType[t] = [];
      byType[t].push(regiao);
    });

    var html = '<div class="year-legend">' +
      '<span><span class="dot yc-has"></span>tem dado no ano</span>' +
      '<span><span class="dot yc-missing"></span>sem dado no ano</span>' +
      '</div>';

    html += '<div class="year-table-wrap"><table class="year-table"><thead><tr><th class="rname-col">Região</th>';
    years.forEach(function(yr){ html += '<th>' + yr + '</th>'; });
    html += '</tr></thead><tbody>';

    Object.keys(byType).sort().forEach(function(t){
      html += '<tr class="type-row"><th class="type-cell" colspan="' + (years.length + 1) + '">' + escHtml(t) + '</th></tr>';
      byType[t].forEach(function(regiao){
        var byYear = {};
        v.regions[regiao].forEach(function(pair){ byYear[pair[0]] = pair[1]; });
        html += '<tr><td class="rname-col">' + escHtml(regiao) + '</td>';
        years.forEach(function(yr){
          var present = Object.prototype.hasOwnProperty.call(byYear, yr);
          if (present && hasValue(byYear[yr])){
            html += '<td class="yc yc-has" title="' + yr + ': ' + escHtml(byYear[yr]) + '"></td>';
          } else {
            var reason = present ? 'valor vazio/indisponível' : 'sem registro';
            html += '<td class="yc yc-missing" title="' + yr + ': ' + reason + '"></td>';
          }
        });
        html += '</tr>';
      });
    });

    html += '</tbody></table></div>';
    return html;
  }

  function renderVarList(ds){
    var container = document.getElementById('varList');
    container.innerHTML = '';
    var frag = document.createDocumentFragment();

    ds.variables.forEach(function(v){
      var row = document.createElement('div');
      row.className = 'var-row';
      row.dataset.nome = v.nome;
      row.dataset.status = decisionOf(v.nome);

      var header = document.createElement('div');
      header.className = 'var-header';
      header.innerHTML =
        '<span class="chevron">▸</span>' +
        '<span class="status-dot"></span>' +
        '<span class="var-name"></span>' +
        '<span class="var-range">('+v.yearRange+')</span>';
      header.querySelector('.var-name').textContent = v.nome;

      var actions = document.createElement('div');
      actions.className = 'var-actions';
      actions.innerHTML =
        '<button type="button" class="btn-keep">Manter</button>' +
        '<button type="button" class="btn-not">Não manter</button>' +
        '<button type="button" class="clear-btn">limpar decisão</button>';

      var body = document.createElement('div');
      body.className = 'var-body';
      body.hidden = true;
      body.dataset.rendered = '0';

      function refreshButtons(){
        var d = decisionOf(v.nome);
        row.dataset.status = d;
        actions.querySelector('.btn-keep').classList.toggle('active', d==='keep');
        actions.querySelector('.btn-not').classList.toggle('active', d==='not');
      }
      refreshButtons();

      header.addEventListener('click', function(){
        var willOpen = body.hidden;
        body.hidden = !body.hidden;
        row.classList.toggle('open', willOpen);
        if (willOpen && body.dataset.rendered === '0'){
          body.innerHTML = renderVarBody(v);
          body.dataset.rendered = '1';
        }
      });

      actions.querySelector('.btn-keep').addEventListener('click', function(e){
        e.stopPropagation();
        state.decisions[v.nome] = 'keep';
        delete state.autoFlags[v.nome];
        saveDecisions(state.datasetKey, state.decisions);
        saveAutoFlags(state.datasetKey, state.autoFlags);
        refreshButtons();
        removeAutoTag(row);
        updateProgress();
      });
      actions.querySelector('.btn-not').addEventListener('click', function(e){
        e.stopPropagation();
        state.decisions[v.nome] = 'not';
        delete state.autoFlags[v.nome];
        saveDecisions(state.datasetKey, state.decisions);
        saveAutoFlags(state.datasetKey, state.autoFlags);
        refreshButtons();
        removeAutoTag(row);
        updateProgress();
      });
      actions.querySelector('.clear-btn').addEventListener('click', function(e){
        e.stopPropagation();
        delete state.decisions[v.nome];
        delete state.autoFlags[v.nome];
        saveDecisions(state.datasetKey, state.decisions);
        saveAutoFlags(state.datasetKey, state.autoFlags);
        refreshButtons();
        removeAutoTag(row);
        updateProgress();
      });

      row.appendChild(header);
      row.appendChild(actions);
      row.appendChild(body);
      frag.appendChild(row);
    });

    container.appendChild(frag);
    applyFilters();
    updateProgress();
  }

  function applyFilters(){
    var q = state.search.trim().toLowerCase();
    var rows = document.querySelectorAll('.var-row');
    rows.forEach(function(row){
      var matchesText = !q || row.dataset.nome.toLowerCase().indexOf(q) !== -1;
      var status = row.dataset.status;
      var matchesFilter = state.filter === 'all' || status === state.filter;
      row.classList.toggle('hidden', !(matchesText && matchesFilter));
    });
  }

  function updateProgress(){
    var total = state.variables.length;
    var keep=0, not=0, undecided=0;
    state.variables.forEach(function(v){
      var d = decisionOf(v.nome);
      if (d==='keep') keep++; else if (d==='not') not++; else undecided++;
    });
    document.getElementById('progressTag').innerHTML =
      '<b>'+keep+'</b> manter · <b>'+not+'</b> não manter · <b>'+undecided+'</b> indefinida(s) de '+total;
    document.getElementById('exportNote').textContent =
      undecided > 0
        ? undecided + ' variável(is) ainda indefinida(s) — serão exportadas como "not keep".'
        : 'Todas as variáveis foram revisadas.';
    // status dots may have changed without a full re-render (e.g. after filter change) — nothing else to do here
    applyFilters();
  }

  function saveFile(filename, blob){
    if (downloadsApi){
      return downloadsApi.save({ filename: filename, data: blob }).catch(function(err){
        // If the capability rejects (e.g. declined), still let the user get
        // the file via the plain browser fallback rather than doing nothing.
        fallbackDownload(filename, blob);
      });
    }
    fallbackDownload(filename, blob);
  }

  function fallbackDownload(filename, blob){
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(function(){ URL.revokeObjectURL(url); }, 4000);
  }

  function updateExportButtons(){
    // Buttons stay enabled either way: with the downloads capability we use
    // it, otherwise saveFile() falls back to a plain browser download
    // (works fine when this file is opened directly, e.g. double-clicked).
  }

  // ---------------------------------------------------------------------
  // Loading files
  // ---------------------------------------------------------------------

  function readFileAsText(file){
    return new Promise(function(resolve, reject){
      var reader = new FileReader();
      reader.onload = function(){ resolve(reader.result); };
      reader.onerror = function(){ reject(reader.error); };
      reader.readAsText(file, 'utf-8');
    });
  }

  function setStatus(msg){
    document.getElementById('loadStatus').textContent = msg;
  }

  document.getElementById('fileInput').addEventListener('change', function(e){
    var files = Array.from(e.target.files || []);
    if (!files.length) return;
    setStatus('Lendo ' + files.length + ' arquivo(s)…');

    var allRows = [];
    var names = [];

    var chain = Promise.resolve();
    files.forEach(function(file){
      chain = chain.then(function(){
        return readFileAsText(file).then(function(text){
          names.push(file.name);
          var ext = file.name.split('.').pop().toLowerCase();
          var rows;
          if (ext === 'json'){
            rows = rowsFromJSON(JSON.parse(text));
          } else {
            rows = rowsFromCSVText(text);
          }
          allRows = allRows.concat(rows);
          setStatus('Processado ' + file.name + ' (' + rows.length + ' linha(s))…');
        });
      });
    });

    chain.then(function(){
      if (!allRows.length){
        setStatus('Nenhuma linha válida encontrada nos arquivo(s) selecionado(s).');
        return;
      }
      // datasetKey (used to persist decisions) is always based on the raw,
      // unfiltered rows so toggling "só Distritos" never loses saved decisions.
      var rawDs = buildDataset(allRows);
      state.rows = allRows;
      state.sourceNames = names;
      state.datasetKey = names.slice().sort().join('|') + '::' + rawDs.totalRows;
      state.decisions = loadDecisions(state.datasetKey);
      state.autoFlags = loadAutoFlags(state.datasetKey);
      state.filter = 'all';
      state.search = '';
      document.getElementById('searchBox').value = '';
      document.querySelectorAll('#statusFilter button').forEach(function(b){
        b.classList.toggle('active', b.dataset.filter === 'all');
      });

      rebuildView();

      document.getElementById('emptyState').hidden = true;
      document.getElementById('app').hidden = false;
      document.getElementById('resetBtn').hidden = false;
      setStatus('Carregado: ' + names.join(', ') + ' — ' + fmtNum(rawDs.totalRows) + ' linha(s), ' + rawDs.totalVariables + ' variável(is) no total.');
    }).catch(function(err){
      setStatus('Erro ao processar arquivo: ' + err.message);
    });

    e.target.value = '';
  });

  document.getElementById('resetBtn').addEventListener('click', function(){
    document.getElementById('app').hidden = true;
    document.getElementById('emptyState').hidden = false;
    document.getElementById('resetBtn').hidden = true;
    setStatus('');
  });

  document.getElementById('searchBox').addEventListener('input', function(e){
    state.search = e.target.value;
    applyFilters();
  });

  document.getElementById('statusFilter').addEventListener('click', function(e){
    var btn = e.target.closest('button[data-filter]');
    if (!btn) return;
    state.filter = btn.dataset.filter;
    document.querySelectorAll('#statusFilter button').forEach(function(b){
      b.classList.toggle('active', b === btn);
    });
    applyFilters();
  });

  document.getElementById('expandAllBtn').addEventListener('click', function(){
    document.querySelectorAll('.var-row:not(.hidden)').forEach(function(row){
      var body = row.querySelector('.var-body');
      var nome = row.dataset.nome;
      var v = state.variables.find(function(x){ return x.nome === nome; });
      if (!v) return;
      body.hidden = false;
      row.classList.add('open');
      if (body.dataset.rendered === '0'){
        body.innerHTML = renderVarBody(v);
        body.dataset.rendered = '1';
      }
    });
  });

  document.getElementById('collapseAllBtn').addEventListener('click', function(){
    document.querySelectorAll('.var-row').forEach(function(row){
      row.querySelector('.var-body').hidden = true;
      row.classList.remove('open');
    });
  });

  document.getElementById('exportReviewBtn').addEventListener('click', function(){
    var out = [['Nome','IntervaloDeAnos','Decisao']];
    state.variables.forEach(function(v){
      out.push([v.nome, v.yearRange, decisionOf(v.nome)==='keep' ? 'keep' : 'not keep']);
    });
    var blob = new Blob(['\ufeff' + toCSV(out)], { type: 'text/csv;charset=utf-8' });
    saveFile('variaveis_revisao.csv', blob);
  });

  document.getElementById('exportDataBtn').addEventListener('click', function(){
    var keepSet = {};
    state.variables.forEach(function(v){ if (decisionOf(v.nome)==='keep') keepSet[v.nome]=true; });
    var onlyDistritos = state.onlyDistritos;
    var out = [['Nome','Região','Período','Resultado']];
    var droppedNonDistrito = 0;
    state.rows.forEach(function(r){
      if (!keepSet[r.nome]) return;
      if (onlyDistritos && !isDistrito(r.regiao)){
        droppedNonDistrito++;
        return;
      }
      out.push([r.nome, r.regiao, r.periodo, r.resultado]);
    });
    var blob = new Blob(['\ufeff' + toCSV(out)], { type: 'text/csv;charset=utf-8' });
    saveFile('dados_filtrados.csv', blob);
    setStatus(
      (out.length - 1) + ' linha(s) exportada(s) em dados_filtrados.csv' +
      (onlyDistritos
        ? ' (apenas Distritos — ' + droppedNonDistrito + ' linha(s) de Município/Subprefeitura descartada(s)).'
        : ' (Município e Subprefeitura incluídos — filtro de Distritos desativado).')
    );
  });

})();