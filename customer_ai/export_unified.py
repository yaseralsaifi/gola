import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO

from .utils import to_numeric, clean_number


def compute_delta_table(base_df: pd.DataFrame, cols: dict, config: dict) -> pd.DataFrame:
    col_avgq = cols["avgq"]
    col_high = cols["high_avgq"]

    if not col_high:
        return pd.DataFrame()
    if col_avgq not in base_df.columns or col_high not in base_df.columns:
        return pd.DataFrame()

    avg_series = to_numeric(base_df[col_avgq].map(clean_number))
    high_series = to_numeric(base_df[col_high].map(clean_number))
    decimals_pct = int(config["delta"]["decimals_pct"])

    d = pd.DataFrame(index=base_df.index)

    # (avg - high) / avg
    delta_ratio = np.where(
        (avg_series.notna()) & (avg_series != 0),
        (avg_series - high_series) / avg_series,
        np.nan
    )

    d["[فارق] فارق التغير (نسبي)"] = delta_ratio
    d["[فارق] فئة نسبة الفارق %"] = (pd.Series(delta_ratio, index=base_df.index).abs() * 100.0).round(decimals_pct)

    # ✅ اتجاه مبسط (حسب طلبك: >0 ارتفاع، <0 انخفاض)
    def _dir(x):
        if pd.isna(x):
            return "—"
        if x > 0:
            return "ارتفاع"
        if x < 0:
            return "انخفاض"
        return "مستقر"

    d["[فارق] اتجاه مبسط"] = pd.Series(delta_ratio, index=base_df.index).apply(_dir)

    def _mag(pct):
        if pd.isna(pct):
            return "—"
        if pct < 10:
            return "خفيف"
        elif pct < 30:
            return "متوسط"
        else:
            return "قوي"

    d["[فارق] شدة الفارق"] = d["[فارق] فئة نسبة الفارق %"].apply(_mag)

    return d


def compute_returns_table(base_df: pd.DataFrame, cols: dict, config: dict) -> pd.DataFrame:
    # نفس منطقك في التصدير الموحد (Hardcoded) كما كان
    col_avgpay = cols["avgq"]
    col_base = "نسبة المرتجع من المباع"
    col_new = "نسبة نوع جديد من مرتجعات العميل"
    col_comp = "نسبة نوع تعويض من مرتجعات العميل"

    m_ok = config["returns"]["m_ok"]
    m_watch = config["returns"]["m_watch"]
    m_high = config["returns"]["m_high"]

    def _score_pp(p):
        if pd.isna(p): return np.nan
        if p >= 50: return 10
        elif p >= 25: return 8
        elif p >= 15: return 7
        elif p >= 10: return 6
        elif p >= 5:  return 5
        elif p >= 4:  return 4
        elif p >= 3:  return 3
        elif p >= 2:  return 2
        elif p >= 1:  return 1
        else:        return 0

    def _classify(rate, ref):
        if pd.isna(rate) or pd.isna(ref) or ref == 0:
            return "بيانات غير كافية"
        ratio = rate / ref
        if ratio <= m_ok: return "ضمن المعيار"
        elif ratio <= m_watch: return "يحتاج متابعة"
        elif ratio <= m_high: return "مرتفع"
        else: return "مرتفع جدًا"

    if col_avgpay not in base_df.columns:
        return pd.DataFrame()

    avg_series = to_numeric(base_df[col_avgpay].map(clean_number))
    max_avg = avg_series.max()
    pct_avg = np.where(max_avg > 0, (avg_series / max_avg * 100).round(2), np.nan)
    pp = pd.Series(pct_avg).apply(_score_pp)

    def _one(col_name: str, label: str) -> pd.DataFrame:
        if col_name not in base_df.columns:
            return pd.DataFrame()

        tmp = to_numeric(base_df[col_name].map(clean_number)).replace([np.inf, -np.inf], np.nan)
        ref_vals = tmp[pp.between(5, 10, inclusive="both")]
        ref_avg = ref_vals.mean()

        out = pd.DataFrame(index=base_df.index)
        out[f"[مرتجع] قيمة ({label})"] = tmp
        out[f"[مرتجع] معيار ({label} 10–5)"] = round(ref_avg, 4) if pd.notna(ref_avg) else np.nan

        if pd.isna(ref_avg) or ref_avg == 0:
            out[f"[مرتجع] مضاعف ({label}) مقابل المعيار"] = np.nan
            out[f"[مرتجع] تصنيف ({label})"] = "بيانات غير كافية"
            return out

        ratio = tmp / ref_avg
        out[f"[مرتجع] مضاعف ({label}) مقابل المعيار"] = ratio
        out[f"[مرتجع] تصنيف ({label})"] = tmp.apply(lambda x: _classify(x, ref_avg))
        return out

    parts = [
        _one(col_base, "المرتجع من المباع"),
        _one(col_new, "النوع الجديد"),
        _one(col_comp, "نوع تعويض"),
    ]
    parts = [p for p in parts if not p.empty]
    if not parts:
        return pd.DataFrame()
    return pd.concat(parts, axis=1)


def compute_rep_turnover_map(base_df: pd.DataFrame) -> pd.DataFrame:
    """
    يحسب دوران المديونية لكل مندوب (ربعي/شهري) ثم يرجع DataFrame
    يحتوي على مفاتيح الربط + العمودين المطلوب تكرارهما أمام كل عميل.
    """
    REP_NAME_COL = "اسم المندوب"
    REP_ID_COL = "رقم المندوب"
    DEBT_COL = "المديونية"
    AVGQ_COL = "متوسط السداد الربعي"
    MONTHLY_COL = "السداد الشهري للعميل"

    required = [REP_NAME_COL, REP_ID_COL, DEBT_COL, AVGQ_COL, MONTHLY_COL]
    if any(c not in base_df.columns for c in required):
        return pd.DataFrame()

    w = base_df.copy()
    w[DEBT_COL] = to_numeric(w[DEBT_COL].map(clean_number)).fillna(0.0)
    w[AVGQ_COL] = to_numeric(w[AVGQ_COL].map(clean_number)).fillna(0.0)
    w[MONTHLY_COL] = to_numeric(w[MONTHLY_COL].map(clean_number)).fillna(0.0)

    grp = w.groupby([REP_ID_COL, REP_NAME_COL], dropna=False).agg(
        اجمالي_المديونية=(DEBT_COL, "sum"),
        اجمالي_متوسط_السداد_الربعي=(AVGQ_COL, "sum"),
        اجمالي_السداد_الشهري=(MONTHLY_COL, "sum"),
    ).reset_index()

    grp["الدوران الربعي للمندوب"] = np.where(
        grp["اجمالي_المديونية"] != 0,
        grp["اجمالي_متوسط_السداد_الربعي"] / grp["اجمالي_المديونية"],
        np.nan
    )

    grp["الدوران الشهري للمندوب"] = np.where(
        grp["اجمالي_المديونية"] != 0,
        grp["اجمالي_السداد_الشهري"] / grp["اجمالي_المديونية"],
        np.nan
    )

    return grp[[REP_ID_COL, REP_NAME_COL, "الدوران الربعي للمندوب", "الدوران الشهري للمندوب"]]


def render_unified_export(df, df_original, cols, config):
    with st.expander("📦 تصدير ملف Excel موحّد (جميع الأعمدة والنتائج)", expanded=False):
        st.write(
            "ينشئ ملفًا واحدًا يجمع: أعمدة الملف الأصلي + نتائج التبويب الأساسي + أعمدة الفارق + تصنيفات المرتجع "
            "+ (تكرار) دوران المندوب أمام كل عميل."
        )

        # جداول مساعدة
        df_delta_all = compute_delta_table(df, cols, config)
        df_returns_all = compute_returns_table(df, cols, config)
        rep_turn = compute_rep_turnover_map(df_original)

        # Sheet unified (صفوف العملاء)
        unified = df_original.copy()

        # أعمدة النتائج الأساسية الموجودة في df وليست في df_original
        main_extra_cols = [c for c in df.columns if c not in df_original.columns]
        if main_extra_cols:
            unified = unified.join(df[main_extra_cols].add_prefix("[أساسي] "))

        # Join الفارق والمرتجع
        if df_delta_all is not None and not df_delta_all.empty:
            unified = unified.join(df_delta_all)
        if df_returns_all is not None and not df_returns_all.empty:
            unified = unified.join(df_returns_all)

        # ====== إضافة دوران المندوب لكل عميل (تكرار على الصفوف) ======
        if rep_turn is not None and not rep_turn.empty:
            if ("رقم المندوب" in unified.columns) and ("اسم المندوب" in unified.columns):
                unified = unified.merge(
                    rep_turn,
                    how="left",
                    on=["رقم المندوب", "اسم المندوب"]
                )
            else:
                unified["الدوران الربعي للمندوب"] = np.nan
                unified["الدوران الشهري للمندوب"] = np.nan
        else:
            unified["الدوران الربعي للمندوب"] = np.nan
            unified["الدوران الشهري للمندوب"] = np.nan

        # عرض
        st.dataframe(unified, use_container_width=True)

        # تصدير ملف واحد (Sheet واحدة Unified)
        buf = BytesIO()
        unified.to_excel(buf, index=False)
        buf.seek(0)

        st.download_button(
            "⬇️ تحميل الملف الموحّد (Excel)",
            buf,
            file_name="نتائج_موحّدة_كل_التبويبات.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )