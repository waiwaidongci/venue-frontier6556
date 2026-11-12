import {useEffect,useState} from 'react';
import {useLocation} from '../router';
import {researchStore,loadResearch} from '../stores/research';
import {authStore,canEdit} from '../stores/auth';
import {createComparison} from '../api/comparisons';
import {useTask} from '../hooks/useTask';
import {usePolling} from '../hooks/usePolling';
import {number} from '../utils/format';
import {fields,inputKeys,outputKeys} from '../constants/enums';
import type {ComparisonPair,ComparisonResult} from '../types/domain';
import PageHeading from '../components/common/PageHeading';
import ErrorNotice from '../components/common/ErrorNotice';
import EmptyState from '../components/common/EmptyState';
import StatusBadge from '../components/common/StatusBadge';

const scoreLabels:[keyof ComparisonPair['scores'],string][]=[
  ['own_before','θ_b(x_b) 前期对前期'],
  ['own_after','θ_a(x_a) 后期对后期'],
  ['before_against_after','θ_a(x_b) 前期对后期'],
  ['after_against_before','θ_b(x_a) 后期对前期'],
];
const directionLabels:Record<string,string>={improved:'上升',regressed:'下降',unchanged:'持平',unavailable:'无法比较'};

export default function Comparisons(){
  const {query}=useLocation(),lab=researchStore.use(),{user}=authStore.use(),{busy,error,perform}=useTask();
  const [selected,setSelected]=useState(Number(query.get('comparison'))||0);
  const [message,setMessage]=useState('');
  const [form,setForm]=useState({name:'2026Q2→Q3 · 跨期生产率',before_benchmark_id:0,after_benchmark_id:0,inputs:inputKeys,outputs:outputKeys});
  useEffect(()=>{perform(async()=>{await loadResearch();const list=researchStore.get().benchmarks;
    setSelected(id=>id||researchStore.get().comparisons[0]?.id||0);
    setForm(f=>({...f,before_benchmark_id:f.before_benchmark_id||list[0]?.id||0,after_benchmark_id:f.after_benchmark_id||list[1]?.id||0}));});},[perform]);
  useEffect(()=>{const id=Number(query.get('comparison'));if(id)setSelected(id);},[query.get('comparison')]);
  usePolling(async()=>{if(researchStore.get().comparisons.some(c=>c.id===selected&&['queued','running'].includes(c.status)))await loadResearch();});
  const benchmarkName=(id:number)=>lab.benchmarks.find(b=>b.id===id)?.period||'—';
  const comparison=lab.comparisons.find(c=>c.id===selected);
  const result=comparison?.status==='completed'?comparison.result as ComparisonResult:undefined;
  const pairs=result?.pairs||[];
  const summary=result?.summary;
  function toggle(kind:'inputs'|'outputs',key:string){setForm(f=>({...f,[kind]:f[kind].includes(key)?f[kind].filter(x=>x!==key):[...f[kind],key]}));}
  function download(){if(!comparison||!result)return;
    const rows:string[][]=[['venue_code','venue_name','status','theta_before','theta_after','theta_before_vs_after','theta_after_vs_before','catch_up','frontier_shift','total_change','direction','reason']];
    for(const p of pairs)rows.push([p.venue_code,p.venue_name,p.status,...(['own_before','own_after','before_against_after','after_against_before'] as const).map(k=>String(p.scores[k]?.theta??'')),String(p.catch_up??''),String(p.frontier_shift??''),String(p.total_change??''),p.direction,p.reason]);
    const csv='﻿'+rows.map(r=>r.map(c=>{const text=String(c);return /^[=+\-@\t\r]/.test(text)?`'${text}`:`"${text.replace(/"/g,'""')}"`}).join(',')).join('\n');
    const link=document.createElement('a');link.href=URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'}));link.download=`qiyuan-comparison-${comparison.id}.csv`;link.click();URL.revokeObjectURL(link.href);}
  return <><PageHeading index="05" title="把季度变化拆成追赶与前沿移动" text="同一批场馆按编号配对；用两期各自与交叉参照，区分场馆追上标杆和标杆整体退步。"><a className="outline" href="#/sources">核对同期口径 +</a>{result&&<button className="outline" onClick={download}>下载比较CSV ↓</button>}</PageHeading>
  <ErrorNotice message={error} retry={()=>perform(loadResearch)}/>
  <div className="solver-layout">
    {canEdit(user)?<form className="research-form" onSubmit={e=>{e.preventDefault();perform(async()=>{const c=await createComparison(form);setSelected(c.id);setMessage(`比较 #${c.id} 已进入队列，完成后自动显示。`);await loadResearch();});}}>
      <h2>建立跨期比较档案</h2>
      <label>比较名称<input value={form.name} onChange={e=>setForm({...form,name:e.target.value})} required minLength={2}/></label>
      <label>前期参照集<select value={form.before_benchmark_id} onChange={e=>setForm({...form,before_benchmark_id:Number(e.target.value)})}>{lab.benchmarks.map(b=><option key={b.id} value={b.id}>{b.period} / {b.name} / {b.row_count}馆</option>)}</select></label>
      <label>后期参照集<select value={form.after_benchmark_id} onChange={e=>setForm({...form,after_benchmark_id:Number(e.target.value)})}>{lab.benchmarks.map(b=><option key={b.id} value={b.id}>{b.period} / {b.name} / {b.row_count}馆</option>)}</select></label>
      {(['inputs','outputs'] as const).map(kind=><fieldset key={kind}><legend>{kind==='inputs'?'投入维度':'产出维度'}<small>至少选1项</small></legend>{(kind==='inputs'?inputKeys:outputKeys).map(key=><label className="checkbox" key={key}><input type="checkbox" checked={form[kind].includes(key)} onChange={()=>toggle(kind,key)}/>{fields[key]}</label>)}</fieldset>)}
      <p className="input-note">两期必须按时间顺序且季度不同；投入产出口径在两期之间共用。只按场馆编号配对，单期场馆单列。源数据更新后请新建比较，旧档案按建立时的样本与指纹保留。</p>
      <button className="primary" disabled={busy||!form.inputs.length||!form.outputs.length||form.before_benchmark_id===form.after_benchmark_id}>提交跨期分解 →</button>{message&&<p className="success" role="status">{message}</p>}
    </form>:<section className="research-form"><h2>当前为只读联络权限</h2><p>可读取全部比较档案与结果；不能建立新的跨期比较。</p></section>}
    <aside className="model-sheet"><p className="eyebrow">MALMQUIST / CCR INPUT ORIENTED</p><h2>分数上升，<br/>未必是场馆追上了。</h2><div className="model-formula"><b>EC·TC</b><span>EC = θ_a(x_a) / θ_b(x_b)<br/>TC = sqrt(θ_b(x_b)/θ_a(x_b) · θ_b(x_a)/θ_a(x_a))<br/>TFP = EC · TC</span></div><ol><li><b>四类参照分数</b><p>两期各自用本期完整参照集求解，另加两组交叉参照。θ&gt;1 表示目标在另一期前沿之上，不裁剪成1。</p></li><li><b>追赶与前沿移动</b><p>EC 只描述场馆相对本期前沿的位置变化；TC 描述前沿本身的移动。二者相乘才是总变化。</p></li><li><b>不能比较就说明</b><p>零产出或交叉求解不可行时整条配对标记无法比较，返回空值，不填零也不硬算比值。</p></li></ol></aside>
  </div>
  <div className="run-selector"><label>比较档案<select value={selected} onChange={e=>setSelected(Number(e.target.value))}>{lab.comparisons.map(c=><option key={c.id} value={c.id}>#{c.id} {c.name}</option>)}</select></label>{comparison&&<StatusBadge status={comparison.status}/>}<span>{comparison&&`${benchmarkName(comparison.before_benchmark_id)} → ${benchmarkName(comparison.after_benchmark_id)}`}</span></div>
  {comparison?.status==='completed'&&result?<>
    <section className="comparison-summary">
      <div className="summary-metrics">
        <div><span>配对场馆</span><b>{summary?.paired_count}<small>馆 / 可比较 {summary?.comparable_count}</small></b></div>
        <div><span>上升 / 下降 / 持平</span><b>{summary?.improved_count} / {summary?.regressed_count} / {summary?.unchanged_count}<small>无法比较 {summary?.not_comparable_count}</small></b></div>
        <div><span>几何平均 追赶 EC</span><b>{number(summary?.geometric_mean_catch_up,3)}</b></div>
        <div><span>几何平均 前沿移动 TC</span><b>{number(summary?.geometric_mean_frontier_shift,3)}</b></div>
        <div><span>几何平均 总变化</span><b>{number(summary?.geometric_mean_total_change,3)}</b></div>
      </div>
      <p className="method-line">前期 {result.before.period as string} / 后期 {result.after.period as string}；投入口径 {result.inputs.map(k=>fields[k]).join('、')}；产出口径 {result.outputs.map(k=>fields[k]).join('、')}。共用的单位缩放系数已随档案保存。</p>
    </section>
    <section className="comparison-table">
      <div className="section-heading"><h2>按场馆编号配对的生产率分解</h2><span>EC × TC = 总变化 / 单位缩放不变</span></div>
      <div className="table-wrap"><table><thead><tr><th>场馆</th><th>θ_b(x_b)</th><th>θ_a(x_a)</th><th>θ_a(x_b)</th><th>θ_b(x_a)</th><th>追赶 EC</th><th>前沿移动 TC</th><th>总变化</th><th>解读</th></tr></thead><tbody>
        {pairs.map(p=><tr key={p.venue_code}><td><b>{p.venue_name}</b><small>{p.venue_code}</small></td>
          {scoreLabels.map(([key])=><td key={key}>{p.scores[key]?.theta==null?'—':number(p.scores[key].theta,4)}</td>)}
          {p.status==='comparable'?<><td>{number(p.catch_up,4)}</td><td>{number(p.frontier_shift,4)}</td><td>{number(p.total_change,4)}</td><td className={p.direction==='regressed'?'rust':p.direction==='improved'?'green':''}>{directionLabels[p.direction]||p.direction}</td></>
          :<td colSpan={4} className="rust">{p.reason}</td>}
        </tr>)}
      </tbody></table></div>
      <p className="input-note">θ_b(x_b) 前期目标对前期参照；θ_a(x_a) 后期目标对后期参照；θ_a(x_b) 与 θ_b(x_a) 为交叉参照。EC=θ_a(x_a)/θ_b(x_b)；TC=sqrt(θ_b(x_b)/θ_a(x_b)·θ_b(x_a)/θ_a(x_a))；总变化=EC·TC。θ&gt;1 只表示相对另一期前沿，不代表绝对表现。</p>
    </section>
    <div className="comparison-layout">
      <section className="comparison-table"><div className="section-heading"><h2>仅出现在单期的场馆</h2><span>不配对 / 不填比值</span></div>
        <div className="table-wrap"><table><thead><tr><th>场馆</th><th>所在期</th><th>人员工时</th><th>能源费用</th><th>到访人次</th><th>项目场次</th></tr></thead><tbody>
          {result.only_before.map((r)=><tr key={'b'+r.observation_id}><td><b>{r.venue_name}</b><small>{r.venue_code}</small></td><td>前期 {result.before.period as string}</td><td>{number(r.staff_hours,2)}</td><td>{number(r.energy_cost,2)}</td><td>{number(r.visits)}</td><td>{number(r.programs)}</td></tr>)}
          {result.only_after.map((r)=><tr key={'a'+r.observation_id}><td><b>{r.venue_name}</b><small>{r.venue_code}</small></td><td>后期 {result.after.period as string}</td><td>{number(r.staff_hours,2)}</td><td>{number(r.energy_cost,2)}</td><td>{number(r.visits)}</td><td>{number(r.programs)}</td></tr>)}
        </tbody></table></div>
        {!result.only_before.length&&!result.only_after.length&&<p className="input-note">两期场馆编号完全对应，没有单期场馆。</p>}
      </section>
      <section className="comparison-table"><div className="section-heading"><h2>如何读这一次比较</h2><span>口径与限制</span></div>
        <p className="method-line">总变化 &gt;1 表示相对生产率上升，但可能来自场馆追赶（EC），也可能来自前沿整体移动（TC）。如果多数场馆 EC 持平而 TC 下降，季度分数上升更可能是标杆退步，而不是场馆追上。比较只描述本次同期参照集与技术边界，不是绝对最优或资源削减依据。</p>
        <p className="input-note">零产出、交叉参照不可行或其他求解失败时，该配对显示“无法比较”并保留原因；不把空值当作0，也不对空值做比值。</p>
      </section>
    </div>
    <p className="fingerprint">COMPARISON SHA256 / {result.fingerprint} / 样本与口径已随档案固化</p>
  </>:<EmptyState title={comparison?.status==='failed'?'比较未完成':'等待跨期比较'} text={comparison?.error||'跨期比较会按队列自动刷新；请选择前后两个不同季度的参照集，或先建立比较档案。'}/>}
  </>
}
