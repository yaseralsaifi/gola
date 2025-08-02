# 🧠 مشروع تحليل السمات مقابل الهدف - نسخة متوافقة مع Render وملفات Excel مرنة
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score

st.set_page_config(page_title="تحليل السمات والهدف", layout="wide")
st.title("🧪 تحليل العلاقة بين السمات والهدف")

uploaded_file = st.file_uploader("📥 ارفع ملف Excel يحتوي على البيانات", type=["xlsx"])

if uploaded_file:
    df = pd.read_excel(uploaded_file)
    st.success("✅ تم تحميل البيانات بنجاح")
    st.subheader("🔍 نظرة عامة على البيانات")
    st.write(df.head())

    # عرض الأعمدة الموجودة فعليًا
    st.write("🧾 الأعمدة المتوفرة:", df.columns.tolist())

    # محاولة العثور على العمود "سدد" تلقائيًا
    target_column = None
    for col in df.columns:
        if str(col).strip() == "سدد":
            target_column = col
            break

    if target_column:
        X = df.drop(target_column, axis=1)
        y = df[target_column]

        st.subheader("📊 تحليل سمة مقابل الهدف")
        selected_feature = st.selectbox("اختر سمة لعرض العلاقة", X.columns)
        fig, ax = plt.subplots()
        sns.boxplot(x=y, y=X[selected_feature], ax=ax)
        ax.set_xlabel("سدد (0=لا، 1=نعم)")
        ax.set_ylabel(selected_feature)
        st.pyplot(fig)

        st.subheader("🤖 تدريب نموذج سريع")
        test_size = st.slider("نسبة بيانات الاختبار", 0.1, 0.5, 0.3)
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=test_size, random_state=42)

        model = RandomForestClassifier()
        model.fit(X_train, y_train)
        y_pred = model.predict(X_test)

        st.write("✅ دقة النموذج:", accuracy_score(y_test, y_pred))
        st.text("📋 تقرير التصنيف:")
        st.text(classification_report(y_test, y_pred))
    else:
        st.error("❌ العمود 'سدد' غير موجود في البيانات. تأكد من كتابته بدون مسافات أو رموز.")
else:
    st.warning("📂 الرجاء رفع ملف Excel للبدء")
