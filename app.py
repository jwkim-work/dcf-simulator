import streamlit as st
import pandas as pd
import numpy_financial as npf
import plotly.graph_objects as go

st.set_page_config(layout="wide", page_title="Advanced RE DCF Model")

st.title("부동산 현금흐름(DCF) 및 민감도 분석 시뮬레이터")
st.markdown("수치 변동에 따른 투자 수익률(IRR) 영향도를 직관적으로 파악하기 위한 교육 및 분석용 도구")

# --- 1. 사이드바: 투자 변수 입력 ---
st.sidebar.header("1. 매입 및 운영 변수")
purchase_price = st.sidebar.number_input("총 매입가 (억원)", value=4035)
going_in_cap = st.sidebar.slider("매입 캡레이트 (Going-in Cap, %)", 2.0, 10.0, 4.5, 0.1) / 100
noi_growth = st.sidebar.slider("NOI 연 성장률 (%)", 0.0, 10.0, 2.0, 0.1) / 100
holding_period = st.sidebar.slider("보유 기간 (년)", 1, 10, 5)
exit_cap_rate = st.sidebar.slider("엑싯 캡레이트 (Exit Cap, %)", 2.0, 10.0, 5.0, 0.1) / 100

st.sidebar.header("2. 자본 구조 (Capital Stack)")
senior_ltv = st.sidebar.slider("선순위 대출 비중 (%)", 0, 80, 60) / 100
senior_rate = st.sidebar.slider("선순위 금리 (%)", 1.0, 10.0, 4.5, 0.1) / 100
mezz_ltv = st.sidebar.slider("메자닌 대출 비중 (%)", 0, 30, 0) / 100
mezz_rate = st.sidebar.slider("메자닌 금리 (%)", 3.0, 15.0, 7.5, 0.1) / 100

st.sidebar.header("3. 모델링 가정 (Assumptions)")
interest_calc_method = st.sidebar.radio(
    "이자 지급 방식 선택",
    ("단순 연리 (Simple Interest)", "분기 복리 (Quarterly Compounding)")
)

if senior_ltv + mezz_ltv >= 1.0:
    st.sidebar.error("🚨 선순위와 메자닌 비중의 합이 100%를 초과할 수 없습니다.")
    st.stop()

# --- 2. 핵심 금융 계산 로직 ---
senior_debt = purchase_price * senior_ltv
mezz_debt = purchase_price * mezz_ltv
equity = purchase_price - senior_debt - mezz_debt
year_1_noi = purchase_price * going_in_cap

if interest_calc_method == "단순 연리 (Simple Interest)":
    total_interest = (senior_debt * senior_rate) + (mezz_debt * mezz_rate)
else:
    total_interest = (senior_debt * ((1 + senior_rate/4)**4 - 1)) + (mezz_debt * ((1 + mezz_rate/4)**4 - 1))

cash_flows = [-equity] 
ncf_list = [] 

# ✅ Year 0 데이터 먼저 삽입
cf_data = [{
    "연차": "Year 0 (Investment)",
    "NOI (영업이익)": 0.0,
    "이자 비용": 0.0,
    "영업현금흐름 (NCF)": 0.0,
    "매각 수익 (Net Proceeds)": 0.0,
    "에쿼티 현금흐름 (Total CF)": round(-equity, 1)
}]

for t in range(1, holding_period + 1):
    current_noi = year_1_noi * ((1 + noi_growth)**(t-1))
    c_ncf = current_noi - total_interest
    
    if t == holding_period:
        next_year_noi = current_noi * (1 + noi_growth)
        exit_price = next_year_noi / exit_cap_rate
        net_proceeds = exit_price - senior_debt - mezz_debt
        
        cash_flows.append(c_ncf + net_proceeds)
        ncf_list.append(c_ncf + net_proceeds)
        cf_data.append({"연차": f"Year {t}", "NOI (영업이익)": round(current_noi, 1), "이자 비용": round(total_interest, 1), "영업현금흐름 (NCF)": round(c_ncf, 1), "매각 수익 (Net Proceeds)": round(net_proceeds, 1), "에쿼티 현금흐름 (Total CF)": round(c_ncf + net_proceeds, 1)})
    else:
        cash_flows.append(c_ncf)
        ncf_list.append(c_ncf)
        cf_data.append({"연차": f"Year {t}", "NOI (영업이익)": round(current_noi, 1), "이자 비용": round(total_interest, 1), "영업현금흐름 (NCF)": round(c_ncf, 1), "매각 수익 (Net Proceeds)": 0.0, "에쿼티 현금흐름 (Total CF)": round(c_ncf, 1)})

irr = npf.irr(cash_flows) * 100 if npf.irr(cash_flows) is not None else 0
equity_multiple = sum(ncf_list) / equity if equity > 0 else 0

# --- 3. 화면 출력 ---
col1, col2, col3 = st.columns(3)
col1.metric("총 매입가", f"{purchase_price:,.0f} 억원")
col2.metric("투입 에쿼티 (Equity)", f"{equity:,.0f} 억원")
col3.metric("1년차 NOI", f"{year_1_noi:,.1f} 억원")

st.markdown("---")
res_col1, res_col2 = st.columns(2)
res_col1.metric("🎯 Levered IRR (에쿼티 수익률)", f"{irr:.2f}%")
res_col2.metric("💰 Equity Multiple (지분 배수)", f"{equity_multiple:.2f}x")
st.markdown("---")

st.subheader("📊 연도별 현금흐름표 (Cash Flow Waterfall)")
df_cf = pd.DataFrame(cf_data)
st.dataframe(df_cf, use_container_width=True)
st.markdown("---")

# --- 4. 동적 민감도 분석 (Tornado Chart) 로직 ---
def calc_sensitivity_irr(test_exit_cap, test_noi_growth, test_senior_rate):
    t_year_1_noi = purchase_price * going_in_cap
    if interest_calc_method == "단순 연리 (Simple Interest)":
        t_total_interest = (senior_debt * test_senior_rate) + (mezz_debt * mezz_rate)
    else:
        t_total_interest = (senior_debt * ((1 + test_senior_rate/4)**4 - 1)) + (mezz_debt * ((1 + mezz_rate/4)**4 - 1))
    
    t_cf = [-equity]
    for t in range(1, holding_period + 1):
        c_noi = t_year_1_noi * ((1 + test_noi_growth)**(t-1))
        c_ncf = c_noi - t_total_interest
        if t == holding_period:
            n_noi = c_noi * (1 + test_noi_growth)
            e_price = n_noi / test_exit_cap
            n_proceeds = e_price - senior_debt - mezz_debt
            t_cf.append(c_ncf + n_proceeds)
        else:
            t_cf.append(c_ncf)
    res = npf.irr(t_cf)
    return res * 100 if res is not None else 0

irr_base = irr
irr_exit_down = calc_sensitivity_irr(exit_cap_rate - 0.005, noi_growth, senior_rate)
irr_exit_up = calc_sensitivity_irr(exit_cap_rate + 0.005, noi_growth, senior_rate)
irr_growth_down = calc_sensitivity_irr(exit_cap_rate, noi_growth - 0.01, senior_rate)
irr_growth_up = calc_sensitivity_irr(exit_cap_rate, noi_growth + 0.01, senior_rate)
irr_rate_down = calc_sensitivity_irr(exit_cap_rate, noi_growth, senior_rate - 0.005)
irr_rate_up = calc_sensitivity_irr(exit_cap_rate, noi_growth, senior_rate + 0.005)

st.subheader("🌪️ 핵심 변수별 IRR 민감도 (Tornado Chart)")
variables = ['Exit Cap (+/- 0.5%p)', 'NOI 성장률 (+/- 1.0%p)', '선순위 금리 (+/- 0.5%p)']
low_impact = [irr_exit_up - irr_base, irr_growth_down - irr_base, irr_rate_up - irr_base]
high_impact = [irr_exit_down - irr_base, irr_growth_up - irr_base, irr_rate_down - irr_base]

fig = go.Figure()
fig.add_trace(go.Bar(y=variables, x=low_impact, base=irr_base, name='악화 시 (Downside)', orientation='h', marker_color='#ff4b4b'))
fig.add_trace(go.Bar(y=variables, x=high_impact, base=irr_base, name='개선 시 (Upside)', orientation='h', marker_color='#00cc96'))
fig.update_layout(barmode='relative', title_text='Base IRR 대비 수익률 변동 폭', xaxis_title='IRR (%)')
st.plotly_chart(fig, use_container_width=True)
