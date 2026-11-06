// 使い方(/guide)の本文。 静的な HTML(見本 2026-11-03 から生成)。 写真 = public/guide/*.jpg(本番画面をスマホ幅で撮影)
// ★写真を撮り直したら注記の枠(.mark の %)も一緒に直す。
export const GUIDE_BODY = `

<h1>使い方</h1>
<p class="lead">MANGAL で次の一冊を見つける2つの方法。題名がわかっている時は「検索」、決まっていない時は「羅針盤」。</p>
<nav class="toc"><a href="#search">🔍 検索</a><a href="#compass" class="cp">🧭 羅針盤</a></nav>

<!-- ───────── 検索 ───────── -->
<section id="search">
<h2><svg viewBox="0 0 24 24" fill="none" stroke="#d9f843" stroke-width="2"><circle cx="11" cy="11" r="7"/><path d="M20 20l-4-4"/></svg>検索</h2>
<p class="sec-lead">題名・よみがな・ローマ字・作者名のどれでも探せます。</p>

<div class="step">
<h3><span class="num">1</span>検索の窓に入れて「検索」</h3>
<p>トップページの窓か、上の「検索」から。ひらがなでも、ローマ字でもかまいません。</p>
<div class="stage s-anim"><span class="anim-label">ANIMATION</span>
  <div class="s-box"><div class="s-input"><span class="pr">mangal&gt;</span><span class="s-type">のだめ</span><span class="s-caret"></span></div><div class="s-btn">検索</div></div>
  <div class="s-hand"></div>
  <div class="s-res">
    <div class="s-card"><div class="s-cov" style="background:linear-gradient(135deg,#e85d3b,#f6d34a)"></div><div><div class="t">のだめカンタービレ</div><div class="a">二ノ宮知子 2002〜2010 完結</div></div></div>
    <div class="s-card"><div class="s-cov" style="background:linear-gradient(135deg,#3b7be8,#9ad1f5)"></div><div><div class="t">○○○○○</div><div class="a">作者名 2016〜2017 完結</div></div></div>
    <div class="s-card"><div class="s-cov" style="background:linear-gradient(135deg,#8a3be8,#f59ad1)"></div><div><div class="t">○○○○○○</div><div class="a">作者名 2015〜2022 完結</div></div></div>
  </div>
</div>
<div class="kw"><span>のだめ</span><span>nodame</span><span>二ノ宮</span><span>ノダメ</span></div>
<p class="cap">↑ どれでも同じ作品が出ます</p>
</div>

<div class="step">
<h3><span class="num">2</span>カテゴリで1回しぼる</h3>
<p>検索のあとに、カテゴリ(アニメ化・完結・連載中・少年・女性…)を押すと、1回で結果がしぼれます。もっと細かい条件は次の「フィルター」で。</p>
<div class="shot"><img src="/guide/browse.jpg" width="640" height="668" loading="lazy" decoding="async" alt="検索の画面"><div class="mark" style="left:2.8%;top:21.9%;width:94.4%;height:11.6%"><b>1</b></div><div class="mark" style="left:3.7%;top:46.6%;width:92.6%;height:34.7%"><b>2</b></div><div class="mark" style="left:3.7%;top:87.5%;width:92.6%;height:9.4%"><b>3</b></div></div>
<p class="cap">① 検索の窓 ② カテゴリ(数字はその件数) ③ フィルター</p>
</div>

<div class="step" id="filter">
<h3><span class="num">3</span>フィルターで細かく絞る</h3>
<p>カテゴリの下の「⚙ フィルターで絞り込む」を押すと、条件の札がならんだ画面が開きます。札を押すたびに結果が絞られ、いちばん下のボタンの数字がすぐ変わります。</p>
<div class="shot"><img src="/guide/f1.jpg" width="640" height="1381" loading="lazy" decoding="async" alt="フィルターの画面"><div class="mark" style="left:3.9%;top:9.2%;width:92.1%;height:8.2%"><b>1</b></div><div class="mark" style="left:54.0%;top:43.5%;width:18.9%;height:3.7%"><b>2</b></div><div class="mark" style="left:65.9%;top:23.0%;width:20.9%;height:3.4%"><b>3</b></div><div class="mark" style="left:4.9%;top:64.8%;width:90.1%;height:3.9%"><b>4</b></div><div class="mark" style="left:3.9%;top:92.7%;width:92.1%;height:5.5%"><b>5</b></div></div>
<p class="cap">① 選んでいる条件(×で1つずつ外す・「条件をリセット」で全部) ② 選んだ札は光る ③ 札の数字 = いまの条件に足した時に残る作品数 ④ 要素・出版社・連載誌・著者は押すと開く ⑤ 押すと一覧にもどる</p>
<table class="ftab">
<tr><th>種類</th><td>アニメ化作品のみ・受賞作品のみ</td></tr>
<tr><th>連載状態</th><td>完結・連載中・休載</td></tr>
<tr><th>巻数</th><td>1巻のみ / 2〜5巻 / 6〜10巻 / 11〜15巻 / 16〜20巻 / 21巻以上</td></tr>
<tr><th>分野</th><td>少年・少女・青年・女性・児童</td></tr>
<tr><th>ジャンル</th><td>アクション・恋愛・ミステリー・グルメ など32種</td></tr>
<tr><th>創刊</th><td>1巻が出た年代</td></tr>
<tr><th>要素</th><td>バンド・料理・成長物語 など、ジャンルより細かい特徴</td></tr>
<tr><th>出版社・連載誌・著者</th><td>名前の一覧から選ぶ(著者は五十音)</td></tr>
<tr><th>並び順</th><td>標準・年代(新しい順/古い順)・タイトル五十音・巻数の多い順</td></tr>
</table>
<div class="tip"><b>札の重なり方:</b> ジャンルと要素は「ぜんぶ持っている作品」にしぼります(音楽+コメディ = 両方ある作品)。連載状態・巻数・分野・出版社は「どれか」です(少年+青年 = どちらか)。数字が 0 の札は薄く表示されます。</div>
</div>

<div class="step">
<h3><span class="num">4</span>要素で「こういうの」を探す</h3>
<p>ジャンルだけでは広すぎる時は「要素」を開きます。いまの条件の中で多い順にならぶので、そのまま「この中にどんな話があるか」の目次にもなります。</p>
<div class="shot"><img src="/guide/f2.jpg" width="640" height="617" loading="lazy" decoding="async" alt="要素を開いたところ"><div class="mark" style="left:4.0%;top:3.1%;width:92.0%;height:8.9%"><b>1</b></div><div class="mark" style="left:4.0%;top:14.1%;width:19.7%;height:7.8%"><b>2</b></div></div>
<p class="cap">完結 × 音楽 で絞った後に要素を開いたところ。① 押すと開く ② バンド・アイドル・クラシック音楽…から選べる</p>
<div class="recipe">
<div class="rh">組み合わせの例</div>
<div><span>完結</span><span>21巻以上</span><span>スポーツ</span><em>→ 長く一気に読める完結スポーツ</em></div>
<div><span>1巻のみ</span><span>恋愛</span><em>→ 1冊で終わる恋の話</em></div>
<div><span>ジャンル:グルメ</span><span>要素:お仕事</span><em>→ 料理の仕事もの</em></div>
</div>
<div class="tip">絞った結果の画面の「共有」を押すと、その条件のまま友だちに送れます。</div>
</div>

<div class="step">
<h3><span class="num">5</span>一覧表で並べかえる</h3>
<p>全作品を表で見たい時は ≡メニューの「一覧表」。人気順・50音順・開始年・巻数で並べかえられ、同じフィルターも使えます。</p>
<div class="tip">うまく出ない時: 「の」「ノ」の違いや、のばし棒(ー)を抜いて試してください。</div>
</div>
<a class="cta" href="/browse">検索をひらく ›</a>
</section>

<!-- ───────── 羅針盤 ───────── -->
<section id="compass" class="cpsec">
<h2><svg viewBox="0 0 24 24" fill="none" stroke="#ff5a5a" stroke-width="2"><circle cx="12" cy="12" r="9"/><path class="needle" d="M15.5 8.5l-2 5-5 2 2-5z"/></svg>羅針盤</h2>
<p class="sec-lead">1冊の本から「同じ作者」「同じ雑誌」「同じ年」「似た要素」の糸をたどって、次の本へ旅する道具です。読みたい本が決まっていない時に。</p>

<div class="step">
<h3><span class="num">1</span>ひらく</h3>
<p>この赤い針のマークが入口です。作品ページから開くと、その本が真ん中に来ます。</p>
<div class="ways">
  <div class="way"><span class="cicon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/><path class="needle" d="M15.5 8.5l-2 5-5 2 2-5z"/></svg></span><br>上の「羅針盤」</div>
  <div class="way"><span class="cicon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/><path class="needle" d="M15.5 8.5l-2 5-5 2 2-5z"/></svg></span><br>作品ページの<br>赤いボタン</div>
  <div class="way"><span class="cicon"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/><path class="needle" d="M15.5 8.5l-2 5-5 2 2-5z"/></svg></span><br>≡メニュー</div>
</div>
</div>

<div class="step">
<h3><span class="num">2</span>画面の見かた</h3>
<div class="shot"><img src="/guide/main.jpg" width="640" height="1340" loading="lazy" decoding="async" alt="羅針盤の画面"><div class="mark" style="left:39.3%;top:40.7%;width:21.4%;height:14.2%"><b>1</b></div><div class="mark" style="left:43.7%;top:23.0%;width:12.6%;height:8.4%"><b>2</b></div><div class="mark" style="left:0.0%;top:4.9%;width:100.0%;height:6.2%"><b>3</b></div><div class="mark" style="left:0.0%;top:0.0%;width:100.0%;height:4.9%"><b>4</b></div><div class="mark" style="left:0.5%;top:88.1%;width:99.1%;height:11.7%"><b>5</b></div></div>
<p class="cap">① いまの本 ② 周りの本(=糸の入口) ③ 旅路(たどった本) ④ 糸の色の切り替え ⑤ いま選んでいる本の紹介</p>
<div class="legend">
  <div><i style="background:var(--c-author)"></i>作者が同じ</div>
  <div><i style="background:var(--c-mag)"></i>同じ雑誌</div>
  <div><i style="background:var(--c-year)"></i>同じ年に開始</div>
  <div><i style="background:var(--c-theme)"></i>要素(料理・成長物語…)</div>
  <div><i style="background:var(--c-genre)"></i>ジャンル</div>
  <div><i style="background:var(--accent)"></i>よく似たジャンル</div>
  <div><i style="background:var(--c-simel)"></i>似た要素</div>
</div>
</div>

<div class="step">
<h3><span class="num">3</span>真ん中を押すと、その本の紹介</h3>
<p>真ん中の本を押すと、その本の紹介が<b>漫画の1ページ(コマ割り)</b>になって重なります。題名・作者・キャッチ・巻数・ジャンル・要素がひと目でわかります。</p>
<div class="stage k-anim"><span class="anim-label">ANIMATION</span>
  <div class="k-path"><i style="background-image:url(https://thumbnail.image.rakuten.co.jp/@0_mall/book/cabinet/9681/9784063259681.jpg?_ex=120x120)"></i><span style="color:#888;font-size:11px">旅路</span></div>
  <div class="k-ring">
    <div class="thr" style="width:120px;transform:rotate(-90deg);background:var(--accent)"></div>
    <div class="thr" style="width:120px;transform:rotate(-30deg);background:var(--c-mag)"></div>
    <div class="thr" style="width:120px;transform:rotate(30deg);background:var(--c-genre)"></div>
    <div class="thr" style="width:120px;transform:rotate(90deg);background:var(--c-year)"></div>
    <div class="thr" style="width:120px;transform:rotate(150deg);background:var(--c-theme)"></div>
    <div class="thr" style="width:120px;transform:rotate(210deg);background:var(--c-author)"></div>
    <div class="bk" style="top:calc(48% - 120px);background:linear-gradient(135deg,#d64,#fb5)"></div>
    <div class="bk" style="left:calc(50% + 104px);top:calc(48% - 60px);background:linear-gradient(135deg,#2a8,#9e6)"></div>
    <div class="bk" style="left:calc(50% + 104px);top:calc(48% + 60px);background:linear-gradient(135deg,#c73,#fc8)"></div>
    <div class="bk" style="top:calc(48% + 120px);background:linear-gradient(135deg,#63c,#c9f)"></div>
    <div class="bk" style="left:calc(50% - 104px);top:calc(48% + 60px);background:linear-gradient(135deg,#27c,#8cf)"></div>
    <div class="bk" style="left:calc(50% - 104px);top:calc(48% - 60px);background:linear-gradient(135deg,#3b7be8,#9ad1f5)"></div>
    <div class="bk k-center" style="background-image:url(https://thumbnail.image.rakuten.co.jp/@0_mall/book/cabinet/9681/9784063259681.jpg?_ex=200x200)"></div>
  </div>
  <div class="k-hand"></div>
  <div class="k-wrap"><div class="k-page">
    <div class="ck ck-cov" style="--d:0s"><img src="https://thumbnail.image.rakuten.co.jp/@0_mall/book/cabinet/9681/9784063259681.jpg?_ex=400x400" alt=""></div>
    <div class="ck ck-title" style="--d:.15s"><div class="ck-t">のだめカンタービレ</div><div class="ck-kana">ノダメカンタービレ</div><div class="ck-auth">二ノ宮知子</div></div>
    <div class="ck ck-say" style="--d:.3s"><div class="ck-bubble">指揮者を志すエリート音大生が出会ったのは、料理も片付けもできないのに類まれなピアノを奏でる風変わりな少女。凸凹コンビが奏でる音楽ラブコメ。</div></div>
    <div class="ck ck-data" style="--d:.45s">
      <div class="ck-row"><b class="ck-years">2002〜2010 完結</b><b class="ck-vols">全25巻</b><span class="ck-stamp">アニメ化</span></div>
      <div class="ck-meta">講談社 ・ 女性</div>
      <div class="ck-tags"><span class="ck-tag g">コメディ</span><span class="ck-tag g">ギャグ</span><span class="ck-tag g">音楽</span><span class="ck-tag g">恋愛</span><span class="ck-tag g">ラブコメ</span><span class="ck-tag g">日常</span><span class="ck-tag">ミュージカル</span><span class="ck-tag">言葉の壁</span><span class="ck-tag">成長物語</span><span class="ck-tag">オタク文化</span><span class="ck-tag">クラシック音楽</span><span class="ck-tag">大学</span><span class="ck-tag">ツンデレ</span></div>
      <div class="ck-btns"><span class="dt">詳細 ›</span><span class="kd">Kindle</span><span class="az">Amazon</span><span class="cl">閉じる</span></div>
    </div>
  </div></div>
  <div class="k-step"><span class="s1">① 真ん中の本を押す</span><span class="s2">② その本の紹介がコマ割りで出る</span><span class="s3">③「閉じる」か外を押すと輪にもどる</span></div>
</div>
<p class="cap">「詳細 ›」で作品ページへ。Kindle・Amazon で本を探せます。</p>
<div class="tip">周りの本を選んでいる時に真ん中を押すと、紹介は出ずに選択が外れます。</div>
</div>

<div class="step">
<h3><span class="num">4</span>糸を広げる</h3>
<p>周りの本は「糸の入口」です。下の文字が糸の種類と名前、数字はその糸でつながる本の数。<b>作者・雑誌・年・似たジャンル・似た要素</b>の入口は、1回押すとその糸の本がまわりに一気に広がります。</p>
<div class="shot"><img src="/guide/c3.jpg" width="640" height="982" loading="lazy" decoding="async" alt="糸を広げたところ"><div class="mark" style="left:1.9%;top:16.1%;width:13.2%;height:4.2%"><b>1</b></div><div class="mark" style="left:16.0%;top:16.1%;width:12.8%;height:4.2%"><b>2</b></div><div class="mark" style="left:29.7%;top:16.1%;width:17.0%;height:4.2%"><b>3</b></div><div class="mark" style="left:47.7%;top:16.1%;width:16.6%;height:4.2%"><b>4</b></div><div class="mark" style="left:65.2%;top:16.1%;width:10.6%;height:4.2%"><b>5</b></div></div>
<p class="cap">広げた後の道具: ① ✕ 閉じる(輪にもどる) ② 年表(古い順にならべ直す) ③ ⚗ さらに絞る ④ 次を見る(続きの本) ⑤ ◎ 回(本が多い時は何回かに分けて見せる。押すと好きな回へ)</p>
</div>

<div class="step">
<h3><span class="num">5</span>1冊選んで、もう1回で進む</h3>
<p>広がった本を1回押すと、下に紹介が出ます。気になったらもう1回押す(または「〈糸〉の糸で進む →」)と、その本が真ん中に来て、新しい糸が広がります。</p>
<div class="shot"><img src="/guide/c8.jpg" width="640" height="1206" loading="lazy" decoding="async" alt="本を選んだところ"><div class="mark" style="left:32.1%;top:24.9%;width:36.3%;height:27.0%"><b>1</b></div><div class="mark" style="left:15.6%;top:96.0%;width:37.4%;height:3.1%"><b>2</b></div></div>
<p class="cap">① 選んだ本が大きくなる ② ここを押しても進める</p>
<div class="stage c-anim"><span class="anim-label">ANIMATION</span>
  <div class="c-path"><i style="background:linear-gradient(135deg,#e85d3b,#f6d34a)"></i><i class="p2" style="background:linear-gradient(135deg,#3b7be8,#9ad1f5)"></i><span class="dots">…</span></div>
  <div class="ring">
    <div class="thr" style="width:120px;transform:rotate(-90deg);background:var(--accent)"></div>
    <div class="thr" style="width:120px;transform:rotate(-30deg);background:var(--c-mag)"></div>
    <div class="thr" style="width:120px;transform:rotate(30deg);background:var(--c-genre)"></div>
    <div class="thr" style="width:120px;transform:rotate(90deg);background:var(--c-year)"></div>
    <div class="thr" style="width:120px;transform:rotate(150deg);background:var(--c-theme)"></div>
    <div class="thr" style="width:120px;transform:rotate(210deg);background:var(--c-author)"></div>
    <div class="bk" style="top:calc(48% - 120px);background:linear-gradient(135deg,#d64,#fb5)"></div>
    <div class="bk" style="left:calc(50% + 104px);top:calc(48% - 60px);background:linear-gradient(135deg,#2a8,#9e6)"></div>
    <div class="bk" style="left:calc(50% + 104px);top:calc(48% + 60px);background:linear-gradient(135deg,#c73,#fc8)"></div>
    <div class="bk" style="top:calc(48% + 120px);background:linear-gradient(135deg,#63c,#c9f)"></div>
    <div class="bk" style="left:calc(50% - 104px);top:calc(48% + 60px);background:linear-gradient(135deg,#27c,#8cf)"></div>
  </div>
  <!-- 押される本(左上=作者) -->
  <div class="bk target" style="left:calc(50% - 104px);top:calc(48% - 60px);--tx:104px;--ty:60px;background:linear-gradient(135deg,#3b7be8,#9ad1f5)"></div>
  <div class="bk center" style="background:linear-gradient(135deg,#e85d3b,#f6d34a)"></div>
  <div class="c-hand" style="left:calc(50% - 119px);top:calc(48% - 75px)"></div>
  <div class="ring2">
    <div class="thr" style="width:120px;transform:rotate(-60deg);background:var(--c-author)"></div>
    <div class="thr" style="width:120px;transform:rotate(0deg);background:var(--c-mag)"></div>
    <div class="thr" style="width:120px;transform:rotate(60deg);background:var(--c-year)"></div>
    <div class="thr" style="width:120px;transform:rotate(120deg);background:var(--c-theme)"></div>
    <div class="thr" style="width:120px;transform:rotate(180deg);background:var(--c-genre)"></div>
    <div class="bk" style="left:calc(50% + 60px);top:calc(48% - 104px);background:linear-gradient(135deg,#a33,#f77)"></div>
    <div class="bk" style="left:calc(50% + 120px);background:linear-gradient(135deg,#2a8,#9e6)"></div>
    <div class="bk" style="left:calc(50% + 60px);top:calc(48% + 104px);background:linear-gradient(135deg,#63c,#c9f)"></div>
    <div class="bk" style="left:calc(50% - 60px);top:calc(48% + 104px);background:linear-gradient(135deg,#27c,#8cf)"></div>
    <div class="bk" style="left:calc(50% - 120px);background:linear-gradient(135deg,#c73,#fc8)"></div>
  </div>
  <div class="c-sheet"><b>○○○○(同じ作者の別の本)</b><br><span style="color:#aaa">紹介文がここに出ます</span><br><span class="go">〈作者〉の糸で進む →</span></div>
  <div class="c-step"><span class="s1">① 広げた本を1回押す</span><span class="s3">③ 真ん中に来て、新しい糸が広がる</span></div>
</div>
<p class="cap">進むたびに、左上の旅路に本が1冊ずつ増えていきます。</p>
</div>

<div class="step">
<h3><span class="num">6</span>ジャンル・要素は「重ねて」広げる</h3>
<p><b>ジャンル</b>(橙)と<b>要素</b>(青)の入口だけは、押してもすぐには広がりません。押すと「選んだ」状態で光り、ほかのジャンル・要素を押すと条件が<b>重なり</b>ます。数字は重ねた時に残る本の数(→31)。真ん中の下に出るボタンで広げます。</p>
<div class="shot"><img src="/guide/c2.jpg" width="640" height="744" loading="lazy" decoding="async" alt="ジャンルと要素を重ねたところ"><div class="mark" style="left:63.1%;top:10.5%;width:12.6%;height:15.2%"><b>1</b></div><div class="mark" style="left:12.3%;top:51.8%;width:12.6%;height:15.2%"><b>2</b></div><div class="mark" style="left:38.4%;top:62.8%;width:23.2%;height:8.6%"><b>3</b></div></div>
<p class="cap">のだめカンタービレから ① ジャンル「音楽」 ② 要素「成長物語」を押して重ねたところ。③「成長物語 × 音楽 31冊を広げる」で、音楽ものの成長物語だけが広がる。選んだ入口をもう一度押しても広がります。</p>
<div class="tip">重ねるほど「この本のどこが好きか」に近い本になります。0冊になる入口は押せなくなります。</div>
</div>

<div class="step">
<h3><span class="num">7</span>広げた後に「さらに絞る」</h3>
<p>広げた本が多すぎる時は、上の「⚗ さらに絞る」。いま広げている本を、真ん中の本が持っているジャンル・要素でもう一段しぼれます。</p>
<div class="shot"><img src="/guide/c5.jpg" width="640" height="306" loading="lazy" decoding="async" alt="さらに絞る"><div class="mark" style="left:2.3%;top:28.0%;width:16.0%;height:11.4%"><b>1</b></div><div class="mark" style="left:2.3%;top:50.8%;width:21.1%;height:11.4%"><b>2</b></div></div>
<p class="cap">31冊から ① ジャンル「恋愛」なら18冊 ② 要素「ミュージカル」なら4冊。札を選んで下のボタンで絞る(何も選ばずに押すと絞りを外す)</p>
</div>

<div class="step">
<h3><span class="num">8</span>「ほか ▸」と、ジャンルの組み替え</h3>
<p>輪に入りきらなかった要素・ジャンルは、下の「要素 ほか・ジャンル ほか ▸」にまとまっています。ここでも押して重ねられます。</p>
<div class="shot"><img src="/guide/c6.jpg" width="640" height="367" loading="lazy" decoding="async" alt="ほかの糸の一覧"><div class="mark" style="left:2.3%;top:13.8%;width:95.3%;height:82.2%"><b>1</b></div><div class="mark" style="left:71.8%;top:56.9%;width:25.9%;height:6.7%"><b>2</b></div></div>
<p class="cap">① 輪に出ていない要素とジャンル(押して重ねる) ② ジャンルを組み替える</p>
<p>「⇄ ジャンルを組み替える」は、真ん中の本のジャンルを<b>外したり足したり</b>して似た本を探す道具です。たとえば「ギャグ」を外せば、笑いより音楽ドラマ寄りののだめに似た本が出ます。</p>
<div class="shot"><img src="/guide/c7.jpg" width="640" height="432" loading="lazy" decoding="async" alt="ジャンルを組み替える"><div class="mark" style="left:2.3%;top:19.8%;width:95.3%;height:8.0%"><b>1</b></div><div class="mark" style="left:2.3%;top:35.9%;width:95.3%;height:47.1%"><b>2</b></div></div>
<p class="cap">① この本のジャンル(押すと外す) ② 足してみるジャンル(＋を押すと足す)</p>
</div>

<div class="step">
<h3><span class="num">9</span>戻る・送る</h3>
<p>左上の<b>旅路</b>の小さな本を押すと、その本まで戻れます。何もないところを押すと、ひとつ前の状態に戻ります。気に入った本は下の「詳細」で作品ページへ。</p>
<div class="tip">右上の「共有」で、<b>たどってきた旅路ごと</b>友だちに送れます。受け取った人の画面にも同じ旅路がならび、最後の本から続きを旅できます。</div>
</div>

<dl class="faq">
<dt>周りの本が毎回ちがうのは?</dt><dd>近い本ほど出やすい「くじ」で選んでいるからです。人気順ではありません。開き直すと別の出会いがあります。</dd>
<dt>「ジャンル」と「似たジャンル」のちがいは?</dt><dd>ジャンル(橙)は「音楽」など1つのジャンルを持つ本。似たジャンル(黄)は、ジャンルの組み合わせ全体がこの本と近い本です(近さで「よく似た」「似た」「やや似た」と表示が変わります)。</dd>
<dt>「要素」と「似た要素」のちがいは?</dt><dd>要素(青)は「成長物語」など1つの特徴を持つ本。似た要素(水色)は、要素をいくつも共有している本です。</dd>
<dt>糸を1色だけにしたい</dt><dd>いちばん上の色の札(作者・同じ雑誌…)を押すと、その糸を消したり戻したりできます。</dd>
</dl>
<a class="cta cp" href="/compass">羅針盤をひらく ›</a>
</section>

<p class="foot"><a href="/about">MANGAL について(サイトの目的・データの出どころ) ›</a></p>
`;
