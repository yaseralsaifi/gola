import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO

from .utils import to_numeric, clean_number

def render_delta_tab(df, cols, config):
    st.subheader("🔁 أعمدة الفارق المبسطة (بالمعادلة الجديدة)")

    col_avgq = cols["avgq"]
    col_high = cols["high_avgq"]
    decimals_pct = config["delta"]["decimals_pct"]

    if not col_high:
        st.info("للحساب هنا يلزم اختيار عمود 'أعلى متوسط السداد الربعي' من الشريط الجانبي.")
        return

    if col_avgq not in df.columns or col_high not in df.columns:
        st.info("للحساب هنا يلزم وجود الأعمدة المختارة في الملف.")
        return

    avg_series  = to_numeric(df[col_avgq].map(clean_number))
    high_series = to_numeric(df[col_high].map(clean_number))

    df_delta = df.copy()

    # (avg - high) / avg
    df_delta["فارق التغير (نسبي)"] = np.where(
        (avg_series.notna()) & (avg_series != 0),
        (avg_series - high_series) / avg_series,
        np.nan
    )

    # حجم الفارق كنسبة مئوية
    df_delta["فئة نسبة الفارق %"] = (
        df_delta["فارق التغير (نسبي)"].abs() * 100
    ).round(decimals_pct)

    # اتجاه مبسط
    def simple_dir(x):
        if pd.isna(x):
            return "—"
        if x < 0:
            return "ارتفاع"
        if x > 0:
            return "انخفاض"
        return "مستقر"

    df_delta["اتجاه مبسط"] = df_delta["فارق التغير (نسبي)"].apply(simple_dir)

    # شدة الفارق
    def magnitude_band(pct):
        if pd.isna(pct):
            return "—"
        if pct < 10:
            return "خفيف"
        elif pct < 30:
            return "متوسط"
        else:
            return "قوي"

    df_delta["شدة الفارق"] = df_delta["فئة نسبة الفارق %"].apply(magnitude_band)

    st.dataframe(
        df_delta[
            [
                col_avgq,
                col_high,
                "فارق التغير (نسبي)",
                "فئة نسبة الفارق %",
                "اتجاه مبسط",
                "شدة الفارق",
            ]
        ],
        use_container_width=True,
    )

    out_delta = BytesIO()
    df_delta.to_excel(out_delta, index=False)
    out_delta.seek(0)
    st.download_button(
        "⬇️ تحميل ملف الفارق (Excel)",
        out_delta,
        file_name="نتائج_أعمدة_الفارق.xlsx",
    )
