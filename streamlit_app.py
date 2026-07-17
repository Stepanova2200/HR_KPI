import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_title = "Дашборд укомплектованности"
st.set_page_config(page_title="Дашборд укомплектованности", layout="wide")
st.title("📊 Мониторинг укомплектованности штата")

# --- 1. ЗАГРУЗКА ДАННЫХ: ТОЛЬКО ФАЙЛ ОТ ПОЛЬЗОВАТЕЛЯ ---
@st.cache_data
def load_data(uploaded_file):
    """Читает CSV, нормализует названия колонок и считает метрики."""
    try:
        df = pd.read_csv(uploaded_file, parse_dates=["Дата"], encoding='utf-8')
    except UnicodeDecodeError:
        uploaded_file.seek(0)
        df = pd.read_csv(uploaded_file, parse_dates=["Дата"], encoding='cp1251')
        
    # Нормализация названий колонок для стабильности
    mapping = {col.strip().lower(): col for col in df.columns}
    
    required_raw = ["дата", "цех/участок", "плановая численность", "фактическая численность"]
    missing = [req for req in required_raw if req not in mapping]
    
    if missing:
        st.error(f"❌ В загруженном файле отсутствуют обязательные колонки: {missing}")
        return None

    rename_dict = {
        mapping["дата"]: "Дата",
        mapping["цех/участок"]: "Цех",
        mapping["плановая численность"]: "План",
        mapping["фактическая численность"]: "Факт"
    }
    df.rename(columns=rename_dict, inplace=True)
    
    # Проверка на числовой тип (на случай строк в CSV)
    for col in ["План", "Факт"]:
        df[col] = pd.to_numeric(df[col], errors='coerce')
        
    # Расчет метрик с защитой от деления на ноль
    df["Недокомплект"] = df["План"] - df["Факт"]
    plan_safe = df["План"].replace(0, pd.NA)
    df["Укомплектованность, %"] = (df["Факт"] * 100.0 / plan_safe).round(1)
    
    return df


uploaded_file = st.file_uploader(
    "📁 Загрузите ваш CSV-файл", 
    type=['csv'], 
    help="Файл должен содержать колонки: Дата, Цех/участок, Плановая численность, Фактическая численность"
)

if not uploaded_file:
    st.info("ℹ️ Для начала работы загрузите CSV-файл с данными об укомплектованности.")
    st.stop()

df = load_data(uploaded_file)

if df is None or df.empty:
    st.warning("Данные пусты или некорректны после загрузки.")
    st.stop()

# --- 2. ФИЛЬТРЫ В САЙДБАРЕ ---
st.sidebar.header("🔍 Фильтры")
min_date = df["Дата"].min().date()
max_date = df["Дата"].max().date()

selected_date = st.sidebar.date_input(
    "Выберите дату для детального анализа",
    value=max_date,
    min_value=min_date,
    max_value=max_date
)

unique_depts = sorted(df["Цех"].unique())
selected_depts = st.sidebar.multiselect(
    "Выберите цехи",
    options=unique_depts,
    default=unique_depts
)

if not selected_depts:
    st.warning("Не выбран ни один цех. Выберите хотя бы один цех в левом меню.")
    st.stop()

mask = (df["Дата"].dt.date == selected_date) & (df["Цех"].isin(selected_depts))
filtered_df = df[mask]

daily_mask = df["Цех"].isin(selected_depts)
trend_df = df[daily_mask]

# --- 3. KPI ПО ВЫБРАННОЙ ДАТЕ И ЦЕХАМ ---
overall_staffing = filtered_df["Укомплектованность, %"].mean()
total_understaffing = filtered_df["Недокомплект"].sum()

col_kpi1, col_kpi2, _ = st.columns([1, 1, 3])
with col_kpi1:
    st.metric(
        label="Средняя укомплектованность",
        value=f"{overall_staffing:.1f}%",
        delta=f"{'▲' if overall_staffing > 95 else '▼'} {overall_staffing - 95:.1f}%"
    )
with col_kpi2:
    st.metric(
        label="Суммарный недокомплект",
        value=f"{int(total_understaffing)} чел."
    )
st.caption(f"Целевой уровень: 95% | Данные показаны только для выбранных фильтров")

st.markdown("---")

# --- 4. СТОЛБЧАТАЯ ДИАГРАММА ---
st.subheader(f"Укомплектованность по выбранным цехам на {selected_date}")

dept_stats = filtered_df.groupby("Цех").agg(
    avg_understaffing=("Недокомплект", "mean"),
    avg_staffing=("Укомплектованность, %", "mean")
).reset_index()

fig_bar = px.bar(
    dept_stats,
    x="Цех",
    y="avg_staffing",
    color="avg_staffing",
    color_continuous_scale="Blues",
    text_auto=".1f",
    labels={"Цех": "Цех", "avg_staffing": "Укомплектованность (%)"},
)
fig_bar.update_layout(showlegend=False, height=400, yaxis_range=[70, 105])
st.plotly_chart(fig_bar, width='stretch')

st.subheader("Топ-5 цехов с наибольшим недокомплектом (на дату)")
top_5_understaffed = dept_stats.sort_values("avg_understaffing", ascending=False).head(5)
st.dataframe(
    top_5_understaffed[["Цех", "avg_understaffing"]].rename(columns={"avg_understaffing": "Недокомплект, чел."}), 
    width='stretch'
)

st.markdown("---")

# --- 5. ЛИНЕЙНЫЙ ГРАФИК: ОБЩИЙ ТРЕНД ---
st.subheader("Динамика укомплектованности (общий тренд по выбранным цехам)")

daily_trend = trend_df.groupby("Дата")["Укомплектованность, %"].mean().reset_index()

fig_line = px.line(
    daily_trend,
    x="Дата",
    y="Укомплектованность, %",
    markers=True,
    labels={"Дата": "Дата", "Укомплектованность, %": "Укомплектованность (%)"},
    title="Общий тренд укомплектованности"
)
fig_line.add_hline(y=95, line_dash="dash", line_color="green", annotation_text="Цель: 95%")
fig_line.update_layout(height=400, yaxis_range=[60, 105])
st.plotly_chart(fig_line, width='stretch')

# --- 6. ДЕТАЛИЗАЦИЯ ---
with st.expander("📋 Детализация по дням и цехам"):
    st.dataframe(filtered_df.style.format({"Укомплектованность, %": "{:.1f}%"}), width='stretch')
