import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import yfinance as yf

@st.cache_data
def load_data(file_path):
    """Loads the base ranking data from the user's CSV."""
    try:
        df = pd.read_csv(file_path)
        score_cols = ['総合スコア', 'VALUEスコア', 'QUALITYスコア', 'GROWTHスコア', 'MOMENTUMスコア']
        for col in score_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        return df
    except FileNotFoundError:
        st.error(f"Error: '{file_path}' not found. Please make sure it's in the same folder as the script.")
        return None

@st.cache_data
def get_detailed_data(tickers):
    """
    Fetches detailed data needed for visualization (like Sector and Market Cap).
    """
    detailed_data = []
    st.info(f"Fetching detailed data for top {len(tickers)} companies...")
    progress_bar = st.progress(0)
    for i, ticker_code in enumerate(tickers):
        try:
            stock = yf.Ticker(ticker_code)
            info = stock.info
            detailed_data.append({
                'ティッカー': ticker_code,
                '会社名': info.get('shortName'), # Get the most current name
                'セクター': info.get('sector'),
                '時価総額': info.get('marketCap')
            })
        except Exception:
            continue
        progress_bar.progress((i + 1) / len(tickers))
    progress_bar.empty()
    return pd.DataFrame(detailed_data)

@st.cache_data
def get_price_history(ticker):
    """Fetches 1-year price history."""
    try:
        stock = yf.Ticker(ticker)
        return stock.history(period="1y")
    except Exception:
        return None

# --- Main App ---
st.set_page_config(layout="wide")
st.title("🇯🇵 TSE Stock Analysis Dashboard")

base_df = load_data('TSE_all_comprehensive_ranking_2025-07.csv')

if base_df is not None:
    top_100_df = base_df.head(100)
    top_tickers = top_100_df['ティッカー'].tolist()
    
    detailed_df = get_detailed_data(top_tickers)

    # --- This is the corrected merge logic ---
    # 1. Drop the old '会社名' column from the base data before merging
    base_scores_df = top_100_df.drop(columns=['会社名'], errors='ignore')
    
    # 2. Merge the scores with the new detailed data.
    # This ensures a single, clean '会社名' column from the fresh data.
    df = pd.merge(base_scores_df, detailed_df, on='ティッカー', how='left')
    
    # 3. Clean up any rows that failed to fetch essential data
    df.dropna(subset=['セクター', '時価総額', '会社名'], inplace=True)
    # ----------------------------------------

    # --- Sidebar Filters ---
    st.sidebar.header("Stock Screener Filters")
    # ... (The rest of the script is the same) ...

    # Check if df is not empty after filtering
    if not df.empty:
        score_range = st.sidebar.slider(
            "Filter by Overall Score:",
            min_value=float(df['総合スコア'].min()),
            max_value=float(df['総合スコア'].max()),
            value=(float(df['総合スコア'].quantile(0.5)), float(df['総合スコア'].max()))
        )
        all_sectors = df['セクター'].unique().tolist()
        selected_sectors = st.sidebar.multiselect("Filter by Sector:", options=all_sectors, default=all_sectors)

        # Apply filters from the sidebar
        filtered_df = df[
            (df['総合スコア'] >= score_range[0]) &
            (df['総合スコア'] <= score_range[1]) &
            (df['セクター'].isin(selected_sectors))
        ].copy() # Use .copy() to avoid SettingWithCopyWarning

        # --- Create Tabs for Different Views ---
        tab1, tab2 = st.tabs(["📊 Market Overview", "🔍 Screener & Deep Dive"])

        with tab1:
            st.header("Market Overview")
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("Overall Score Distribution")
                fig_hist = px.histogram(df, x="総合スコア", nbins=40, title="Score Distribution of Top Companies")
                st.plotly_chart(fig_hist, use_container_width=True)
            with col2:
                st.subheader("Top Performing Sectors")
                sector_scores = df.groupby('セクター')['総合スコア'].mean().sort_values(ascending=False)
                fig_bar = px.bar(sector_scores, orientation='h', title="Average Overall Score by Sector")
                fig_bar.update_layout(xaxis_title="Average Score", yaxis_title="Sector")
                st.plotly_chart(fig_bar, use_container_width=True)

            st.subheader("Value vs. Quality Landscape")
            fig_bubble = px.scatter(
                filtered_df, x='VALUEスコア', y='QUALITYスコア', size='時価総額',
                color='総合スコア', color_continuous_scale=px.colors.sequential.Viridis,
                hover_name='会社名', hover_data=['ティッカー', 'セクター']
            )
            st.plotly_chart(fig_bubble, use_container_width=True)

        with tab2:
            st.header("Stock Screener & Deep Dive")
            st.write(f"Displaying {len(filtered_df)} stocks based on your filters.")
            st.dataframe(filtered_df)
            st.markdown("---")
            st.subheader("Stock Deep Dive")

            if not filtered_df.empty:
                selected_stock_name = st.selectbox("Select a stock to analyze:", options=filtered_df['会社名'].tolist())
                if selected_stock_name:
                    stock_details = filtered_df[filtered_df['会社名'] == selected_stock_name].iloc[0]
                    col1, col2 = st.columns(2)
                    with col1:
                        st.subheader(f"Score Profile: {stock_details['会社名']}")
                        score_categories = ['VALUEスコア', 'QUALITYスコア', 'GROWTHスコア', 'MOMENTUMスコア']
                        score_values = stock_details[score_categories].values.flatten().tolist()
                        fig_radar = go.Figure(data=go.Scatterpolar(r=score_values, theta=score_categories, fill='toself'))
                        fig_radar.update_layout(polar=dict(radialaxis=dict(visible=True, range=[0, 10])))
                        st.plotly_chart(fig_radar, use_container_width=True)
                    with col2:
                        st.subheader(f"Price History: {stock_details['ティッカー']}")
                        price_history = get_price_history(stock_details['ティッカー'])
                        if price_history is not None:
                            fig_price = px.line(price_history, y='Close', title="1-Year Price History")
                            st.plotly_chart(fig_price, use_container_width=True)
                        else:
                            st.warning("Could not fetch price history.")
            else:
                st.warning("No stocks to display based on the current filter settings.")
    else:
        st.warning("Could not create dashboard because the initial data frame is empty.")
