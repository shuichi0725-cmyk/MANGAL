import { TONE_MS, TONE_R, TONE_STEP, pickTone, toneName, toneOrder, toneQ, type ToneKey } from "./compass";

// ★背景 = 中央の本の書影を網点の形にくり抜いたもの(依頼書「背景 = 書影の網点」)。
//   楽天の書影サーバーは別ドメインからの読み取りを許していない(Access-Control-Allow-Origin 無し)ので
//   getImageData で点の色を読むことはできない。 → 重ね合わせで作る:
//   画面外の canvas に書影を描く → 同じ canvas に「その瞬間の半径の円の集まり」を1本の path で描き
//   destination-in で書影を点の形にくり抜く → 旧・新の2枚を表の canvas に重ねる。
//   画素を読まないので、別ドメイン画像で canvas が汚染されても描画はできる。
//   明るさ・彩度は canvas 要素の CSS filter(compass.css)。

type Role = "in" | "out" | null;
type Layer = { img: HTMLImageElement | null; role: Role };

/** 背景が「糸を手繰る」ですべる量(本の0.6倍)と、その始まり。 */
type Flow = { x: number; y: number; t0: number };

const FLOW_MS = 750;
/** すべっても書影の端が見えないよう、上下左右に余白を取って敷く */
const OVERSCAN = 110;

function ease(t: number): number {
  // cubic-bezier(.4,0,.2,1) 相当のなめらかな加減速
  return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
}

export class Halftone {
  private cv: HTMLCanvasElement;
  private off: HTMLCanvasElement;
  private w = 0;
  private h = 0;
  private dpr = 1;
  private cx = 0;
  private cy = 0;
  private cols = 0;
  private rows = 0;
  private cur: Layer = { img: null, role: null };
  private old: Layer | null = null;
  private order: Float32Array | null = null;
  private orderKey: ToneKey | null = null;
  private t0 = 0;
  private raf = 0;
  private last: ToneKey | null = null;
  private flow: Flow | null = null;
  private outOff: [number, number] = [0, 0];
  private token = 0;
  private dead = false;
  reduce = false;
  onTone: ((name: string) => void) | null = null;

  constructor(cv: HTMLCanvasElement) {
    this.cv = cv;
    this.off = document.createElement("canvas");
  }

  /** 画面の大きさと羅針盤の中央(px)。 */
  resize(w: number, h: number, cx: number, cy: number): void {
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    const changed = w !== this.w || h !== this.h || dpr !== this.dpr;
    this.w = w;
    this.h = h;
    this.dpr = dpr;
    if (cx !== this.cx || cy !== this.cy) this.orderKey = null;
    this.cx = cx;
    this.cy = cy;
    if (changed) {
      for (const c of [this.cv, this.off]) {
        c.width = Math.max(1, Math.round(w * dpr));
        c.height = Math.max(1, Math.round(h * dpr));
      }
      this.cols = Math.ceil(w / TONE_STEP);
      this.rows = Math.ceil(h / TONE_STEP);
      this.orderKey = null;
    }
    if (this.orderKey === null && this.last && this.raf) this.makeOrder(this.last);
    if (!this.raf) this.draw(null);
  }

  /** 中央の本が変わった。 flow = 背景がすべる量(px・本の0.6倍・世界と同じ向き)。 */
  setCover(url: string | null, flow: { x: number; y: number } | null = null): void {
    const tok = ++this.token;
    if (flow && !this.reduce && (flow.x || flow.y)) {
      // 今見えている書影は読み込みを待たずにすべり出す
      this.cur.role = "out";
      if (this.old) this.old.role = "out";
      this.flow = { x: flow.x, y: flow.y, t0: performance.now() };
      this.loop();
    }
    const done = (img: HTMLImageElement | null) => {
      if (tok !== this.token || this.dead) return;
      this.start(img);
    };
    if (!url) {
      done(null);
      return;
    }
    const img = new Image();
    img.decoding = "async";
    img.onload = () => done(img);
    img.onerror = () => done(null);
    img.src = url;
  }

  destroy(): void {
    this.dead = true;
    cancelAnimationFrame(this.raf);
    this.raf = 0;
  }

  private makeOrder(key: ToneKey): void {
    this.order = toneOrder(key, this.cols, this.rows, this.cx / TONE_STEP, this.cy / TONE_STEP);
    this.orderKey = key;
  }

  private start(img: HTMLImageElement | null): void {
    const flowing = !!this.flow && performance.now() - this.flow.t0 < FLOW_MS;
    this.old = this.cur.img ? { img: this.cur.img, role: this.cur.role } : null;
    this.cur = { img, role: flowing ? "in" : null };
    if (this.reduce || (!this.old && !img)) {
      this.old = null;
      this.flow = null;
      this.cur.role = null;
      this.t0 = 0;
      if (!this.raf) this.draw(null);
      return;
    }
    const key = pickTone(this.last);
    this.last = key;
    this.makeOrder(key);
    this.onTone?.(toneName(key));
    this.t0 = performance.now();
    this.loop();
  }

  private loop(): void {
    if (this.raf || this.dead) return;
    const tick = () => {
      this.raf = 0;
      if (this.dead) return;
      const now = performance.now();
      const p = this.t0 ? Math.min(1, (now - this.t0) / TONE_MS) : null;
      const flowOn = !!this.flow && now - this.flow.t0 < FLOW_MS;
      this.draw(p);
      if (p !== null && p >= 1) {
        this.old = null;
        this.t0 = 0;
      }
      if (!flowOn && this.flow) {
        this.outOff = [this.flow.x, this.flow.y]; // すべり終えた旧書影はその位置のまましぼむ
        this.flow = null;
        if (this.cur.role === "in") this.cur.role = null;
      }
      if ((p !== null && p < 1) || flowOn) this.raf = requestAnimationFrame(tick);
      else this.draw(null);
    };
    this.raf = requestAnimationFrame(tick);
  }

  private offset(role: Role): [number, number] {
    const f = this.flow;
    if (!role) return [0, 0];
    if (!f) return role === "out" ? this.outOff : [0, 0];
    const e = ease(Math.min(1, (performance.now() - f.t0) / FLOW_MS));
    return role === "out" ? [f.x * e, f.y * e] : [f.x * (e - 1), f.y * (e - 1)];
  }

  /** p = 入れ替えの全体の進み(null = 静止: 今の書影だけを満点で)。 */
  private draw(p: number | null): void {
    const ctx = this.cv.getContext("2d");
    const octx = this.off.getContext("2d");
    if (!ctx || !octx || !this.w) return;
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, this.cv.width, this.cv.height);
    const mixing = p !== null && !!this.order && !!this.old;
    const layers: [Layer, boolean][] = [];
    if (mixing && this.old?.img) layers.push([this.old, false]);
    if (this.cur.img) layers.push([this.cur, true]);
    if (!layers.length) return;

    // 点の半径を1回だけ計算して、旧・新の2本の path を作る
    const { cols, rows } = this;
    const st = TONE_STEP;
    const R = TONE_R;
    const TAU = Math.PI * 2;
    const pathOld = new Path2D();
    const pathNew = new Path2D();
    for (let j = 0; j < rows; j++)
      for (let i = 0; i < cols; i++) {
        const k = j * cols + i;
        const x = i * st + st / 2;
        const y = j * st + st / 2;
        const q = p === null || !this.order ? 1 : toneQ(p, this.order[k] ?? 0);
        const rn = R * q;
        const ro = R * (1 - q);
        if (rn > 0.3) {
          pathNew.moveTo(x + rn, y);
          pathNew.arc(x, y, rn, 0, TAU);
        }
        if (mixing && ro > 0.3) {
          pathOld.moveTo(x + ro, y);
          pathOld.arc(x, y, ro, 0, TAU);
        }
      }

    for (const [layer, isNew] of layers) {
      const img = layer.img as HTMLImageElement;
      const iw = img.naturalWidth || img.width;
      const ih = img.naturalHeight || img.height;
      if (!iw || !ih) continue;
      octx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
      octx.globalCompositeOperation = "source-over";
      octx.clearRect(0, 0, this.w, this.h);
      const s = Math.max((this.w + OVERSCAN * 2) / iw, (this.h + OVERSCAN * 2) / ih);
      const dw = iw * s;
      const dh = ih * s;
      const [ox, oy] = this.offset(layer.role);
      octx.drawImage(img, (this.w - dw) / 2 + ox, (this.h - dh) / 2 + oy, dw, dh);
      octx.globalCompositeOperation = "destination-in";
      octx.fill(isNew ? pathNew : pathOld);
      octx.globalCompositeOperation = "source-over";
      ctx.drawImage(this.off, 0, 0);
    }
  }
}
