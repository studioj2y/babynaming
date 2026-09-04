/* 零依赖前端验证：用最小 DOM 桩真实执行 v2/index.html 主脚本，
   覆盖本轮新增/改写的流程：
   - 生辰场景（日期+时辰等大、继续按钮初始置灰、跳过文案）
   - 八字弹窗渲染（baziCard）
   - 主理老师轮播（s08c2：一位一卡 + 左右箭头 + 星师综合底部按钮）
   - 无生辰时轮播剔除生肖老师；有生辰则含生肖老师
   - buildWeights 维度映射（生肖相宜→zodiac）×WEIGHT_BOOST
   - callAPI：A 线带主理权重；B 线只带生辰、weights=null（不加主理）
   - 结果页命盘卡片、goHome 复位
   用法：node data/_fe_verify.js  */
const fs = require('fs');
const path = require('path');

const html = fs.readFileSync(path.join(__dirname, '..', 'v2', 'index.html'), 'utf-8');
const m = html.match(/<script[^>]*>([\s\S]*?)<\/script>/);
let script = m[1];
script += '\n;globalThis.__T={renderAsk,renderResult,renderScene,renderCarousel,moveCarousel,teacherCarouselList,fetchBazi,_returnTarget,buildWeights,callAPI,go,proceed,goHome,SCENES,state,TEACHER_PICK,TEACHER_DIM,DEFAULT_WEIGHTS,WEIGHT_BOOST,CHAR};';

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
      if (p === 'style') return { setProperty() {}, removeProperty() {}, set() {}, get() { return ''; } };
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
function check(name, cond) { console.log((cond ? '✔ ' : '✘ ') + name); if (!cond) ok = false; }

try {
  // ---- 1) 生辰场景：日期+时辰等大、继续按钮初始置灰、跳过文案 ----
  T.state._actorReady = true;
  T.renderAsk(T.SCENES.s08b);
  const birthHtml = store['#scene'] || '';
  check('生辰场景渲染出日期输入 type="date"', birthHtml.includes('type="date"'));
  check('生辰场景用 birthWrap（日期/时辰等大）', birthHtml.includes('birthWrap'));
  check('生辰场景继续按钮初始 disabled（门控：须填日期）', birthHtml.includes('disabled'));
  check('生辰场景含跳过按钮「暂不观察生辰八字」', birthHtml.includes('暂不观察生辰八字'));
  check('时辰下拉含「12 时」默认项', birthHtml.includes('12 时'));

  // ---- 2) 八字弹窗：带 state.bazi 渲染 baziCard ----
  T.state.bazi = { gz:['甲辰','己巳','甲申','己巳'], day_master:'甲', day_master_wx:'木',
                   strong:'弱', use_gods:['木','水'], zodiac:'龙' };
  T.renderAsk(T.SCENES.s08b_result);
  const baziHtml = store['#scene'] || '';
  check('八字弹窗渲染出 .baziCard', baziHtml.includes('baziCard'));
  check('八字弹窗显示八字干支', baziHtml.includes('甲辰') && baziHtml.includes('己巳'));
  check('八字弹窗显示日主/旺衰/喜用神', baziHtml.includes('甲木') && baziHtml.includes('身弱') && baziHtml.includes('木、水'));
  check('八字弹窗显示生肖', baziHtml.includes('生肖 龙'));

  // ---- 3) 主理轮播列表：无生辰剔除生肖老师 ----
  T.state.birth = null;
  const noBirth = T.teacherCarouselList();
  check('无生辰：轮播不含生肖老师', !noBirth.some(t=>t.v==='shengxiao'));
  check('无生辰：轮播含 5 位主理老师', noBirth.length === 5);
  check('无生辰：仍含星师综合对应键（balance 走按钮，不在此列表）', !noBirth.some(t=>t.v==='balance'));

  // ---- 4) 主理轮播列表：有生辰含生肖老师 ----
  T.state.birth = { year: 2024, month: 5, day: 20, hour: 12 };
  const withBirth = T.teacherCarouselList();
  check('有生辰：轮播含生肖老师', withBirth.some(t=>t.v==='shengxiao'));
  check('有生辰：轮播含 6 位主理老师', withBirth.length === 6);

  // ---- 5) 轮播场景渲染：一位一卡 + 箭头 + 星师综合底部按钮 ----
  T.state._actorReady = true;
  T.renderCarousel(T.SCENES.s08c2);
  const carHtml = store['#scene'] || '';
  check('轮播渲染出 .carousel', carHtml.includes('carousel'));
  check('轮播渲染出 tCard（一位一卡）', carHtml.includes('tCard'));
  check('轮播渲染出左右箭头 arrL/arrR', carHtml.includes('arrL') && carHtml.includes('arrR'));
  check('轮播渲染出「选定这位老师」按钮', carHtml.includes('pickBtn'));
  check('轮播渲染出「星师综合」底部按钮', carHtml.includes('balanceBtn'));
  check('轮播首屏立绘键为列表第一位（wuxing）', T.state._carouselList[0].v === 'wuxing');

  // ---- 6) moveCarousel 切换不抛错且索引变化 ----
  const before = T.state._teacherIdx;
  T.moveCarousel(1);
  check('moveCarousel(+1) 切到下一老师', T.state._teacherIdx === (before + 1) % T.state._carouselList.length);
  T.moveCarousel(-1);
  check('moveCarousel(-1) 切回原位', T.state._teacherIdx === before);

  // ---- 7) buildWeights 维度映射（生肖相宜→zodiac）×WEIGHT_BOOST ----
  const W = T.DEFAULT_WEIGHTS, BOOST = T.WEIGHT_BOOST;
  const expect = { wuxing:W.wuxing, yuwen:W.pronounce, ziyuan:W.meaning, shuli:W.stroke, yijing:W.gender, shengxiao:W.zodiac };
  for (const [k, base] of Object.entries(expect)) {
    T.state.primaryTeacher = k;
    const w = T.buildWeights();
    const dim = T.TEACHER_DIM[k];
    check('buildWeights('+k+') → '+dim+' ×'+BOOST, w && Math.abs(w[dim] - base*BOOST) < 1e-9 && w[dim] > base);
  }
  T.state.primaryTeacher = 'balance';
  check('buildWeights(balance)=null', T.buildWeights() === null);
  T.state.primaryTeacher = undefined;
  check('buildWeights(undefined)=null', T.buildWeights() === null);

  // ---- 8) callAPI：A 线带主理权重 ----
  T.state.branch = 'A';
  T.state.primaryTeacher = 'wuxing';
  T.callAPI();
  const a1 = lastFetch && lastFetch.body ? JSON.parse(lastFetch.body) : null;
  check('A 线 callAPI → /api/generate', a1 && lastFetch.url === '/api/generate');
  check('A 线 callAPI 发送 weights（偏五行 ×'+BOOST+'）', a1 && a1.weights && Math.abs(a1.weights.wuxing - W.wuxing*BOOST) < 1e-9);
  check('A 线 callAPI 发送 birth', a1 && a1.birth && a1.birth.year === 2024);

  // ---- 9) callAPI：B 线只带生辰、weights=null（不加主理） ----
  T.state.branch = 'B';
  T.state.primaryTeacher = undefined;   // B 线不进轮播，primaryTeacher 不设置
  T.callAPI();
  const b1 = lastFetch && lastFetch.body ? JSON.parse(lastFetch.body) : null;
  check('B 线 callAPI → /api/analyze', b1 && lastFetch.url === '/api/analyze');
  check('B 线 callAPI 发送 birth', b1 && b1.birth && b1.birth.year === 2024);
  check('B 线 callAPI weights=null（不加主理）', b1 && b1.weights === null);

  // ---- 10) 结果页命盘卡片 ----
  T.state.branch = 'A';
  T.state.primaryTeacher = 'wuxing';
  T.state.result = {
    names: [{ name:'林沐渊', total:90.9, dims:{ wuxing:96 }, given_chars:['沐','渊'], given_wx:['水','水'], explain:[] }],
    meta: { has_birth:true, gz:['甲辰','己巳','甲申','己巳'], day_master:'甲', day_master_wx:'木', strong:'弱', use_gods:['木','水'], zodiac:'龙' }
  };
  T.renderResult();
  const resHtml = store['#result'] || '';
  check('结果页渲染出命盘卡片 .baziCard', resHtml.includes('baziCard'));
  check('结果页命盘显示八字干支', resHtml.includes('甲辰') && resHtml.includes('己巳'));

  // ---- 11) goHome 复位 bazi / 轮播态 ----
  T.state.bazi = { gz:['x'] }; T.state._carouselList = []; T.state._teacherIdx = 2;
  T.goHome();
  check('goHome 清除 bazi', T.state.bazi === undefined);
  check('goHome 清除 _carouselList', !('_carouselList' in T.state));
  check('goHome 清除 _teacherIdx', !('_teacherIdx' in T.state));

  console.log(ok ? '\n前端新增/改写流程端到端验证：全部通过 ✔' : '\n前端验证存在失败项 ✘');
  process.exit(ok ? 0 : 1);
} catch (e) {
  console.log('✘ 运行时抛出异常：', e && e.stack ? e.stack.split('\n').slice(0,5).join('\n') : e);
  process.exit(1);
}
