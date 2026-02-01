import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO

from .utils import to_numeric, clean_number


def render_rep_turnover_tab(df: pd.DataFrame, cols: dict, config: dict):
    st.subheader("👥 دوران المديونية للمندوبين (مرة واحدة)")

    # أسماء الأعمدة كما في ملفك (حسب الصور)
    REP_ID_COL   = "رقم المندوب"
    REP_NAME_COL = "اسم المندوب"
    DEBT_COL     = "المديونية"
    AVGQ_COL     = "متوسط السداد الربعي"
    MONTHLY_COL  = "السداد الشهري للعميل"

    required = [REP_ID_COL, REP_NAME_COL, DEBT_COL, AVGQ_COL, MONTHLY_COL]
    missing = [c for c in required if c not in df.columns]
    if missing:
        st.error(f"الأعمدة التالية غير موجودة في الملف: {missing}")
        return

    # تنظيف وتحويل الأرقام
    work = df.copy()
    work[DEBT_COL] = to_numeric(work[DEBT_COL].map(clean_number)).fillna(0.0)
    work[AVGQ_COL] = to_numeric(work[AVGQ_COL].map(clean_number)).fillna(0.0)
    work[MONTHLY_COL] = to_numeric(work[MONTHLY_COL].map(clean_number)).fillna(0.0)

    # تجميع كل المندوبين
    grp = work.groupby([REP_ID_COL, REP_NAME_COL], dropna=False).agg(
        عدد_العملاء=(DEBT_COL, "size"),
        اجمالي_المديونية=(DEBT_COL, "sum"),
        اجمالي_متوسط_السداد_الربعي=(AVGQ_COL, "sum"),
        اجمالي_السداد_الشهري=(MONTHLY_COL, "sum"),
    ).reset_index()

    # حساب الدوران (مع حماية القسمة على صفر)
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

    # ترتيب (يمكن تغييره بسهولة)
    grp = grp.sort_values("الدوران الربعي للمندوب", ascending=False)

    # عرض
    st.markdown("### 📊 جدول دوران المديونية للمندوبين")
    st.dataframe(grp, use_container_width=True)

    # تصدير Excel
    buf = BytesIO()
    grp.to_excel(buf, index=False)
    buf.seek(0)

    st.download_button(
        "⬇️ تحميل جدول دوران المديونية للمندوبين (Excel)",
        buf,
        file_name="all_reps_debt_turnover.xlsx"
    )
