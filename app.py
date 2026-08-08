import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from portfolio_constraint import PortfolioConstraintApplicator

# 1. Page Configuration
st.set_page_config(
    page_title="FidelFolio | Portfolio Constraint Application",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. Premium Custom CSS Styling (Glassmorphism & Vibrant Dark Theme)
st.markdown("""
<style>
    /* Import modern Google Font */
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&display=swap');
    
    html, body, [class*="css"], .stApp {
        font-family: 'Outfit', sans-serif;
    }
    
    /* Title styling */
    .title-gradient {
        background: linear-gradient(135deg, #00f2fe 0%, #4facfe 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 700;
        font-size: 3rem;
        margin-bottom: 5px;
    }
    
    .subtitle-text {
        font-size: 1.1rem;
        color: #a0aec0;
        margin-bottom: 25px;
    }
    
    /* Custom cards for metrics */
    .glass-card {
        background: rgba(255, 255, 255, 0.03);
        backdrop-filter: blur(10px);
        border-radius: 16px;
        padding: 20px;
        border: 1px solid rgba(255, 255, 255, 0.08);
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.2);
        transition: all 0.3s ease;
        text-align: center;
        margin-bottom: 15px;
    }
    .glass-card:hover {
        transform: translateY(-3px);
        border-color: rgba(0, 242, 254, 0.3);
        box-shadow: 0 12px 40px 0 rgba(0, 242, 254, 0.1);
    }
    
    .card-title {
        font-size: 0.8rem;
        color: #718096;
        text-transform: uppercase;
        letter-spacing: 1.5px;
        font-weight: 600;
        margin-bottom: 8px;
    }
    
    .card-value {
        font-size: 2.2rem;
        font-weight: 700;
        background: linear-gradient(135deg, #00f2fe 0%, #4facfe 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    
    /* Section dividers */
    .section-header {
        font-size: 1.4rem;
        font-weight: 600;
        color: #e2e8f0;
        border-bottom: 2px solid rgba(255, 255, 255, 0.05);
        padding-bottom: 8px;
        margin-top: 25px;
        margin-bottom: 15px;
    }
</style>
""", unsafe_allow_html=True)

# 3. Load & Cache Applicator
@st.cache_resource
def get_applicator():
    rules_file = 'assignment_investment_rules.csv'
    sector_file = 'assignment_sector_data.csv'
    mcap_file = 'assignment_mcap.csv'
    return PortfolioConstraintApplicator(rules_file, sector_file, mcap_file)

try:
    applicator = get_applicator()
except Exception as e:
    st.error(f"Error loading datasets. Please ensure raw CSV files exist in the repository root directory. Details: {e}")
    st.stop()

# 4. Custom Parameterized Constraint Logic
def run_custom_pipeline(stocks, year, mcap_percent, sector_percent):
    if not stocks:
        return [], [], [], []
    
    # --- STAGE 1: Market Cap Screen ---
    stocks_with_mcap = []
    for stock in stocks:
        mcap = applicator.mcap_dict.get(stock, {}).get(year, 0)
        stocks_with_mcap.append((stock, mcap))
    stocks_with_mcap.sort(key=lambda x: x[1], reverse=True)
    
    cutoff_index = int(len(stocks_with_mcap) * mcap_percent)
    mcap_kept = [stock for stock, _ in stocks_with_mcap[:cutoff_index]]
    mcap_excluded = [stock for stock, _ in stocks_with_mcap[cutoff_index:]]
    
    # --- STAGE 2: Sector Concentration Limit ---
    max_per_sector = int(len(mcap_kept) * sector_percent)
    if max_per_sector < 1:
        max_per_sector = 1
        
    stocks_by_sector = {}
    for stock in mcap_kept:
        sector = applicator.sector_dict.get(stock, 'Unknown')
        if sector not in stocks_by_sector:
            stocks_by_sector[sector] = []
        mcap = applicator.mcap_dict.get(stock, {}).get(year, 0)
        stocks_by_sector[sector].append((stock, mcap))
        
    sector_kept = []
    sector_excluded = []
    for sector, sector_stocks in stocks_by_sector.items():
        sector_stocks.sort(key=lambda x: x[1], reverse=True)
        for i, (stock, mcap) in enumerate(sector_stocks):
            if i < max_per_sector:
                sector_kept.append(stock)
            else:
                sector_excluded.append(stock)
                
    return sector_kept, mcap_excluded, sector_excluded, stocks_with_mcap

# 5. Sidebar Controls & Configurations
st.sidebar.markdown("### ⚙️ Optimization Parameters")

# Strategy selection
strategies = applicator.investment_rules['strat_name'].unique().tolist()
selected_strategy = st.sidebar.selectbox("Select Investment Strategy", strategies, index=0)

# Year selection (excluding the strategy name column)
year_columns = [col for col in applicator.investment_rules.columns if col != 'strat_name']
selected_year = st.sidebar.selectbox("Select Year", year_columns, index=len(year_columns) - 2) # Default to 2021

st.sidebar.markdown("---")
st.sidebar.markdown("### 🛠️ Adjust Constraint Thresholds")

# Market Cap constraint slider
mcap_cutoff_slider = st.sidebar.slider(
    "Market Cap Keep Threshold (Top %)",
    min_value=50,
    max_value=100,
    value=80,
    step=5,
    help="Default is keeping top 80% (excluding the bottom 20% by market cap)."
) / 100.0

# Sector limit slider
sector_limit_slider = st.sidebar.slider(
    "Maximum Allocation per Sector (%)",
    min_value=5,
    max_value=100,
    value=25,
    step=5,
    help="Default limits each sector to a maximum of 25% of the portfolio."
) / 100.0

# 6. Title and Banner
st.markdown('<div class="title-gradient">FidelFolio</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle-text">Systematic Portfolio Constraint Optimization Dashboard</div>', unsafe_allow_html=True)

# 7. Main Application Logic
strategy_row = applicator.investment_rules[applicator.investment_rules['strat_name'] == selected_strategy].iloc[0]
raw_stocks_str = strategy_row[selected_year]

# Parse raw stock list
original_stocks = applicator.parse_stock_list(raw_stocks_str)

if not original_stocks:
    st.info(f"No stock holdings found for strategy and year combination: {selected_strategy} in {selected_year}.")
    st.stop()

# Run constraint solver
constrained_stocks, mcap_excluded, sector_excluded, stocks_with_mcap_data = run_custom_pipeline(
    original_stocks, selected_year, mcap_cutoff_slider, sector_limit_slider
)

total_exclusions = len(mcap_excluded) + len(sector_excluded)
exclusion_rate = (total_exclusions / len(original_stocks)) * 100 if original_stocks else 0

# Count unique sectors present post-constraint
final_sectors = set(applicator.sector_dict.get(s, 'Unknown') for s in constrained_stocks)

# 8. Render Metric Cards
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.markdown(f'''
        <div class="glass-card">
            <div class="card-title">Original Size</div>
            <div class="card-value">{len(original_stocks)}</div>
        </div>
    ''', unsafe_allow_html=True)
with col2:
    st.markdown(f'''
        <div class="glass-card">
            <div class="card-title">Constrained Size</div>
            <div class="card-value">{len(constrained_stocks)}</div>
        </div>
    ''', unsafe_allow_html=True)
with col3:
    st.markdown(f'''
        <div class="glass-card">
            <div class="card-title">Exclusion Rate</div>
            <div class="card-value">{exclusion_rate:.1f}%</div>
        </div>
    ''', unsafe_allow_html=True)
with col4:
    st.markdown(f'''
        <div class="glass-card">
            <div class="card-title">Unique Sectors</div>
            <div class="card-value">{len(final_sectors)}</div>
        </div>
    ''', unsafe_allow_html=True)

# 9. Tabs for Layout Structure
tab_dashboard, tab_explorer, tab_batch = st.tabs(["📊 Analytical Dashboard", "🔍 Portfolio Explorer", "⚙️ Batch Runner"])

with tab_dashboard:
    # Row for visual distributions
    col_left, col_right = st.columns(2)
    
    with col_left:
        st.markdown('<div class="section-header">Sector Concentration Analysis</div>', unsafe_allow_html=True)
        
        # Sector weights post-constraint
        sector_counts = {}
        for stock in constrained_stocks:
            sec = applicator.sector_dict.get(stock, 'Unknown')
            sector_counts[sec] = sector_counts.get(sec, 0) + 1
            
        if sector_counts:
            df_sector = pd.DataFrame({
                'Sector': list(sector_counts.keys()),
                'Stocks Count': list(sector_counts.values())
            }).sort_values(by='Stocks Count', ascending=True)
            
            # Max sector limit value for line reference
            max_limit_val = int(len(constrained_stocks) * sector_limit_slider)
            
            fig_sec = px.bar(
                df_sector,
                y='Sector',
                x='Stocks Count',
                orientation='h',
                template='plotly_dark',
                color='Stocks Count',
                color_continuous_scale=['#00f2fe', '#4facfe']
            )
            fig_sec.update_layout(
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                coloraxis_showscale=False,
                margin=dict(l=10, r=10, t=10, b=10),
                height=350
            )
            fig_sec.add_vline(x=max_limit_val, line_width=2, line_dash="dash", line_color="#ff70a6")
            st.plotly_chart(fig_sec, use_container_width=True)
        else:
            st.warning("No sectors to analyze.")
            
    with col_right:
        st.markdown('<div class="section-header">Market Cap Categorization</div>', unsafe_allow_html=True)
        
        # Classify caps post-constraint
        cap_counts = {'Large-Cap (>10,000 Cr)': 0, 'Mid-Cap (1,000-10,000 Cr)': 0, 'Small-Cap (<1,000 Cr)': 0}
        for stock in constrained_stocks:
            mcap_val = applicator.mcap_dict.get(stock, {}).get(selected_year, 0)
            if mcap_val > 10000:
                cap_counts['Large-Cap (>10,000 Cr)'] += 1
            elif mcap_val >= 1000:
                cap_counts['Mid-Cap (1,000-10,000 Cr)'] += 1
            else:
                cap_counts['Small-Cap (<1,000 Cr)'] += 1
                
        df_cap = pd.DataFrame({
            'Category': list(cap_counts.keys()),
            'Count': list(cap_counts.values())
        })
        
        fig_cap = px.pie(
            df_cap,
            names='Category',
            values='Count',
            hole=0.45,
            template='plotly_dark',
            color='Category',
            color_discrete_map={
                'Large-Cap (>10,000 Cr)': '#00d2ff',
                'Mid-Cap (1,000-10,000 Cr)': '#9d4edd',
                'Small-Cap (<1,000 Cr)': '#ff70a6'
            }
        )
        fig_cap.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            margin=dict(l=10, r=10, t=10, b=10),
            height=350
        )
        st.plotly_chart(fig_cap, use_container_width=True)

with tab_explorer:
    st.markdown('<div class="section-header">Portfolio Constituents Explorer</div>', unsafe_allow_html=True)
    
    # Detailed data table of kept stocks
    details_list = []
    for s in constrained_stocks:
        mcap_val = applicator.mcap_dict.get(s, {}).get(selected_year, 0)
        sec = applicator.sector_dict.get(s, 'Unknown')
        details_list.append({'Stock Name': s, 'Sector': sec, f'MCap {selected_year} (Cr)': f"{mcap_val:,.2f}"})
        
    df_details = pd.DataFrame(details_list)
    
    col_tab_left, col_tab_right = st.columns([3, 2])
    
    with col_tab_left:
        st.markdown(f"**Kept Assets ({len(constrained_stocks)} Stocks)**")
        if not df_details.empty:
            st.dataframe(df_details, use_container_width=True, height=450)
        else:
            st.info("No stocks kept in final portfolio.")
            
    with col_tab_right:
        st.markdown(f"**Exclusion Log ({total_exclusions} Excluded)**")
        
        with st.expander(f"🚫 Market Cap Exclusions ({len(mcap_excluded)})"):
            if mcap_excluded:
                for s in mcap_excluded:
                    val = applicator.mcap_dict.get(s, {}).get(selected_year, 0)
                    st.text(f"• {s} (MCap: {val:,.2f} Cr)")
            else:
                st.text("No stocks excluded by Market Cap Filter.")
                
        with st.expander(f"🚫 Sector Over-concentration Exclusions ({len(sector_excluded)})"):
            if sector_excluded:
                for s in sector_excluded:
                    val = applicator.mcap_dict.get(s, {}).get(selected_year, 0)
                    sec = applicator.sector_dict.get(s, 'Unknown')
                    st.text(f"• {s} ({sec} | MCap: {val:,.2f} Cr)")
            else:
                st.text("No stocks excluded by Sector Constraint.")

with tab_batch:
    st.markdown('<div class="section-header">Full System Batch Optimization</div>', unsafe_allow_html=True)
    st.write("This tool processes all 100 strategies across all years using the slider-defined custom thresholds, and outputs a downloadable `output_custom.csv` file.")
    
    if st.button("🚀 Trigger Full Batch Process"):
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Clone investment rules df to update
        batch_df = applicator.investment_rules.copy()
        total_strats = len(batch_df)
        
        for idx, row in batch_df.iterrows():
            status_text.text(f"Processing strategy {idx+1}/{total_strats}: {row['strat_name'][:50]}...")
            
            for y_col in year_columns:
                s_list_str = row[y_col]
                if pd.isna(s_list_str) or str(s_list_str).strip() == '':
                    continue
                    
                parsed_s = applicator.parse_stock_list(s_list_str)
                if not parsed_s:
                    continue
                    
                # Run the pipeline
                final_s, _, _, _ = run_custom_pipeline(parsed_s, y_col, mcap_cutoff_slider, sector_limit_slider)
                batch_df.at[idx, y_col] = str(final_s)
                
            progress_bar.progress((idx + 1) / total_strats)
            
        status_text.text("✅ Full batch optimization complete!")
        
        # Download button
        csv_data = batch_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download Custom Output CSV",
            data=csv_data,
            file_name="output_custom.csv",
            mime="text/csv"
        )
