import streamlit as st
import numpy as np
from io import BytesIO

from .utils import to_numeric, clean_number
from .scoring import (
    score_purchase_power,
    score_debt_age,
    score_risk,
    final_classification,
)

def render_main_tab(df, df_original, cols, config):
    st.subheader("🔎 التصنيف والتحليل الأساسي")

    col_debt = cols["debt"]
    col_avgq = cols["avgq"]
    col_age  = cols["age"]

    missing = [c for c in [col_debt, col_avgq] if c not in df.columns]
    if missing:
        st.error(f"يجب توافر أعمدة: {missing}")
        st.stop()

    # تنظيف القيم المختارة ثم تحويلها لرقمية
    for c in [col_debt, col_avgq] + ([col_age] if col_age else []):
        df[c] = to_numeric(df[c].map(clean_number))

    # نسبة من القائد (متوسط السداد)
    max_avg = df[col_avgq].max()
    df["نسبة من القائد (متوسط)"] = np.where(
        max_avg > 0,
        (df[col_avgq] / max_avg * 100).round(2),
        np.nan
    )

    # نقاط القوة الشرائية / الالتزام / المخاطرة
    df["نقاط القوة الشرائية"] = df["نسبة من القائد (متوسط)"].apply(
        lambda x: score_purchase_power(x, config["pp"])
    )
    df["نقاط الالتزام"] = (
        df[col_age].apply(lambda x: score_debt_age(x, config["age"]))
        if col_age and col_age in df.columns else 0
    )

    def safe_ratio(a, b):
        try:
            a = float(a) if not np.isnan(a) else 0.0
            b = float(b) if not np.isnan(b) else 0.0
            return a / b if b != 0 else np.nan
        except Exception:
            return np.nan

    df["مؤشر المخاطرة (مديونية/متوسط)"] = df.apply(
        lambda r: safe_ratio(r[col_debt], r[col_avgq]),
        axis=1
    ).round(3)

    df["نقاط المخاطرة"] = df.apply(
        lambda r: score_risk(r[col_debt], r[col_avgq], config["risk"]),
        axis=1
    )

    # التصنيف النهائي
    df["إجمالي النقاط"] = df[
        ["نقاط القوة الشرائية", "نقاط الالتزام", "نقاط المخاطرة"]
    ].sum(axis=1)

    df["التصنيف النهائي"] = df["إجمالي النقاط"].apply(
        lambda s: final_classification(s, config["final"])
    )

    # ===== نسب المندوب =====
    rep_col_candidates = ["اسم المندوب", "المندوب", "مندوب", "اسم مندوب"]
    rep_col = next((c for c in rep_col_candidates if c in df.columns), None)

    if rep_col is not None and col_debt in df.columns:
        cnt = df.groupby([rep_col, "التصنيف النهائي"])["إجمالي النقاط"].size().rename("عدد")
        cnt_by_class = cnt.groupby(level=1).transform("sum")
        share_count = (cnt / cnt_by_class * 100).round(2)

        debt_grp = df.groupby([rep_col, "التصنيف النهائي"])[col_debt].sum().rename("مديونية")
        debt_by_class = debt_grp.groupby(level=1).transform("sum")
        share_debt = (debt_grp / debt_by_class * 100).round(2)

        share_count_map = share_count.to_dict()
        share_debt_map = share_debt.to_dict()

        df["نسبة المندوب من فئة العميل (بالعدد %)"] = df.apply(
            lambda r: share_count_map.get((r[rep_col], r["التصنيف النهائي"]), np.nan),
            axis=1
        )
        df["نسبة المندوب من فئة العميل (بالمديونية %)"] = df.apply(
            lambda r: share_debt_map.get((r[rep_col], r["التصنيف النهائي"]), np.nan),
            axis=1
        )

        df["إجمالي مديونية المندوب"] = df.groupby(rep_col)[col_debt].transform("sum")
        df["مديونية المندوب ضمن هذه الفئة"] = df.groupby(
            [rep_col, "التصنيف النهائي"]
        )[col_debt].transform("sum")

        df["نسبة الفئة داخل مديونية المندوب (%)"] = np.where(
            df["إجمالي مديونية المندوب"] > 0,
            (df["مديونية المندوب ضمن هذه الفئة"] / df["إجمالي مديونية المندوب"]) * 100,
            np.nan
        ).round(2)
    else:
        df["نسبة المندوب من فئة العميل (بالعدد %)"] = np.nan
        df["نسبة المندوب من فئة العميل (بالمديونية %)"] = np.nan
        df["نسبة الفئة داخل مديونية المندوب (%)"] = np.nan

    # نسبة كل تصنيف من إجمالي المديونية
    total_debt = df[col_debt].sum(skipna=True)
    if total_debt and total_debt != 0:
        class_debt = df.groupby("التصنيف النهائي")[col_debt].sum()
        share_map = (class_debt / total_debt * 100).to_dict()
        df["نسبة التصنيف من إجمالي المديونية (%)"] = (
            df["التصنيف النهائي"].map(share_map).round(2)
        )
    else:
        df["نسبة التصنيف من إجمالي المديونية (%)"] = 0.0

    # ===== خطة المعالجة الذكية =====
    st.markdown("### 🧠 خطة المعالجة الذكية")

    df["مبلغ الانحراف (للـ3 أشهر)"] = np.maximum(
        0.0,
        df[col_debt].fillna(0).astype(float)
        - 3.0 * df[col_avgq].fillna(0).astype(float)
    ).round(2)

    df["قسط الانحراف الشهري"] = (df["مبلغ الانحراف (للـ3 أشهر)"] / 3.0).round(2)
    df["فقد_نقاط_التزام/مخاطرة؟"] = (
        (df["نقاط الالتزام"] < 5) | (df["نقاط المخاطرة"] < 5)
    )

    def base_targets(class_name, pwr_bucket, avg_q, debt):
        avg_q = float(avg_q or 0)
        debt = float(debt or 0)
        pwr_bucket = float(pwr_bucket or 0)

        if pwr_bucket < 5:
            return debt, avg_q

        if class_name == "ملتزم":
            pay, sales = avg_q, avg_q
        elif class_name == "جيد":
            pay, sales = avg_q * 1.10, avg_q
        elif str(class_name).startswith("جدوله مديونية وتثبيت"):
            pay, sales = avg_q * 1.15, avg_q
        elif str(class_name).startswith("جدوله مديونية وتخفيف"):
            pay, sales = avg_q * 1.15, avg_q * 0.90
        elif class_name == "قبل النهاية":
            pay, sales = avg_q * 1.15, avg_q * 0.85
        else:
            pay, sales = 0.0, 0.0

        return round(pay, 2), round(sales, 2)

    pay_base_list, sales_base_list, pay_final_list = [], [], []

    for _, r in df.iterrows():
        pay_b, sales_b = base_targets(
            r["التصنيف النهائي"],
            r["نقاط القوة الشرائية"],
            r[col_avgq],
            r[col_debt],
        )
        pay_base_list.append(pay_b)
        sales_base_list.append(sales_b)

        pay_final_list.append(
            round(
                pay_b
                + (
                    float(r["قسط الانحراف الشهري"])
                    if bool(r["فقد_نقاط_التزام/مخاطرة؟"])
                    else 0.0
                ),
                2,
            )
        )

    df["هدف السداد الشهري (أساس)"] = pay_base_list
    df["هدف المبيعات الشهري"] = sales_base_list
    df["هدف السداد الشهري (بعد المعالجة)"] = pay_final_list

    df["ملاحظة خطة السداد"] = np.where(
        df["فقد_نقاط_التزام/مخاطرة؟"],
        "تفعيل الخطة: تمت إضافة قسط الانحراف الشهري",
        "لا توجد خسارة نقاط في الالتزام/المخاطرة — الاكتفاء بالهدف الأساسي",
    )

    st.success("✅ تم إعداد التصنيف والخطة بنجاح.")
    st.dataframe(df, use_container_width=True)

    out_main = BytesIO()
    df.to_excel(out_main, index=False)
    out_main.seek(0)
    st.download_button(
        "⬇️ تحميل الملف الناتج (Excel)",
        out_main,
        file_name="نتائج_التصنيف_v5_6_5.xlsx",
    )
