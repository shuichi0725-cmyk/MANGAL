/** 全集コーナーの view 型 (= data/zenshuu-view.json。生成 = scripts/_gen-zenshuu-data.py) */
export type ZenshuuVol = {
  n?: number | null;
  t: string;
  i?: string | null;
  d?: string;
  c?: string | null;
  s?: string | null;
  /** 非漫画巻(エッセイ・対談等の特例掲載) */
  nm?: boolean;
};
export type ZenshuuWork = { name: string; vols: ZenshuuVol[] };
export type ZenshuuSet = { n: number; name: string; isbn: string; date: string; cover?: string | null; lineup?: string | null };
export type ZenshuuCollection = {
  key: string;
  name: string;
  /** 作家名(title「<作家> 作品一覧」用)。null = 1作品の全集等で作品一覧と名乗れない */
  author?: string | null;
  publisher: string;
  total: number;
  years: string;
  axis: "num" | "works" | "sets";
  linked: number;
  isbns?: number;
  complete: boolean;
  guinness?: boolean;
  covers: (string | null)[];
  works?: ZenshuuWork[];
  sets?: ZenshuuSet[];
};
export type ZenshuuView = { collections: ZenshuuCollection[] };
