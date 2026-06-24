import streamlit as st
import re
import pandas as pd

st.set_page_config(page_title="大商所焦煤期货仓单成本计算器", layout="wide")

# ==========================================
# 辅助提取函数 (必须放在最顶部，防止 NameError)
# ==========================================
def parse_text_advanced(text):
    data = {'类型': '精煤/焦煤', '灰分': None, '硫分': None, '挥发分': None, 'G值': None, 'Y值': None, '水分': None, 'CSR': None, '价格': 0, '回收率': None}
    if not text.strip():
        return data
        
    if "原煤" in text: 
        data['类型'] = "原煤"
    
    # 防混淆核心：如果文本包含分号“；”，只取前半句（即本期竞拍详情），直接扔掉上期历史干扰信息
    clean_text = text.split('；')[0].split(';')[0]
    
    # 智能解析核心指标 (兼容 内灰、A、Ad、S、Std、V、Vdaf、G、Y、MT、CSR)
    a_match = re.search(r'(?:[Aa][d]?|内灰)[:≤<=]*([\d\.]+)', clean_text)
    s_match = re.search(r'[Ss][t]?[,d]?[:≤<=]*([\d\.]+)', clean_text)
    v_match = re.search(r'[Vv][d]?[:≤<=]*([\d\.\-]+)', clean_text)
    g_match = re.search(r'[Gg][:≥>=]*(\d+)', clean_text)
    y_match = re.search(r'[Yy][:≥>=]*([\d\.]+)', clean_text)
    mt_match = re.search(r'[Mm][Tt][:≤<=]*([\d\.]+)', clean_text)
    csr_match = re.search(r'[Cc][Ss][Rr][:≥>=]*(\d+)', clean_text)
    rec_match = re.search(r'回收(\d+)', clean_text)
    
    # 精准价格抓取逻辑（防倒扣、防上期干扰、防涨跌幅数字干扰）
    price_final = 0
    if "流拍" in clean_text:
        # 流拍：寻找起拍价
        start_price = re.search(r'起拍价[:]*(\d+)', clean_text)
        if start_price: price_final = int(start_price.group(1))
    else:
        # 成交：优先寻找成交价区间（如 1079-1101），并取最低价
        deal_range = re.search(r'以(\d+)-(\d+)元/吨', clean_text)
        if deal_range:
            price_final = int(deal_range.group(1)) # 取下限
        else:
            # 如果是单一成交价（如 1710元/吨）
            single_deal = re.search(r'以[:]*(\d+)元/吨', clean_text)
            if single_deal:
                price_final = int(single_deal.group(1))
            else:
                # 兜底：直接找起拍价
                start_price = re.search(r'起拍价[:]*(\d+)', clean_text)
                if start_price: price_final = int(start_price.group(1))

    if a_match: data['灰分'] = float(a_match.group(1))
    if s_match: data['硫分'] = float(s_match.group(1))
    if v_match: data['挥发分'] = v_match.group(1)
    if g_match: data['G值'] = int(g_match.group(1))
    if y_match: data['Y值'] = float(y_match.group(1))
    if mt_match: data['水分'] = float(mt_match.group(1))
    if csr_match: data['CSR'] = int(csr_match.group(1))
    if rec_match: data['回收率'] = int(rec_match.group(1))
    data['价格'] = price_final
    return data

# ==========================================
# 页面渲染区
# ==========================================
st.title("🧱 大商所焦煤期货仓单成本智能计算器")
st.markdown("""
本程序基于大连商品交易所最新的焦煤期货交割规则与升贴水标准设计。
已启用**无指标即最差可交割档位算法**与**关键项强制填选机制**，全面防范期现套利中的指标缺失风险。
""")

st.sidebar.header("🛠️ 交易所及区域规则配置")

location = st.sidebar.selectbox(
    "1. 指定交割仓库地点 **:red[必填]**", 
    ["请选择...", "山西 (基准库)", "港口/其他地区 (唐山/青岛/日照/连云港/天津等)"]
)
if location == "山西 (基准库)":
    region_premium = 0
    port_handling_fee = 0
elif location == "港口/其他地区 (唐山/青岛/日照/连云港/天津等)":
    region_premium = 170  
    port_handling_fee = 35 
else:
    region_premium = None
    port_handling_fee = None

freight_input = st.sidebar.text_input("2. 至最近交割库的运费 (元/吨)**:red[必填]** *无运费请输入0", value="")

st.sidebar.subheader("📊 质量标准基准线（无指标即最差可交割档位）")
st.sidebar.markdown("- **灰分 Ad**: 基准 10.5% ; 【≤10.0% 升价30; 10.5%-11.0% 扣价30】")
st.sidebar.markdown("- **硫分 Std**: 基准 1.3% ; 【(1.3-1.6]% 每升高0.01%扣5元; [0.7-1.3]% 每降低0.01%升价2.5元; <0.7% 不额外升水，按0.7%档位封顶升价】")
st.sidebar.markdown("- **挥发分 Vdaf**: 基准 [16.0%, 26.0%] ; 【(26.0%, 28.0%] 扣价50】")
st.sidebar.markdown("- **GR.I (黏结指数)**: 基准 入库≥75，出库>65，无升贴水")
st.sidebar.markdown("- **Y (胶质层最大厚度)**: 基准 10mm；【>10mm，无升贴水】")
st.sidebar.markdown("- **CSR (反应后强度)**: 基准 [60%, 65%) ; ≥65% 升价80")
st.sidebar.markdown("- **水分 Mt**: 基准 8.0%, 超过8.0%进行扣重折算: `(1 - 0.08) / (1 - 水分实测值)`")
st.sidebar.markdown("- **镜质体随机反射率标准差**: 基准 0.13")
st.sidebar.markdown("- **镜质体最大反射率**: 基准 （1.0, 1.7），占比≥70%")

col_in, col_out = st.columns([1, 1])

with col_in:
    st.subheader("📥 现货竞拍或报价文本输入")
    user_text = st.text_area("请在这里粘贴您的焦煤报价文本**:red[必填]**：", value="", placeholder="请在此粘贴现货竞拍或群聊报价文字...", height=150)
    
    parsed_data = parse_text_advanced(user_text)
    
    st.markdown("#### 🔍 核心交易要素核对（请逐项确认或修正）：")
    input_price = st.number_input("3. 现货价格 (元/吨)", value=int(parsed_data['价格']), step=10)
    input_type = st.selectbox("4. 煤种类型 **:red[必填]**", ["请选择...", "精煤/焦煤", "原煤"], index=2 if parsed_data['类型']=="原煤" else 0)
    
    if input_type == "原煤":
        rec_val = parsed_data['回收率'] if parsed_data['回收率'] else 90
        input_rec_str = st.text_input("5. 原煤回收率 (%) (原煤**:red[必填]**)", value=str(rec_val))
        try:
            input_rec = float(input_rec_str)
        except ValueError:
            input_rec = None
    else:
        input_rec = 100.0  

    st.markdown("#### 🔬 质量指标明细 (若缺省将启用交割底线估算)：")
    
    real_missing_for_warning = []
    if parsed_data['灰分'] is None: 
        real_missing_for_warning.append("灰分(Ad)")
        default_a = 11.0
    else: 
        default_a = parsed_data['灰分']
        
    if parsed_data['硫分'] is None: 
        real_missing_for_warning.append("硫分(Std)")
        default_s = 1.60
    else: 
        default_s = parsed_data['硫分']
        
    if parsed_data['挥发分'] is None: 
        real_missing_for_warning.append("挥发分(Vdaf)")
        default_v = 28.0
    else:
        try:
            if '-' in str(parsed_data['挥发分']):
                default_v = float(max(re.findall(r'[\d\.]+', str(parsed_data['挥发分']))))
            else:
                default_v = float(parsed_data['挥发分'])
        except:
            default_v = 28.0

    if parsed_data['水分'] is None: 
        real_missing_for_warning.append("水分(Mt)")
        default_mt = 8.0
    else: 
        default_mt = parsed_data['水分']
        
    if parsed_data['CSR'] is None: 
        real_missing_for_warning.append("强度(CSR)")
        default_csr = 60
    else: 
        default_csr = parsed_data['CSR']

    c1, c2, c3 = st.columns(3)
    with c1:
        ui_a = st.number_input("灰分 Ad (%)", value=float(default_a), step=0.1)
        ui_g = st.number_input("粘结指数 G", value=int(parsed_data['G值']) if parsed_data['G值'] else 80, step=1)
    with c2:
        ui_s = st.number_input("硫分 Std (%)", value=float(default_s), step=0.01)
        ui_y = st.number_input("胶质层 Y (mm)", value=float(parsed_data['Y值']) if parsed_data['Y值'] else 15.0, step=0.5)
    with c3:
        ui_mt = st.number_input("水分 Mt (%)", value=float(default_mt), step=0.1)
        ui_csr = st.number_input("强度 CSR (%)", value=int(default_csr), step=1)

with col_out:
    st.subheader("🎯 期货仓单折算成本输出")
    
    is_freight_valid = False
    try:
        if freight_input.strip() != "":
            ui_freight = float(freight_input)
            is_freight_valid = True
    except ValueError:
        pass

    check_passed = True
    if not user_text.strip(): st.warning("⚠️ 请先在左侧输入【现货竞拍或报价文本】"); check_passed = False
    if location == "请选择...": st.warning("⚠️ 请在左侧侧边栏选择【指定交割仓库地点】"); check_passed = False
    if not is_freight_valid: st.warning("⚠️ 请在左侧侧边栏填入【至最近交割库的运费】"); check_passed = False
    if input_type == "请选择...": st.warning("⚠️ 请核对并选择【煤种类型】"); check_passed = False
    if input_type == "原煤" and (input_rec is None or input_rec <= 0): st.warning("⚠️ 煤种为原煤，请输入【原煤回收率】"); check_passed = False
    if input_price <= 0: st.warning("⚠️ 请输入或核对有效的【现货价格】"); check_passed = False

    if check_passed:
        if input_type == "原煤":
            base_washed_price = (input_price / (input_rec / 100.0)) + 50
            st.info(f"🏭 **步骤1（原煤洗选折算）**：原煤价 {input_price} 元/吨 $\div$ 回收率 {input_rec}% + 50 = 精煤 {base_washed_price:.2f} 元/吨")
        else:
            base_washed_price = input_price
            st.info(f"💰 **步骤1（煤种确认）**：精煤口径基准价为 {base_washed_price:.2f} 元/吨")

        weight_multiplier = 1.0
        if ui_mt > 8.0:
            weight_multiplier = (1 - 0.08) / (1 - ui_mt / 100.0)
            adjusted_price = base_washed_price * weight_multiplier
            st.info(f"💧 **步骤2（水分扣重）**：Mt={ui_mt}% > 8.0%，扣重折合后现货价 {adjusted_price:.2f} 元/吨")
        else:
            adjusted_price = base_washed_price
            st.info(f"💧 **步骤2（水分确认）**：Mt={ui_mt}% ≤ 8.0%，不扣重")

        details = []
        total_premium_discount = 0
        is_deliverable = True

        if ui_a > 11.0: details.append(f"❌ 灰分 Ad={ui_a}% > 11.0%：**不可交割！**"); is_deliverable = False
        elif ui_a > 10.5: total_premium_discount -= 30; details.append(f"📉 灰分 Ad={ui_a}%：**扣价 30 元/吨**")
        elif ui_a > 10.0: details.append(f"✨ 灰分 Ad={ui_a}%：无质量升贴水")
        else: total_premium_discount += 30; details.append(f"📈 灰分 Ad={ui_a}% ≤ 10.0%：**升价 30 元/吨**")

        if ui_s > 1.60: details.append(f"❌ 硫分 Std={ui_s}% > 1.60%：**不可交割！**"); is_deliverable = False
        elif ui_s > 1.30:
            penalty = (ui_s - 1.30) * 100 * 5
            total_premium_discount -= penalty
            details.append(f"📉 硫分 Std={ui_s}%：共**扣价 {penalty:.1f} 元/吨**")
        elif ui_s >= 0.70:
            bonus = (1.30 - ui_s) * 100 * 2.5
            total_premium_discount += bonus
            details.append(f"📈 硫分 Std={ui_s}%：共**升价 {bonus:.1f} 元/吨**")
        else:
            bonus = (1.30 - 0.70) * 100 * 2.5
            total_premium_discount += bonus
            details.append(f"📈 硫分 Std={ui_s}% < 0.70%：按边界计最大**升价 {bonus:.1f} 元/吨**")

        if default_v > 28.0 or default_v < 16.0: details.append(f"❌ 挥发分 Vdaf={default_v}%：**不可交割！**"); is_deliverable = False
        elif default_v > 26.0: total_premium_discount -= 50; details.append(f"📉 挥发分 Vdaf={default_v}%：**扣价 50 元/吨**")
        else: details.append(f"✨ 挥发分 Vdaf={default_v}%：无质量升贴水")

        if ui_csr < 60: details.append(f"❌ CSR 强度={ui_csr}%：**不可交割品！**"); is_deliverable = False
        elif ui_csr >= 65: total_premium_discount += 80; details.append(f"📈 CSR 强度={ui_csr}%：**升价 80 元/吨**")
        else: details.append(f"✨ CSR 强度={ui_csr}%：无质量升贴水")

        if ui_g < 75: details.append(f"⚠️ 警告：G值={ui_g} < 75 入库门槛！")
        if ui_y < 10.0: details.append(f"⚠️ 警告：胶质层 Y={ui_y}mm < 10mm 交割门槛！")

        final_cost = adjusted_price - total_premium_discount + ui_freight + region_premium + port_handling_fee

        st.markdown("#### 📑 交割品质与规则匹配明细：")
        for d in details:
            if "❌" in d: st.error(d)
            elif "📉" in d or "⚠️" in d: st.warning(d)
            else: st.write(d)

        st.write("---")
        if not is_deliverable:
            st.error("🚨 终审判定：该现货品质含有超标项，【无法注册】为大商所标准仓单！")
        else:
            st.metric(label="📊 预估折合大商所标准期货仓单成本", value=f"{round(final_cost)} 元/吨")
            if len(real_missing_for_warning) > 0:
                missing_str = "、".join(real_missing_for_warning)
                st.warning(f"⚠️ 【指标缺失】未检测到：{missing_str}。本次仅为预估测算，无法判定是否可交割。")
            else:
                st.success("✅ 【指标完整】所有核心指标均已就位，结果具备参考价值！")
    else:
        st.info("💡 请在左侧完成所有标记了 (必填/必选) 的交易项，系统将实时为您呈现精准的仓单成本。")
