"use strict";
const e=id=>document.getElementById(id);
let data=[],mode="all",visible=12;
const fmt=n=>new Intl.NumberFormat("ja-JP").format(Number(n)||0);
const formatDate=v=>{let d=new Date(v);return Number.isFinite(d.getTime())?new Intl.DateTimeFormat("ja-JP",{timeZone:"Asia/Tokyo",month:"short",day:"numeric"}).format(d):"時刻未確認"};
function el(tag,className,text){let x=document.createElement(tag);if(className)x.className=className;if(text!==undefined)x.textContent=String(text);return x}
function filtered(){
 const q=e("search").value.toLocaleLowerCase().trim();
 const src=e("source").value;
 let rows=data.filter(j=>(src==="all"||j.source===src)&&
   (mode!=="ai"||j.ai_first)&&
   (mode!=="remote"||j.kind==="employment_or_unverified")&&
   (!q||[j.title,j.company,j.location,j.contract_type].join(" ").toLowerCase().includes(q)));
 const sort=e("sort").value;
 if(sort==="ai")rows.sort((a,b)=>Number(b.ai_first)-Number(a.ai_first));
 if(sort==="title")rows.sort((a,b)=>a.title.localeCompare(b.title));
 return rows;
}
function draftPrompt(j){
 return "次の求人の詳細を掲載元で確認し、応募条件と規約を調べてください。"+
 "受託できる具体的な納品物・作業時間・AI完結可能性を根拠付きで判定し、"+
 "事実を捏造せず応募ドラフトを作ってください。"+
 "公式APIが必要な送信・契約・支払いは提供元の承認手順を守ってください。\n"+
 "Title: "+j.title+"\nSource: "+j.source+"\nOriginal listing: "+j.url+
 "\nBudget: "+(j.compensation||"Not listed");
}
function render(){
 const items=filtered(),list=e("jobsList");
 e("resultCount").textContent=fmt(items.length)+" 件";
 list.replaceChildren();
 if(!items.length){list.appendChild(el("div","empty","条件に一致する公開求人がありません。検索条件を変更してください。"));e("showMore").hidden=true;return}
 for(const j of items.slice(0,visible)){
   const box=el("article","job");
   const top=el("div","job-head");
   top.appendChild(el("span","source-tag",j.source));
   if(j.ai_first)top.appendChild(el("span","ai-tag","AI優先候補・未検証"));
   box.appendChild(top);
   box.appendChild(el("h3","",j.title));
   box.appendChild(el("div","company",j.company||"企業名非公開"));
   let meta=el("div","detail");
   meta.appendChild(el("span","",j.location||"リモート等"));
   if(j.compensation)meta.appendChild(el("span","",j.compensation));
   meta.appendChild(el("span","",j.contract_type||"契約区分要確認"));
   meta.appendChild(el("span","",formatDate(j.published_at)));
   box.appendChild(meta);
   const bottom=el("div","job-bottom");
   const copy=el("button","copy","AI提案用の指示をコピー");
   copy.type="button";
   copy.addEventListener("click",async()=>{try{await navigator.clipboard.writeText(draftPrompt(j));copy.textContent="コピーしました";setTimeout(()=>copy.textContent="AI提案用の指示をコピー",1800)}catch{copy.textContent="ブラウザのコピー権限が必要です"}});
   bottom.appendChild(copy);
   const out=el("a","external","掲載元で確認 ↗");
   out.href=j.url;out.target="_blank";out.rel="noopener noreferrer nofollow";
   out.setAttribute("aria-label",j.source+"で案件を開く: "+j.title);
   bottom.appendChild(out);
   box.appendChild(bottom);list.appendChild(box);
 }
 e("showMore").hidden=items.length<=visible;
}
function renderConnections(items){
 const wrap=e("connectorsList");wrap.replaceChildren();
 for(const c of items){
   const card=el("article","connector");card.appendChild(el("strong","",c.name));
   const details={
    public_search:"公開APIによる求人検索・掲載が可能。",
    user_oauth_native_confirmation:"本人OAuthに接続。送信・契約はサービス側の確認が必要。",
    oauth_not_verified:"WebログインとAPI利用権限は別。公式OAuth権限の確認が必要。",
    product_discovery_only:"公開ストアの商品研究に接続。商品販売は別の登録・審査が必要。"
   };
   card.appendChild(el("p","",details[c.status]||"接続を検証中。"));
   card.appendChild(el("div","state",(c.status==="public_search"?"● 公開求人取得":c.status==="user_oauth_native_confirmation"?"● 本人操作が必要":"○ 一部機能のみ")));
   wrap.appendChild(card);
 }
}
for(const id of ["search","source","sort"])e(id).addEventListener("input",()=>{visible=12;render()});
for(const button of document.querySelectorAll(".segmented button")){
 button.addEventListener("click",()=>{mode=button.dataset.mode;visible=12;document.querySelectorAll(".segmented button").forEach(x=>x.classList.toggle("selected",x===button));render()});
}
e("showMore").addEventListener("click",()=>{visible+=12;render()});
(async()=>{
 try{
  let r=await fetch("/jobs.json?bust="+Date.now(),{cache:"no-store"});
  if(!r.ok)throw Error("HTTP "+r.status);
  let json=await r.json();
  if(json.schema!==1||!Array.isArray(json.jobs))throw Error("Invalid schema");
  data=json.jobs.filter(j=>/^https:\/\//.test(j.url)&&["Himalayas","Jobicy"].includes(j.source));
  e("totalJobs").textContent=fmt(data.length);
  e("aiJobs").textContent=fmt(data.filter(j=>j.ai_first).length);
  e("providerCount").textContent=fmt(json.sources.length);
  e("refreshed").textContent=formatDate(json.updated_at);
  renderConnections(json.connectors||[]);
  render();
 }catch(err){
  e("jobsList").replaceChildren(el("div","empty","データを取得できません。API公開状態を確認してください。"));
  e("connectorsList").replaceChildren(el("div","empty","接続状況を取得できません。"));
  e("resultCount").textContent="未取得";
 }
})();
