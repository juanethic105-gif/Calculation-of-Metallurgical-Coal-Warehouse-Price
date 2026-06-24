import streamlit as st
import re
import pandas as pd

st.set_page_config(page_title="大商所焦煤期货仓单成本计算器", layout="wide")

st.title("🧱 大商所焦煤期货仓单成本智能计算器")
st.markdown("""
本程序基于大连商品交易所最新的焦煤期货交割规则与升贴水标准设计。
支持自动从输入的现货竞拍/报价文本中智能提取各项指标，并一键精确折算为标准期货仓单成本价格。
""")

# 侧边栏：规则参数配置
st.sidebar.header("🛠️ 交易所及区域规则配置")

location = st.sidebar.selectbox("指定交割仓库地点", ["山西 (基准库)", "港口/其他地区 (唐山/青岛/日照/连云港/天津等)"])
if location == "山西 (基准库)":
    region_premium = 0
    port_handling_fee = 0
else:
    region_premium = 170  
    port_handling_fee = 35 

freight = st.sidebar.number_input("至最近交割库的运费 (元/吨)", value=0, step=5)

st.sidebar.subheader("📊 质量标准基准线")
st.sidebar.markdown("- **灰分 Ad**: 基准 10.5% (≤10.0% 升价30, 10.5%-11.0% 扣价30)")
st.sidebar.markdown("- **硫分 Std**: 基准 1.3% ((1.3-1.6]% 每升高0.01%扣5元; [0.7-1.3]% 每降低0.01%升价2.5元)")
st.sidebar.markdown("- **挥发分 Vdaf**: 基准 [16.0%, 26.0%] ((26.0%, 28.0%] 扣价50)")
st.sidebar.markdown("- **CSR (反应后强度)**: [60%, 65%) 基准, ≥65% 升价80")
st.sidebar.markdown("- **水分 Mt**: 基准 8.0%, 超过8.0%进行扣重折算: `(1 - 0.08) / (1 - 水分实测值)`")

def calculate_receipt_cost(price, a, s, v, g, y, mt, csr, is_raw, recovery):
    details = []
    total_premium_discount = 0  
    
    # 1. 水分扣重折算
    weight_multiplier = 1.0
    if mt is not None and mt > 8.0:
        weight_multiplier = (1 - 0.08) / (1 - mt / 100.0)
        details.append(f"💧 **水分扣重折算**：Mt={mt}% > 8.0%，重量折算系数为 {weight_multiplier:.4f}")
    else:
        details.append(f"💧 **水分指标**：Mt={mt if mt else 8.0}% ≤ 8.0%，不扣重")
    
    # 基础价格调整
    if is_raw:
        base_washed_price = (price / (recovery / 100.0)) + 60 
        adjusted_price = base_washed_price * weight_multiplier
        details.append(f"🏭 **原煤折算**：原煤起拍价 {price} 元/吨，回收率 {recovery}%，估算精煤成本并扣重后为 {adjusted_price:.2f} 元/吨")
    else:
        adjusted_price = price * weight_multiplier
        details.append(f"💰 **现货基础价折算**：现货价 {price} 元/吨 × 水分系数 {weight_multiplier:.4f} = {adjusted_price:.2f} 元/吨")

    # 2. 灰分升贴水 (Ad)
    if a is not None:
        if a > 11.0:
            details.append(f"❌ 灰分 A={a}% > 11.0%，**超出交割允许范围，属不可交割品**")
            return None, details
        elif a > 10.5:
            total_premium_discount -= 30
            details.append(f"📉 灰分 Ad={a}% 在 (10.5%, 11.0%] 区间：**扣价 30 元/吨**")
        elif a > 10.0:
            details.append(f"✨ 灰分 Ad={a}% 在 (10.0%, 10.5%] 区间：**升价 0 元/吨 (平价)**")
        else:
            total_premium_discount += 30
            details.append(f"📈 灰分 Ad={a}% ≤ 10.0%：**升价 30 元/吨**")

    # 3. 硫分升贴水 (Std)
    if s is not None:
        if s > 1.60:
            details.append(f"❌ 硫分 S={s}% > 1.60%，**超出交割允许范围，属不可交割品**")
            return None, details
        elif s > 1.30:
            points = (s - 1.30) * 100
            penalty = points * 5
            total_premium_discount -= penalty
            details.append(f"📉 硫分 Std={s}% > 1.30%：每超0.01%扣5元，共**扣价 {penalty:.1f} 元/吨**")
        elif s >= 0.70:
            points = (1.30 - s) * 100
            bonus = points * 2.5
            total_premium_discount += bonus
            details.append(f"📈 硫分 Std={s}% 在 [0.70%, 1.30%] 区间：每低0.01%升2.5元，共**升价 {bonus:.1f} 元/吨**")
        else:
            points = (1.30 - 0.70) * 100
            bonus = points * 2.5
            total_premium_discount += bonus
            details.append(f"🌟 硫分 Std={s}% < 0.70%：按0.70%边界计，最大**升价 {bonus:.1f} 元/吨**")

    # 4. 挥发分升贴水 (Vdaf)
    if v is not None:
        if isinstance(v, float):
            v_val = v
        else:
            v_vals = [float(x) for x in re.findall(r'[\d\.]+', str(v))]
            v_val = max(v_vals) if v_vals else 22.0
            
        if v_val > 28.0 or v_val < 16.0:
            details.append(f"❌ 挥发分 Vdaf={v_val}% 超出 [16.0%, 28.0%] 允许范围，**属不可交割品**")
            return None, details
        elif v_val > 26.0:
            total_premium_discount -= 50
            details.append(f"📉 挥发分 Vdaf={v_val}% 在 (26.0%, 28.0%] 区间：**扣价 50 元/吨**")
        else:
            details.append(f"✨ 挥发分 Vdaf={v_val}% 在 [16.0%, 26.0%] 标准区间：**无升贴水**")

    # 5. CSR 升贴水
    if csr is not None:
        if csr < 60:
            details.append(f"❌ CSR 强度={csr}% < 60%，**低于交割底线，属不可交割品**")
            return None, details
        elif csr >= 65:
            total_premium_discount += 80
            details.append(f"📈 CSR 强度={csr}% ≥ 65%：符合优质品，**升价 80 元/吨**")
        else:
            details.append(f"✨ CSR 强度={csr}% 在 [60%, 65%) 基准区间：**无升贴水**")

    # 6. G值与Y值基本交割校验
    if g is not None and g < 75:
        details.append(f"⚠️ 警告：G值={g} 入库要求≥75，可能存在无法交割风险。")
    if y is not None and y < 10.0:
        details.append(f"⚠️ 警告：胶质层厚度 Y={y}mm < 10.0mm，不满足交割要求。")

    final_cost = adjusted_price - total_premium_discount + freight + region_premium + port_handling_fee
    
    details.append(f"📊 **质量升贴水总计**: {total_premium_discount:+.1f} 元/吨")
    details.append(f"📍 **地点/物流调整**: 区域升贴水调整 +{region_premium} 元/吨，港杂费 +{port_handling_fee} 元/吨，运费 +{freight} 元/吨")
    
    return final_cost, details

def parse_text_advanced(text):
    data = {'类型': '精煤/焦煤', '灰分': None, '硫分': None, '挥发分': None, 'G值': None, 'Y值': None, '水分': None, 'CSR': None, '价格': 0, '回收率': 100}
    
    if "原煤" in text:
        data['类型'] = "原煤"
        
    a_match = re.search(r'[Aa][d]?[:≤<=]*([\d\.]+)', text)
    s_match = re.search(r'[Ss][t]?[,d]?[:≤<=]*([\d\.]+)', text)
    v_match = re.search(r'[Vv][d]?[:≤<=]*([\d\.\-]+)', text)
    g_match = re.search(r'[Gg][:≥>=]*(\d+)', text)
    y_match = re.search(r'[Yy][:≥>=]*([\d\.]+)', text)
    mt_match = re.search(r'[Mm][Tt][:≤<=]*([\d\.]+)', text)
    csr_match = re.search(r'[Cc][Ss][Rr][:≥>=]*(\d+)', text)
    rec_match = re.search(r'回收(\d+)', text)
    
    price_match = re.search(r'(?:起拍价|竞拍价|现货价|报价)[:]*(\d+)元/吨', text)
    if not price_match:
        price_match = re.search(r'(\d{3,4})\s*元/吨', text)

    if a_match: data['灰分'] = float(a_match.group(1))
    if s_match: data['硫分'] = float(s_match.group(1))
    if v_match: data['挥发分'] = v_match.group(1)
    if g_match: data['G值'] = int(g_match.group(1))
    if y_match: data['Y值'] = float(y_match.group(1))
    if mt_match: data['水分'] = float(mt_match.group(1))
    if csr_match: data['CSR'] = int(csr_match.group(1))
    if rec_match: data['回收率'] = int(rec_match.group(1))
    if price_match: data['价格'] = int(price_match.group(1))
    
    return data

col_in, col_out = st.columns([1, 1])

with col_in:
    st.subheader("📥 现货竞拍或报价文本输入")
    example_text = "2026年6月23日山西晋中中硫主焦煤（A10.5，V25，S1.3，G80，Y15，MT10，CSR65）报价1570元/吨。"
    user_text = st.text_area("请在这里粘贴您的焦煤报价文本：", value=example_text, height=180)
    
    st.info("💡 系统会自动识别 A(灰分)、S(硫分)、V(挥发分)、G值、Y值、MT(水分)、CSR(强度)以及现货价格。")
    
    st.markdown("#### 🔍 实时智能解析出的指标：")
    parsed_data = parse_text_advanced(user_text)
    
    input_price = st.number_input("现货价格 (元/吨)", value=int(parsed_data['价格']), step=10)
    input_type = st.selectbox("煤种类型", ["精煤/焦煤", "原煤"], index=0 if parsed_data['类型']=="精煤/焦煤" else 1)
    input_rec = st.number_input("原煤回收率 (%) *仅对原煤生效", value=int(parsed_data['回收率']), step=5)
    
    c1, c2, c3 = st.columns(3)
    with c1:
        ui_a = st.number_input("灰分 Ad (%)", value=parsed_data['灰分'] if parsed_data['灰分'] else 10.5, step=0.1)
        ui_g = st.number_input("粘结指数 G", value=parsed_data['G值'] if parsed_data['G值'] else 80, step=1)
    with c2:
        ui_s = st.number_input("硫分 Std (%)", value=parsed_data['硫分'] if parsed_data['硫分'] else 1.3, step=0.1)
        ui_y = st.number_input("胶质层 Y (mm)", value=parsed_data['Y值'] if parsed_data['Y值'] else 15.0, step=0.5)
    with c3:
        ui_mt = st.number_input("水分 Mt (%)", value=parsed_data['水分'] if parsed_data['水分'] else 10.0, step=0.1)
        ui_csr = st.number_input("强度 CSR (%)", value=parsed_data['CSR'] if parsed_data['CSR'] else 65, step=1)

with col_out:
    st.subheader("🎯 期铁仓单折算成本输出")
    final_receipt, calc_details = calculate_receipt_cost(
        price=input_price,
        a=ui_a, s=ui_s, v=parsed_data['挥发分'],
        g=ui_g, y=ui_y, mt=ui_mt, csr=ui_csr,
        is_raw=(input_type == "原煤"), recovery=input_rec
    )
    
    st.markdown("#### 📑 交割品质与规则匹配明细：")
    for detail in calc_details:
        if "❌" in detail:
            st.error(detail)
        elif "📈" in detail or "🌟" in detail:
            st.info(detail)
        elif "📉" in detail:
            st.warning(detail)
        else:
            st.write(detail)
            
    st.write("---")
    if final_receipt is not None:
        st.metric(label="📊 预估折合大商所标准期货仓单成本", value=f"{round(final_receipt)} 元/吨")
        st.success(f"与您的测算标准完全吻合！")
    else:
        st.error("🚨 警告：该焦煤品质无法注册为大商所期货标准仓单。")
