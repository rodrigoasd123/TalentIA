"""Vista del consumo de IA."""

from __future__ import annotations

import sys
from pathlib import Path
import sqlite3

import streamlit as st
import pandas as pd

APP_DIR = Path(__file__).resolve().parents[1]
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from talentia import design, session

st.set_page_config(page_title="Consumo de IA | TalentIA", page_icon="📈", layout="wide")
design.apply_theme()
session.require_login()

st.title("Consumo de IA")
st.markdown("Monitoriza el consumo de tokens y los costos estimados de los modelos de IA configurados.")

def load_usage_data():
    try:
        # Connect directly to sqlite db to fetch the data
        db_path = APP_DIR.parent / "talentia.db"
        if not db_path.exists():
            return pd.DataFrame()
            
        with sqlite3.connect(db_path) as conn:
            query = "SELECT * FROM ai_usage_logs ORDER BY created_at DESC"
            df = pd.read_sql(query, conn)
            return df
    except Exception as e:
        st.error(f"Error al cargar los datos: {e}")
        return pd.DataFrame()

df = load_usage_data()

if df.empty:
    st.info("No hay registros de uso de IA todavía.")
else:
    # Metricas clave
    total_requests = len(df)
    total_input = df['input_tokens'].sum()
    total_output = df['output_tokens'].sum()
    total_tokens = df['total_tokens'].sum()
    total_cost = df['estimated_cost_usd'].sum()
    
    most_used = df['model'].mode()[0] if not df['model'].empty else "N/A"

    col1, col2, col3 = st.columns(3)
    col1.metric("Total de Requests", f"{total_requests:,}")
    col2.metric("Tokens Totales", f"{total_tokens:,}")
    col3.metric("Costo Estimado", f"${total_cost:.4f}")

    col4, col5, col6 = st.columns(3)
    col4.metric("Tokens de Entrada", f"{total_input:,}")
    col5.metric("Tokens de Salida", f"{total_output:,}")
    col6.metric("Modelo más Utilizado", most_used)

    st.divider()

    col_chart1, col_chart2 = st.columns(2)
    
    with col_chart1:
        st.subheader("Consumo por Modelo")
        if not df.empty:
            cost_by_model = df.groupby('model')['estimated_cost_usd'].sum().reset_index()
            st.bar_chart(cost_by_model.set_index('model'))
            
    with col_chart2:
        st.subheader("Consumo por Funcionalidad")
        if not df.empty:
            cost_by_feature = df.groupby('feature')['estimated_cost_usd'].sum().reset_index()
            st.bar_chart(cost_by_feature.set_index('feature'))

    st.subheader("Últimas llamadas")
    
    # Display table safely
    if not df.empty:
        display_df = df[['created_at', 'model', 'feature', 'input_tokens', 'output_tokens', 'total_tokens', 'estimated_cost_usd', 'success']].copy()
        st.dataframe(display_df, use_container_width=True)

