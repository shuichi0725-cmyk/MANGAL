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
