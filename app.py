import streamlit as st
import re
import pandas as pd

st.set_page_config(page_title="大商所焦煤期货仓单成本计算器 (多标段批量版)", layout="wide")

# ==========================================
# 核心文本解析器
# ==========================================
def parse_text_advanced(text):
    data = {'类型': '精煤/焦煤', '灰分': None, '硫分': None, '挥发分': None, 'G值': None, 'Y值': None, '水分': None, 'CSR': None, '价格': 0, '回收率': 90.0}
    if not text.strip():
        return data
        
    if "原煤" in text: 
        data['类型'] = "原煤"
    
    # 斩断分号后面的上期历史干扰
    clean_text = text.split('；')[0].split(';')[0]
    
    a_match = re.search(r'(?:[Aa][d]?|内灰)[:≤<=]*([\d\.]+)', clean_text)
    s_match = re.search(r'[Ss][t]?[,d]?[:≤<=]*([\d\.]+)', clean_text)
    v_match = re.search(r'[Vv][d]?[:≤<=]*([\d\.\-]+)', clean_text)
    g_match = re.search(r'[Gg][:≥>=]*(\d+)', clean_text)
    y_match = re.search(r'[Yy][:≥>=]*([\d\.]+)', clean_text)
    mt_match = re.search(r'[Mm][Tt][:≤<=]*([\d\.]+)', clean_text)
    csr_match = re.search(r'[Cc][Ss][Rr][:≥>=]*(\d+)', clean_text)
    rec_match = re.search(r'回收(\d+)', clean_text)
    
    price_final = 0
    if "流拍" in clean_text:
        start_price = re.search(r'起拍价[:]*(\d+)', clean_text)
        if start_price: price_final = int(start_price.group(1))
    else:
        deal_range = re.search(r'以(\d+)-(\d+)元/吨', clean_text)
        if deal_range:
            price_final = int(deal_range.group(2)) 
        else:
            single_deal = re.search(r'以[:]*(\d+)元/吨', clean_text)
            if single_deal:
                price_final = int(single_deal.group(1))
            else:
                start_price = re.search(r'起拍价[:]*(\d+)', clean_text)
                if start_price: price_final = int(start_price.group(1))

    if a_match: data['灰分'] = float(a_match.group(1))
    if s_match: data['硫分'] = float(s_match.group(1))
    if v_match: data['挥发分'] = v_match.group(1)
    if g_match: data['G值'] = int(g_match.group(1))
    if y_match: data['Y值'] = float(y_match.group(1))
    if mt_match: data['水分'] = float(mt_match.group(1))
    if csr_match: data['CSR'] = int(csr_match.group(1))
    if rec_match: data['回收率'] = float(rec_match.group(1))
    data['价格'] = price_final
    return data

# ==========================================
# 页面主标题
# ==========================================
st.title("🧱 大商所焦煤期货仓单成本计算器 (智能批量版)")
st.markdown("""
本版本支持**全局/独立物流双模式切换**。默认启用侧边栏全局物流联动，单独也可自行选择，无指标默认最低。
""")

# ==========================================
# 侧边栏配置：全局共享模式
# ==========================================
st.sidebar.header("🛠️ 交易所全局规则配置")

logistic_mode = st.sidebar.radio(
    "物流参数填报模式",
    ["🌐 多个标的来自同地区 (侧边栏统一填写)", "📍 每个标的来自不同地区 (在每个框里独立填)"]
)

# 全局变量初始化
global_region_premium = None
global_port_handling_fee = None
global_freight = 0.0

if "侧边栏统一填写" in logistic_mode:
    location = st.sidebar.selectbox(
        "1. 全局交割仓库地点 **：red[必选])**", 
        ["请选择...", "山西 (基准库)", "港口/其他地区 (唐山/青岛/日照/连云港/天津等)"]
    )
    if location == "山西 (基准库)":
        global_region_premium, global_port_handling_fee = 0, 0
    elif location == "港口/其他地区 (唐山/青岛/日照/连云港/天津等)":
        global_region_premium, global_port_handling_fee = 170, 35 
        
    freight_input = st.sidebar.text_input("2. 全局至最近交割库的运费 (元/吨)**：red[必选])** *无运费请输入0", value="0")
    try: global_freight = float(freight_input) if freight_input.strip() else 0.0
    except: pass

st.sidebar.subheader("📊 质量标准基准线（无指标即最差可交档位）")
st.sidebar.markdown("- **灰分 Ad**: 基准 10.5% ; 【≤10.0% 升价30; 10.5%-11.0% 扣价30】")
st.sidebar.markdown("- **硫分 Std**: 基准 1.3% ; 【(1.3-1.6]% 每升高0.01%扣5元; [0.7-1.3]% 每降低0.01%升价2.5元; <0.7% 不额外升水，按0.7%档位封顶升价】")
st.sidebar.markdown("- **挥发分 Vdaf**: 基准 [16.0%, 26.0%] ; 【(26.0%, 28.0%] 扣价50】")
st.sidebar.markdown("- **GR.I (黏结指数)**: 基准 入库≥75，出库>65，无升贴水")
st.sidebar.markdown("- **Y (胶质层最大厚度)**: 基准 10mm；【>10mm，无升贴水】")
st.sidebar.markdown("- **CSR (反应后强度)**: 基准 [60%, 65%) ; ≥65% 升价80")
st.sidebar.markdown("- **水分 Mt**: 基准 8.0%, 超过8.0%进行扣重折算: `(1 - 0.08) / (1 - 水分实测值)`")

# ==========================================
# 动态增加/减少面板控制器
# ==========================================
if 'num_coals' not in st.session_state:
    st.session_state.num_coals = 1  

col_btn1, col_btn2, _ = st.columns([1, 1, 5])
with col_btn1:
    if st.button("➕ 增加一个现货煤种"):
        st.session_state.num_coals += 1
with col_btn2:
    if st.button("➖ 减少最后一个煤种") and st.session_state.num_coals > 1:
        st.session_state.num_coals -= 1

all_valid_costs = []
st.write("---")

# ==========================================
# 循环循环生成标的面板
# ==========================================
for i in range(st.session_state.num_coals):
    st.subheader(f"📋 现货标的 #{i+1}")
    
    col_in, col_out = st.columns([1, 1])
    
    with col_in:
        user_text = st.text_area(f"粘贴标的 #{i+1} 的竞拍文本：", value="", key=f"text_{i}", placeholder="粘贴或录入对应文本...", height=110)
        parsed_data = parse_text_advanced(user_text)
        
        # 针对每个标的的地区与物流处理
        if "在每个框里独立填" in logistic_mode:
            c_l1, c_l2 = st.columns(2)
            with c_l1:
                local_loc = st.selectbox(f"标的 #{i+1} 交割仓库地点**：red[别忘填])**", ["请选择...", "山西 (基准库)", "港口/其他地区 (唐山/青岛/日照/连云港/天津等)"], key=f"loc_{i}")
                if local_loc == "山西 (基准库)": region_premium, port_handling_fee = 0, 0
                elif local_loc == "港口/其他地区 (唐山/青岛/日照/连云港/天津等)": region_premium, port_handling_fee = 170, 35
                else: region_premium, port_handling_fee = None, None
            with c_l2:
                local_fr_input = st.text_input(f"标的 #{i+1} 独立运费 (元/吨)**：red[别忘填])**", value="0", key=f"fr_{i}")
                try: ui_freight = float(local_fr_input) if local_fr_input.strip() else 0.0
                except: ui_freight = None
        else:
            # 联动全局变量
            region_premium = global_region_premium
            port_handling_fee = global_port_handling_fee
            ui_freight = global_freight
            
        # 价格与原煤洗选率确认
        c_p1, c_p2 = st.columns(2)
        with c_p1:
            input_price = st.number_input(f"标的 #{i+1} 确认现货价", value=int(parsed_data['价格']), key=f"price_{i}")
            input_type = st.selectbox(f"标的 #{i+1} 确认类型**：red[别忘填])**", ["请选择...", "精煤/焦煤", "原煤"], index=2 if parsed_data['类型']=="原煤" else 0, key=f"type_{i}")
        with c_p2:
            if input_type == "原煤":
                # 核心改进：若文本有提取到回收率则用提取的，其余均一律强制赋予默认值 90.0，同时保留框可以随意手改
                default_rec_val = parsed_data['回收率'] if parsed_data['回收率'] is not None else 90.0
                input_rec = st.number_input(f"标的 #{i+1} 原煤回收率(%)", value=float(default_rec_val), key=f"rec_{i}", step=1.0)
            else:
                input_rec = 100.0

        # 核心5指标风控提取
        missing_list = []
        ui_a = parsed_data['灰分'] if parsed_data['灰分'] is not None else 11.0
        if parsed_data['灰分'] is None: missing_list.append("灰分(Ad)")
        
        ui_s = parsed_data['硫分'] if parsed_data['硫分'] is not None else 1.60
        if parsed_data['硫分'] is None: missing_list.append("硫分(Std)")
        
        if parsed_data['挥发分'] is None:
            missing_list.append("挥发分(Vdaf)")
            ui_v = 28.0
        else:
            try: ui_v = float(max(re.findall(r'[\d\.]+', str(parsed_data['挥发分'])))) if '-' in str(parsed_data['挥发分']) else float(parsed_data['挥发分'])
            except: ui_v = 28.0
            
        ui_mt = parsed_data['水分'] if parsed_data['水分'] is not None else 8.0
        if parsed_data['水分'] is None: missing_list.append("全水分(Mt)")
        
        ui_csr = parsed_data['CSR'] if parsed_data['CSR'] is not None else 60
        if parsed_data['CSR'] is None: missing_list.append("强度(CSR)")
        
        ui_g = int(parsed_data['G值']) if parsed_data['G值'] else 80
        ui_y = float(parsed_data['Y值']) if parsed_data['Y值'] else 15.0

    with col_out:
        st.markdown("**🔄 该标的单项交割演算折算**")
        
        # 规则验证控制单元
        check_passed = True
        if not user_text.strip():
            st.info("💡 面板等待输入现货文本...")
            check_passed = False
        elif region_premium is None or ui_freight is None:
            st.warning("⚠️ 物流配置缺省！请检查侧边栏（或当前框顶部）的【交割地点与运费】")
            check_passed = False
        elif input_type == "请选择...":
            st.warning("⚠️ 请先核对并选定该标的的【精煤/原煤类型】")
            check_passed = False
        elif input_price <= 0:
            st.warning("⚠️ 请手动输入或检查校准提取出的【现货确认价】")
            check_passed = False
            
        if check_passed:
            # 执行交割转换计算
            if input_type == "原煤":
                base_price = (input_price / (input_rec / 100.0)) + 60
                st.write(f"- 🏭 原煤洗选折算: {input_price} $\div$ {input_rec}% + 60 = 精煤 {base_price:.1f} 元/吨")
            else:
                base_price = input_price
                
            if ui_mt > 8.0:
                adjusted_price = base_price * ((1 - 0.08) / (1 - ui_mt / 100.0))
                st.write(f"- 💧 水分扣重生效: 折合现货价放大至 {adjusted_price:.1f} 元/吨")
            else:
                adjusted_price = base_price
                
            # 升贴水档位计算
            details, total_discount, deliverable = [], 0, True
            
            if ui_a > 11.0: details.append(f"❌ 灰分 Ad={ui_a}%: 超出11%不可交割"); deliverable = False
            elif ui_a > 10.5: total_discount -= 30
            elif ui_a <= 10.0: total_discount += 30
                
            if ui_s > 1.60: details.append(f"❌ 硫分 Std={ui_s}%: 超出1.6%不可交割"); deliverable = False
            elif ui_s > 1.30: total_discount -= (ui_s - 1.30) * 100 * 5
            elif ui_s >= 0.70: total_discount += (1.30 - ui_s) * 100 * 2.5
            else: total_discount += (1.30 - 0.70) * 100 * 2.5
                
            if ui_v > 28.0 or ui_v < 16.0: details.append(f"❌ 挥发分 Vdaf={ui_v}%: 越过[16-28]红线"); deliverable = False
            elif ui_v > 26.0: total_discount -= 50
                
            if ui_csr < 60: details.append(f"❌ CSR强度={ui_csr}%: 低于60不可交割"); deliverable = False
            elif ui_csr >= 65: total_discount += 80
                
            if ui_g < 75: details.append(f"⚠️ 警告：G值={ui_g} 未达入库红线75")
            if ui_y < 10.0: details.append(f"⚠️ 警告：胶质层 Y={ui_y}mm 未达入库红线10")
            
            for d in details:
                if "❌" in d: st.error(d)
                else: st.warning(d)
                
            if deliverable:
                final_cost = adjusted_price - total_discount + ui_freight + region_premium + port_handling_fee
                all_valid_costs.append(final_cost)
                st.metric(label=f"🎯 标的 #{i+1} 预估期货仓单成本", value=f"{round(final_cost)} 元/吨")
                if len(missing_list) > 0:
                    st.warning(f"⚠️ 有指标确实缺失，价格预估: { '、'.join(missing_list) }，已套用最差档扣价。")
                else:
                    st.success("✅ 所有指标核对完整，具有参考价值。")
            else:
                st.error("🚨 终审结论：包含核心超标指标，属于无法交割品。")
                
    st.write("---")

# ==========================================
# 📊 底部全局数据汇总看板
# ==========================================
if len(all_valid_costs) > 0:
    st.header("📊 批量竞拍多标的决策看板")
    avg_cost = sum(all_valid_costs) / len(all_valid_costs)
    min_cost = min(all_valid_costs)
    
    col_m1, col_m2, col_m3 = st.columns(3)
    with col_m1:
        st.metric(label="仓单平均价 (Average)", value=f"{round(avg_cost)} 元/吨")
    with col_m2:
        st.metric(label="最低仓单价 (Min)", value=f"{round(min_cost)} 元/吨")
    with col_m3:
        st.metric(label="🔢 参与统计的有效标的总数", value=f"{len(all_valid_costs)} 个")
