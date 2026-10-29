"use strict";
const byId = id => document.getElementById(id);
const num = v => new Intl.NumberFormat('ja-JP').format(Number(v) || 0);
const jst = (s, compact = false) => {
  if (!s) return '未取得';
  const d = new Date(s);
  if (!Number.isFinite(d.getTime())) return '未取得';
  const opts = {timeZone:'Asia/Tokyo', month:'numeric', day:'numeric', hour:'2-digit', minute:'2-digit'};
  if (!compact) opts.year = 'numeric';
  return new Intl.DateTimeFormat('ja-JP', opts).format(d);
};
function set(id, value){ const el = byId(id); if(el) el.textContent = String(value); }
function svg(tag, attrs = {}){
  const node = document.createElementNS('http://www.w3.org/2000/svg', tag);
  Object.keys(attrs).forEach(key => node.setAttribute(key, String(attrs[key])));
  return node;
}
const array = x => Array.isArray(x) ? x : [];
function renderChart(history){
  const holder = byId('historyChart');
  holder.replaceChildren();
  const values = history.map(p => Math.max(0, Number(p.jobs) || 0));
  if(!values.length){
    const empty = svg('text',{x:285,y:112,fill:'#8fa2b7','text-anchor':'middle','font-size':13});
    empty.textContent = 'まだ実行履歴がありません'; holder.appendChild(empty); return;
  }
  const W=570,H=240,top=16,bottom=29,left=9,right=9;
  const maximum = Math.max(...values,1)*1.15;
  for(let i=0;i<4;i++){
    const y=top+(H-top-bottom)*i/3;
    holder.appendChild(svg('line',{x1:left,x2:W-right,y1:y,y2:y,stroke:'#293950','stroke-dasharray':'4 6','stroke-width':1}));
  }
  const points=values.map((v,i)=>({
    x:left+(W-left-right)*(values.length===1?.5:i/(values.length-1)),
    y:H-bottom-(H-top-bottom)*v/maximum, value:v
  }));
  const line=points.map((p,i)=>(i?'L':'M')+p.x.toFixed(1)+' '+p.y.toFixed(1)).join(' ');
  const first=points[0],last=points[points.length-1];
  const area=line+' L'+last.x.toFixed(1)+' '+(H-bottom)+' L'+first.x.toFixed(1)+' '+(H-bottom)+' Z';
  const defs=svg('defs'),grad=svg('linearGradient',{id:'graphFill',x1:0,y1:0,x2:0,y2:1});
  grad.appendChild(svg('stop',{offset:'0%','stop-color':'#57d8bb','stop-opacity':'.26'}));
  grad.appendChild(svg('stop',{offset:'100%','stop-color':'#57d8bb','stop-opacity':'0'}));
  defs.appendChild(grad);holder.appendChild(defs);
  holder.appendChild(svg('path',{d:area,fill:'url(#graphFill)'}));
  holder.appendChild(svg('path',{d:line,fill:'none',stroke:'#69dcc2','stroke-width':3.4,'stroke-linejoin':'round','stroke-linecap':'round'}));
  points.forEach((p,i)=>{
    if(i===points.length-1 || points.length<=8){
      const dot=svg('circle',{cx:p.x,cy:p.y,r:i===points.length-1?5:3,fill:'#6ee8c9',stroke:'#182635','stroke-width':2});
      const tip=svg('title');
      tip.textContent=jst(history[i].at)+': '+num(p.value)+'件';
      dot.appendChild(tip);holder.appendChild(dot);
    }
  });
  set('historyLatest',num(values[values.length-1]));
  set('historyFrom',jst(history[0].at,true));
  set('historyTo',jst(history[history.length-1].at,true));
  set('historyRange',history.length+' 回分');
}
function renderSources(sources){
  const wrap=byId('sourceList');wrap.replaceChildren();
  const max=Math.max(1,...sources.map(s=>Number(s.fetched)||0));
  sources.forEach(item=>{
    const row=document.createElement('div');row.className='source';
    const name=document.createElement('div');name.className='source-name';name.textContent=item.name||'—';
    const progress=document.createElement('div');progress.className='source-progress';
    const fill=document.createElement('div');fill.style.width=Math.max(0,Math.min(100,(Number(item.fetched)||0)*100/max))+'%';
    progress.appendChild(fill);
    const count=document.createElement('div');count.className='source-count';count.textContent=num(item.fetched);
    const state=document.createElement('div');state.className='source-state';
    if(item.state==='ok')state.textContent='正常';
    else if(item.state==='error'){state.classList.add('is-error');state.textContent='エラー';state.title=item.error_type||'';}
    else if(item.state==='blocked_permission'){state.classList.add('is-off');state.textContent='API許可待ち';}
    else{state.classList.add('is-off');state.textContent='未接続';}
    row.append(name,progress,count,state);wrap.appendChild(row);
  });
  if(!sources.length){const x=document.createElement('div');x.className='empty';x.textContent='取得元のデータがありません';wrap.appendChild(x);}
}
function renderStages(stages){
  const wrap=byId('stageList');wrap.replaceChildren();
  stages.forEach(stage=>{
    const row=document.createElement('div');row.className='stage';
    const mark=document.createElement('div');mark.className='stage-marker'+(stage.done?' done':'');mark.textContent=stage.done?'✓':'–';
    const info=document.createElement('div');
    const title=document.createElement('div');title.className='stage-name';title.textContent=stage.name;
    const detail=document.createElement('div');detail.className='stage-detail';detail.textContent=stage.detail;
    info.append(title,detail);
    const state=document.createElement('div');state.className='stage-state'+(stage.done?' done':'');state.textContent=stage.done?'確認済み':'未達';
    row.append(mark,info,state);wrap.appendChild(row);
  });
  const done=stages.filter(s=>s.done).length,total=stages.length;
  const pct=total?Math.round(100*done/total):0;
  set('progressPercent',pct+'%');set('progressCount',done+'/'+total+' 段階');
  byId('overallBar').style.width=pct+'%';
}
function renderApplicationHistory(items){
  const root=byId('applicationHistory');
  if(!root)return;
  root.replaceChildren();
  const valid=array(items).slice(0,20);
  if(!valid.length){
    const el=document.createElement('div');
    el.className='empty';
    el.textContent='確認済みの応募提出履歴はまだありません';
    root.appendChild(el);
    return;
  }
  valid.forEach(item=>{
    const row=document.createElement('div');
    row.className='application-history-entry';
    const info=document.createElement('div');
    info.className='application-history-info';
    const title=document.createElement('strong');
    title.textContent=item.title||'案件名未取得';
    const meta=document.createElement('small');
    meta.textContent=(item.platform||'Upwork')+' ・ '+jst(item.submitted_at);
    info.append(title,meta);
    const right=document.createElement('div');
    right.className='application-history-terms';
    const state=document.createElement('span');
    state.textContent=item.status==='Submitted'?'応募提出済み':'確認待ち';
    const terms=document.createElement('small');
    if(item.platform==='Email応募'){
      terms.textContent='応募メール送信済み・返信待ち';
    }else{
      terms.textContent='$'+num(item.bid_usd)+' / '+num(item.connects_spent)+' Connects';
    }
    right.append(state,terms);
    row.append(info,right);
    root.appendChild(row);
  });
}

function renderWorker(w){
  const data=w||{};
  const state=data.state==='running'?'監視処理稼働中':
              data.state==='stale'?'更新遅延':'未稼働・未確認';
  set('workerState',state);
  set('workerLastTick',jst(data.last_tick,true));
  set('workerEligible',num(data.high_fit_eligible));
  set('workerPrepared',num(data.drafts_created));
  set('workerUnknown',num(data.unknown_outcome));
  const list=byId('workerPlatforms');
  if(!list)return;
  list.replaceChildren();
  const labels={
    requires_individual_confirmation:'案件ごとに本人承認',
    authorized:'公式API応募可能',
    blocked_permission:'API書面許可・OAuth待ち',
    blocked_account:'公式応募アカウント未接続',
    blocked_profile:'プロフィール/KYC未完',
    blocked_apply:'応募API未接続',
    unverified:'未確認'
  };
  array(data.providers).forEach(p=>{
    const row=document.createElement('div');
    row.className='worker-platform';
    const name=document.createElement('strong');
    name.textContent=p.name||'不明な媒体';
    const value=document.createElement('span');
    value.textContent=labels[p.state]||'未確認';
    if(p.state==='authorized')value.className='allowed';
    row.append(name,value);
    list.appendChild(row);
  });
}

function renderCampaign(goal){
  const g=goal||{};
  const target=Number.isInteger(g.target)&&g.target>0?g.target:100;
  const submitted=Number.isInteger(g.verified_submitted)?g.verified_submitted:null;
  set('applicationGoalCount',(submitted===null?'未確認':num(submitted))+' / '+num(target));
  const bar=byId('applicationGoalBar');
  if(bar)bar.style.width=(submitted===null?0:Math.max(0,Math.min(100,100*submitted/target)))+'%';
  set('applicationQueue',num(g.candidate_queue));
  set('applicationScreened',num(g.marketplace_rows_screened));
  set('applicationCampaignAt',jst(g.campaign_checked_at,true));
}

function renderUpwork(u){
  const recent=u&&u.verification==='recent';
  set('upworkVerified',u?.verified_at?'公式最終確認 '+jst(u.verified_at):'公式照合未完了');
  set('upworkSubmitted',recent&&Number.isInteger(u.submitted)?num(u.submitted)+'件':'再確認が必要');
  let state='未確認';
  if(recent&&u.target==='not_submitted')state='未応募';
  if(recent&&u.target==='submitted')state='応募済み';
  if(recent&&u.target==='closed')state='募集終了';
  set('upworkCandidateStatus',state);
  set('upworkConnects',recent&&Number.isInteger(u.target_connects_cost)&&Number.isInteger(u.connects_balance)
    ?num(u.target_connects_cost)+' / '+num(u.connects_balance)
    :'再確認が必要');
  set('upworkInFlight',recent&&Number.isInteger(u.pending)&&Number.isInteger(u.invitations)
    ?num(u.pending)+'件 / '+num(u.invitations)+'件'
    :'再確認が必要');
}

function render(data){
  if(!data||data.schema!==1||!data.metrics)throw Error('Invalid public status schema');
  const m=data.metrics;
  const sources=array(data.sources);
  const stages=array(data.stages);
  set('jobsFetched',num(m.jobs_fetched));
  set('feedsCount',m.sources_ok+'/'+m.sources_total+' 媒体が正常');
  set('candidates',num(m.candidates));
  set('mcpFound',num(m.mcp_found));
  set('mcpIndexed',num(m.mcp_indexed)+'件を候補台帳に収録');
  set('apifyFound',num(m.apify_found));
  set('lastRun',jst(data.last_run));
  set('nextRun',jst(data.next_run_estimate)+'（目安）');
  set('lastUpdated','公開データ更新 '+jst(data.published_at,true));
  set('sourceSummary',m.sources_ok+' / '+m.sources_total+' 正常');
  set('funnelCandidates',num(m.candidates));
  set('applications',m.applications==null?'未確認':num(m.applications));
  set('contracts',num(m.contracts));
  set('outsourced',num(m.outsourced));
  set('revenue','¥'+num(m.revenue_jpy_verified));
  const healthy=data.health==='running';
  const degraded=data.health==='degraded';
  const pill=byId('livePill');
  pill.className='pill'+(healthy?'':degraded?' pill-warning':' pill-muted');
  pill.replaceChildren();
  const dot=document.createElement('span');
  dot.className='pulse-dot';
  pill.appendChild(dot);
  pill.appendChild(document.createTextNode(healthy?' 正常稼働':degraded?' 更新遅延':' 停止・未確認'));
  set('runState',healthy?'ACTIVE':degraded?'DELAYED':'CHECK');
  set('runtimeHint',healthy?'PCの定期実行を確認':degraded?'前回の処理は成功、更新遅延あり':'最後の実行を確認してください');
  byId('runtimeBar').style.width=healthy?'100%':degraded?'58%':'12%';
  renderCampaign(data.application_goal);
  renderApplicationHistory(data.application_history);
  renderWorker(data.worker);
  renderUpwork(data.upwork);
  renderSources(sources);
  renderStages(stages);
  renderChart(array(data.history));
}

async function refresh(){
  try{
    const response=await fetch('/status.json?cache='+Date.now(),{cache:'no-store'});
    if(!response.ok)throw Error('public status fetch failed');
    render(await response.json());
  }catch(error){
    set('runState','CHECK');
    set('runtimeHint','公開データが取得できません');
    const pill=byId('livePill');
    pill.className='pill pill-muted';
    pill.textContent='確認できません';
  }
}

refresh();
window.setInterval(refresh,300000);
