# streamlit_app.py (Dashboard aprimorada)
import streamlit as st
import pandas as pd
from database_manager import DatabaseManager
import datetime

st.set_page_config(page_title="Dashboard Pagamentos", layout="wide", page_icon="📊")
st.title("📈 Dashboard de Pagamentos e Assinaturas")

db_manager = DatabaseManager()

# Métricas rápidas
col1, col2, col3, col4 = st.columns(4)

active_payments = db_manager.get_all_active_payments()
pack_price_map = {"pack_basico": 0.5, "pack_premium": 1.2, "pack_vip": 2.5}
total_revenue = sum(pack_price_map[p[2]] for p in active_payments)

with col1:
    st.metric(label="Pagamentos Ativos", value=len(active_payments))
with col2:
    st.metric(label="Receita Total (R$)", value=f"{total_revenue:.2f}")
with col3:
    st.metric(label="Usuários Únicos", value=len(set(p[1] for p in active_payments)))
with col4:
    # Encontrar o pack mais vendido
    pack_list = [p[2] for p in active_payments]
    if pack_list:  # Evita erro se a lista estiver vazia
        most_sold_pack = max(set(pack_list), key=pack_list.count)
    else:
        most_sold_pack = "N/A"
    st.metric(label="Pack Mais Vendido", value=most_sold_pack)

# Gráficos detalhados
st.subheader("📈 Evolução de Vendas por Pack")
df_active = pd.DataFrame(active_payments, columns=["ID Pagamento", "Usuário", "Pack", "Expira em"])
pack_counts = df_active.groupby("Pack")["ID Pagamento"].count()
st.bar_chart(pack_counts)

# Detalhes dos pagamentos ativos
st.subheader("💰 Pagamentos Recentes")
st.dataframe(df_active)

# Filtros interativos
st.sidebar.header("🎛️ Filtros")
pack_filter = st.sidebar.multiselect(
    "Filtrar por Pack",
    options=df_active["Pack"].unique(),
    default=df_active["Pack"].unique()
)
filtered_df = df_active[df_active["Pack"].isin(pack_filter)]

st.subheader("🔍 Pagamentos Filtrados")
st.dataframe(filtered_df)

# Converter coluna "Expira em" para datetime
df_active["Expira em"] = pd.to_datetime(df_active["Expira em"])
filtered_df["Expira em"] = pd.to_datetime(filtered_df["Expira em"])

# Alertas visuais
st.subheader("⏰ Pagamentos Próximos da Expiração")

# Usando um nome consistente
expiring_soon = df_active[
    df_active["Expira em"] <= (pd.Timestamp.now() + pd.Timedelta(days=3))
]

st.warning(f"{len(expiring_soon)} pagamentos estão próximos de expirar!")
st.dataframe(expiring_soon)
