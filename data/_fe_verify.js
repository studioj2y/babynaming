/* 零依赖前端验证：用最小 DOM 桩真实执行 v2/index.html 主脚本，
   专测新增的「生辰场景渲染/跳过」与「命盘卡片渲染」与「callAPI 带生辰」是否运行时报错。 */
const fs = require('fs');
const path = require('path');

const html = fs.readFileSync(path.join(__dirname, '..', 'v2', 'index.html'), 'utf-8');
const m = html.match(/<script[^>]*>([\s\S]*?)<\/script>/);
let script = m[1];
script += '\n;globalThis.__T={renderAsk,renderResult,SCENES,state,callAPI,go,transitionTo,buildWeights,TEACHER_PICK,TEACHER_DIM,DEFAULT_WEIGHTS};';

// ---- 最小 DOM 桩 ----
const store = {};
function makeEl(sel) {
  const rec = { _sel: sel, _html: '' };
  const handler = {
    get(t, p) {
      if (p === 'innerHTML') return rec._html;
      if (p === 'querySelector') return (s) => makeEl(sel + '>' + s);
      if (p === 'querySelectorAll') return () => [];
      if (p === 'classList') return { add() {}, remove() {}, toggle() {}, contains() { return false; } };
      if (p === 'style') return { setProperty() {}, removeProperty() {}, set() {} , get() { return ''; } };
      if (p === 'dataset') return {};
      if (p === 'value') return rec._v || '';
      if (p === 'textContent') return rec._tc || '';
      const noops = ['appendChild','removeChild','insertAdjacentElement','insertAdjacentText','remove','addEventListener','setAttribute','getAttribute','focus','click','getContext','setProperty','removeProperty','setAttributeNS','setAttribute','append'];
      if (noops.includes(p)) return () => {};
      return (...a) => makeEl(sel);
    },
    set(t, p, v) {
      if (p === 'innerHTML') { rec._html = v; store[sel] = v; }
      else if (p === 'value') rec._v = v;
      else if (p === 'textContent') rec._tc = v;
      return true;
    }
  };
  return new Proxy(rec, handler);
}
const document = {
  querySelector: (s) => makeEl(s),
  getElementById: (s) => makeEl('#' + s),
  createElement: () => makeEl('el'),
  createElementNS: () => makeEl('el'),
  addEventListener: () => {},
  documentElement: makeEl(':root'),
  body: makeEl('body'),
};
let lastFetch = null;
const fetchStub = (url, opts) => {
  lastFetch = { url, body: opts && opts.body };
  return Promise.resolve({ json: () => Promise.resolve({ names: [], meta: {} }) });
};
const noopTimer = () => 0;
const sandbox = {
  document, window: {}, console,
  setTimeout: (fn) => { try { fn && fn(); } catch (e) { throw e; } return 0; },
  setInterval: noopTimer, clearInterval: noopTimer, clearTimeout: noopTimer,
  requestAnimationFrame: (fn) => { try { fn && fn(); } catch (e) { throw e; } return 0; },
  fetch: fetchStub, JSON, Math, Date, Promise,
};

const run = new Function('document','window','setTimeout','setInterval','clearInterval','clearTimeout','requestAnimationFrame','fetch','console','JSON','Math','Date','Promise', script + '\n;return globalThis.__T;');
const T = run(document, sandbox.window, sandbox.setTimeout, sandbox.setInterval, sandbox.clearInterval, sandbox.clearTimeout, sandbox.requestAnimationFrame, fetchStub, console, JSON, Math, Date, Promise);

let ok = true;
function check(name, cond) { console.log((cond ? '✔ ' : '�’✘ ') + name); if (!cond) ok = false; }

try {
  // 1) 生辰场景渲染（可选 + 跳过按钮）
  T.state._actorReady = true;
  T.renderAsk(T.SCENES.s08b);
  const birthHtml = store['#scene'] || '';
  check('生辰场景渲染出日期输入', birthHtml.includes('type="date"'));
  check('生辰场景渲染出「跳过」按钮', birthHtml.includes('skip'));

  // 2) 命盘卡片渲染（带生辰的 meta）
  T.state.result = {
    names: [{ name: '林沐渊', total: 90.9, dims: { wuxing: 96 }, given_chars: ['沐','渊'], given_wx: ['水','水'],
             explain: [] }],
    meta: { has_birth: true, gz: ['甲辰','己巳','甲申','己巳'], day_master: '甲', day_master_wx: '木',
            strong: '弱', use_gods: ['木','水'], zodiac: '龙' }
  };
  T.renderResult();
  const resHtml = store['#result'] || '';
  check('结果页渲染出命盘卡片 .baziCard', resHtml.includes('baziCard'));
  check('命盘显示八字', resHtml.includes('甲辰') && resHtml.includes('己巳'));
  check('命盘显示日主/旺衰/喜用神', resHtml.includes('甲木') && resHtml.includes('身弱') && resHtml.includes('木、水'));

  // 3) callAPI 带生辰发送
  T.state.branch = 'A';
  T.state.birth = { year: 2024, month: 5, day: 20, hour: 10 };
  T.callAPI();
  const sent = lastFetch && lastFetch.body ? JSON.parse(lastFetch.body) : null;
  check('callAPI 发送 birth 字段', sent && sent.birth && sent.birth.year === 2024);

  // 4) callAPI 跳过生辰（birth=null）
  T.state.birth = null;
  T.callAPI();
  const sent2 = lastFetch && lastFetch.body ? JSON.parse(lastFetch.body) : null;
  check('callAPI 跳过时 birth=null', sent2 && sent2.birth === null);

  // 5) 主理老师场景渲染（teacherGrid + 7 位老师）
  T.state._actorReady = true;   // 模拟立绘登场就绪（真实流程中由 showActor 置位）
  T.renderAsk(T.SCENES.s08c);
  const tcHtml = store['#scene'] || '';
  check('主理老师场景渲染出 teacherGrid', tcHtml.includes('teacherGrid'));
  ['五行老师','语文老师','字源老师','数理老师','意境老师','八卦老师','星师综合'].forEach(nm=>{
    check('teacherGrid 含「'+nm+'」', tcHtml.includes(nm));
  });
  check('渲染后默认主理=星师综合(balance)', T.state.primaryTeacher==='balance');

  // 6) buildWeights 维度映射×WEIGHT_BOOST 正确
  const W = T.DEFAULT_WEIGHTS;
  const expect = {wuxing:W.wuxing*3, yuwen:W.pronounce*3, ziyuan:W.meaning*3, shuli:W.stroke*3, yijing:W.gender*3, bagua:W.zodiac*3};
  for(const [k,exp] of Object.entries(expect)){
    T.state.primaryTeacher = k;
    const w = T.buildWeights();
    check('buildWeights('+k+') → 维度权重×3', w && Math.abs((w[T.TEACHER_DIM[k]]||0) - exp) < 1e-9 && w[T.TEACHER_DIM[k]] > W[T.TEACHER_DIM[k]]);
  }
  T.state.primaryTeacher = 'balance';
  check('buildWeights(balance)=null', T.buildWeights()===null);
  T.state.primaryTeacher = undefined;
  check('buildWeights(undefined)=null', T.buildWeights()===null);

  // 7) callAPI 带主理权重发送
  T.state.branch = 'A';
  T.state.primaryTeacher = 'wuxing';
  T.callAPI();
  const sent3 = lastFetch && lastFetch.body ? JSON.parse(lastFetch.body) : null;
  check('callAPI 发送 weights（偏五行）', sent3 && sent3.weights && Math.abs(sent3.weights.wuxing - W.wuxing*3) < 1e-9);
  T.state.primaryTeacher = 'balance';
  T.callAPI();
  const sent4 = lastFetch && lastFetch.body ? JSON.parse(lastFetch.body) : null;
  check('callAPI 综合时 weights=null', sent4 && sent4.weights === null);

  console.log(ok ? '\n前端新增流程端到端验证：全部通过 ✔' : '\n前端验证存在失败项 ✘');
  process.exit(ok ? 0 : 1);
} catch (e) {
  console.log('�’✘ 运行时抛出异常：', e && e.stack ? e.stack.split('\n').slice(0,4).join('\n') : e);
  process.exit(1);
}
