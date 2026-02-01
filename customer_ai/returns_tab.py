import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO

from .utils import clean_number


def render_returns_tab(df, cols, config):
    st.subheader("📊 تصنيفات المرتجع — مستقل")

    m_ok = config["returns"]["m_ok"]
    m_watch = config["returns"]["m_watch"]
    m_high = config["returns"]["m_high"]

    col_avgq = cols["avgq"]

    col_avgpay = st.text_input(
        "اسم عمود (متوسط السداد الربعي)",
        value=col_avgq or "متوسط السداد الربعي",
    )
    col_base = st.text_input(
        "اسم عمود (نسبة المرتجع من المباع)",
        value="نسبة المرتجع من المباع",
    )
    col_new = st.text_input(
        "اسم عمود (نسبة نوع جديد من مرتجعات العميل)",
        value="نسبة نوع جديد من مرتجعات العميل",
    )
    col_comp = st.text_input(
        "اسم عمود (نسبة نوع تعويض من مرتجعات العميل)",
        value="نسبة نوع تعويض من مرتجعات العميل",
    )

    def score_purchase_power_for_returns(p):
        if pd.isna(p):
            return np.nan
        if p >= 50:
            return 10
        elif p >= 25:
            return 8
        elif p >= 15:
            return 7
        elif p >= 10:
            return 6
        elif p >= 5:
            return 5
        elif p >= 4:
            return 4
        elif p >= 3:
            return 3
        elif p >= 2:
            return 2
        elif p >= 1:
            return 1
        else:
            return 0

    def process_return_column(df_in: pd.DataFrame, col_name: str, label: str):
        if col_name not in df_in.columns:
            st.warning(f"⚠️ لم يتم العثور على العمود: {col_name}")
            return None
        if col_avgpay not in df_in.columns:
            st.warning(f"لا يمكن احتساب مجموعة المرجع لعدم توفر '{col_avgpay}'.")
            return None

        avg_series = pd.to_numeric(
            df_in[col_avgpay].map(clean_number), errors="coerce"
        )
        vals = pd.to_numeric(
            df_in[col_name].map(clean_number), errors="coerce"
        )

        max_avg = avg_series.max(skipna=True)
        pct = np.where(max_avg > 0, (avg_series / max_avg * 100), np.nan)
        pp = pd.Series(pct, index=df_in.index).apply(
            score_purchase_power_for_returns
        )
        mask_ref = pp.between(5, 10, inclusive="both")

        ref_avg = vals[mask_ref].mean(skipna=True)

        out = pd.DataFrame(index=df_in.index)
        out[col_name] = vals
        out[f"معيار المرتجع ({label} 10–5)"] = ref_avg

        if pd.isna(ref_avg) or ref_avg == 0:
            out[f"مضاعف المرتجع ({label}) مقابل المعيار"] = np.nan
            out[f"تصنيف المرتجع ({label})"] = "بيانات غير كافية"
            return out

        ratio = vals / ref_avg
        out[f"مضاعف المرتجع ({label}) مقابل المعيار"] = ratio

        def label_ratio(x):
            if pd.isna(x):
                return "بيانات غير كافية"
            if x <= m_ok:
                return "ضمن المعيار"
            elif x <= m_watch:
                return "يحتاج متابعة"
            elif x <= m_high:
                return "مرتفع"
            else:
                return "مرتفع جدًا"

        out[f"تصنيف المرتجع ({label})"] = ratio.apply(label_ratio)
        return out

    sections = []
    for cname, lbl in [
        (col_base, "المرتجع من المباع"),
        (col_new, "النوع الجديد"),
        (col_comp, "نوع تعويض"),
    ]:
        res = process_return_column(df, cname, lbl)
        if res is not None:
            st.subheader(f"🔎 {lbl}")
            st.dataframe(res, use_container_width=True)
            sections.append(res)

    if sections:
        out_ret = BytesIO()
        out_df = pd.concat(sections, axis=1)
        out_df.to_excel(out_ret, index=False)
        out_ret.seek(0)
        st.download_button(
            "⬇️ تحميل الملف (تصنيفات المرتجع)",
            out_ret,
            file_name="نتائج_تصنيفات_المرتجع.xlsx",
        )
