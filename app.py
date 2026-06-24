import streamlit as st
import re
import pandas as pd

st.set_page_config(page_title="大商所焦煤仓单山西竞拍批量计算器", layout="wide")

# ==========================================
# 📊 核心计算逻辑：纯山西标准仓单引擎
# ==========================================
def calculate_shanxi_cost(price, a, s, v, mt, csr):
    # 纯山西基准库：区域升贴水=0，港杂费=0
    total_discount = 0
    deliverable = True
    details = []
    
    # 1. 水分扣重折算
    if mt > 8.0:
        adjusted_price = price * ((1 - 0.08) / (1 - mt / 100.0))
        details.append(f"💧 水分 Mt={mt}% > 8% 触发扣重，折合现货底价放大至: {adjusted_price:.1f} 元/吨")
    else:
        adjusted_price = price
        details.append(f"💧 水分 Mt={mt}% ≤ 8% 正常不扣重")
        
    # 2. 灰分判定
    if a > 11.0:
        details.append(f"❌ 灰分 Ad={a}% > 11% 不可交割")
        deliverable = False
    elif a > 10.5:
        total_discount -= 30
        details.append("📉 灰分 Ad 在 (10.5%, 11.0%] 贴水 30 元/吨")
    elif a <= 10.0:
        total_discount += 30
        details.append("📈 灰分 Ad ≤ 10.0% 优质升水 30 元/吨")
        
    # 3. 硫分判定
    if s > 1.60:
        details.append(f"❌ 硫分 Std={s}% > 1.60% 不可交割")
        deliverable = False
    elif s > 1.30:
        penalty = (s - 1.30) * 100 * 5
        total_discount -= penalty
        details.append(f"📉 硫分 Std={s}% 超出基准，贴水 {penalty:.1f} 元/吨")
    elif s >= 0.70:
        bonus = (1.30 - s) * 100 * 2.5
        total_discount += bonus
        details.append(f"📈 硫分 Std={s}% 触发优质升水 {bonus:.1f} 元/吨")
    else:
        bonus = (1.30 - 0.70) * 100 * 2.5
        total_discount += bonus
        details.append(f"📈 硫分 Std={s}% 触发优质升水 {bonus:.1f} 元/吨")
        
    # 4. 挥发分判定
    if v > 28.0 or v < 16.0:
        details.append(f"❌ 挥发分 Vdaf={v}% 超出 [16-28] 交割红线，不可交割")
        deliverable = False
    elif v > 26.0:
        total_discount -= 50
        details.append("📉 挥发分 Vdaf 在 (26%, 28%] 贴水 50 元/吨")
        
    # 5. CSR 强度判定
    if csr < 60:
        details.append(f"❌ CSR 强度={csr}% < 60% 无法满足交割底线")
        deliverable = False
    elif csr >= 65:
        total_premium_discount = 80  # 升贴水总和加80
        total_discount += 80
        details.append("📈 CSR 强度 ≥ 65% 符合优质品升水 80 元/吨")

    # 最终山西仓单计算：调整后的现货价 - 质量升贴水
    final_cost = adjusted_price - total_discount
    return deliverable, final_cost, details

# ==========================================
# 🔍 智能多行解析引擎（强力升级精准聚焦算法）
# ==========================================
def parse_single_line_safely(line_text):
    # 初始化输出格式
    res = {'is_valid': True, 'reason': '', 'price': 0, 'a': None, 's': None, 'v': None, 'mt': None, 'csr': None, 'raw_text': line_text}
    
    if not line_text.strip() or len(line_text.strip()) < 15:
        res['is_valid'] = False
        return None
        
    # 1. 严格过滤原煤
    if "原煤" in line_text:
        res['is_valid'] = False
        res['reason'] = "🚫 属于原煤品种（已过滤，不参与精煤仓单测算）"
        return res

    # 2. 核心卡口：彻底隔离“上期”的所有数据
    main_part = line_text.split('；')[0].split(';')[0]

    # 3. 提取价格：严格的近邻关联算法，防止数量万吨和上期数字混淆
    price = 0
    # 场景1：全流拍，取本期的起拍价
    if "流拍" in main_part:
        p_match = re.search(r'起拍价[:\s]*(\d{3,4})', main_part)
        if p_match: price = int(p_match.group(1))
    else:
        # 场景2：成交，寻找以 XXXX-XXXX 元/吨成交的最高防守上限
        p_range = re.search(r'以[:\s]*(\d+)-(\d+)\s*元', main_part)
        if p_range:
            price = int(p_range.group(2))
        else:
            # 场景3：成交，寻找以 XXXX 元/吨单一成交
            p_single = re.search(r'以[:\s]*(\d+)\s*元', main_part)
            if p_single: price = int(p_single.group(1))
            else:
                # 场景4：没写成交词，兜底抓本期起拍价
                p_base = re.search(r'起拍价[:\s]*(\d{3,4})', main_part)
                if p_base: price = int(p_base.group(1))
                
    res['price'] = price

    # 4. 指标提取提取 (兼容 内灰、A、S、V、Mt、CSR)
    a_match = re.search(r'(?:[Aa][d]?|内灰)[:≤<=]*([\d\.]+)', main_part)
    s_match = re.search(r'[Ss][t]?[,d]?[:≤<=]*([\d\.]+)', main_part)
    v_match = re.search(r'[Vv][d]?[:≤<=]*([\d\.\-]+)', main_part)
    mt_match = re.search(r'[Mm][Tt][:≤<=]*([\d\.]+)', main_part)
    csr_match = re.search(r'[Cc][Ss][Rr][:≥>=]*(\d+)', main_part)
    
    # 补充：提取 G 和 Y 作为合规性辅助提示
    g_match = re.search(r'[Gg][:≥>=]*(\d+)', main_part)
    y_match = re.search(r'[Yy][:≥>=]*([\d\.]+)', main_part)

    # 赋值与最差替代品防守兜底
    missing_fields = []
    
    if a_match: res['a'] = float(a_match.group(1))
    else: res['a'] = 11.0; missing_fields.append("灰分(Ad)")
    
    if s_match: res['s'] = float(s_match.group(1))
    else: res['s'] = 1.60; missing_fields.append("硫分(Std)")
    
    if v_match:
        try: res['v'] = float(max(re.findall(r'[\d\.]+', str(v_match.group(1))))) if '-' in str(v_match.group(1)) else float(v_match.group(1))
        except: res['v'] = 28.0; missing_fields.append("挥发分(Vdaf)")
    else: res['v'] = 28.0; missing_fields.append("挥发分(Vdaf)")
        
    if mt_match: res['mt'] = float(mt_match.group(1))
    else: res['mt'] = 8.0  # 水分缺省按8%正常走
    
    if csr_match: res['csr'] = int(csr_match.group(1))
    else: res['csr'] = 60; missing_fields.append("强度(CSR)")
    
    res['g'] = int(g_match.group(1)) if g_match else 80
    res['y'] = float(y_match.group(1)) if y_match else 15.0
    res['missing'] = missing_fields
    
    return res

# ==========================================
# 🖥️ 网页前端渲染与交互逻辑
# ==========================================
st.title("🧱 大商所焦煤仓单山西竞拍批量计算器")
st.markdown("""
本系统已针对**山西区域指定交割库**剔除繁琐的跨区选项。
现在支持**一键多行粘贴**。你可以直接把从软件或微信复制的一整页包含多条精煤、原煤的文字直接倒进下方输入框。
""")

# 侧边栏精简为规则查阅面板
st.sidebar.header("📋 山西基准库交割风控基准")
st.sidebar.markdown("""
* **地点升贴水**: 0 元/吨 (山西全境固定为基准库)
* **港杂及物流费**: 0 元/吨 (由于在山西本地设库交割)
* **灰分红线**: $\le 11.0\%$ (超标直接熔断)
* **硫分红线**: $\le 1.60\%$ (超标直接熔断)
* **挥发分红线**: $16.0\% \sim 28.0\%$
* **CSR底线**: $\ge 60\%$
""")

st.subheader("📥 批量现货竞拍文本一键多行输入")
bulk_input = st.text_area(
    "请在此全选粘贴多行竞拍报价文本：", 
    value="", 
    placeholder="在此粘贴多行文本，一行放一个煤种的信息...",
    height=250
)

if bulk_input.strip():
    # 按照换行符切割文本进行处理
    raw_lines = bulk_input.split('\n')
    valid_warehouse_costs = []
    
    st.write("---")
    st.header("⚡ 逐行智能化交割推演结果：")
    
    item_idx = 1
    for raw_line in raw_lines:
        if not raw_line.strip() or len(raw_line.strip()) < 10:
            continue
            
        parsed = parse_single_line_safely(raw_line)
        if parsed is None:
            continue
            
        st.markdown(f"#### 🏷️ 标的 #{item_idx}")
        st.caption(f"**原始竞拍文本:** {raw_line}")
        
        if not parsed['is_valid']:
            st.info(parsed['reason'])
        elif parsed['price'] <= 0:
            st.warning("⚠️ 无法自动锁定该行的本期有效成交价/起拍价。请检查文本，或在下方手动补充：")
            manual_price = st.number_input(f"手动输入标的 #{item_idx} 现货价", value=0, key=f"manual_p_{item_idx}")
            if manual_price > 0:
                parsed['price'] = manual_price
                # 重新计算
                deliverable, final_cost, calc_details = calculate_shanxi_cost(parsed['price'], parsed['a'], parsed['s'], parsed['v'], parsed['mt'], parsed['csr'])
                if deliverable:
                    st.success(f"🎯 预估山西仓单成本: **{round(final_cost)} 元/吨**")
                    valid_warehouse_costs.append(final_cost)
        else:
            # 基础核心校验通过，调用山西计算引擎
            deliverable, final_cost, calc_details = calculate_shanxi_cost(
                parsed['price'], parsed['a'], parsed['s'], parsed['v'], parsed['mt'], parsed['csr']
            )
            
            col_res1, col_res2 = st.columns([4, 3])
            with col_res1:
                st.markdown(f"**⚙️ 抓取要素**: 现货确认价 **{parsed['price']}** 元/吨 | 灰分:{parsed['a']}% | 硫分:{parsed['s']}% | 挥发分:{parsed['v']}% | 水分:{parsed['mt']}% | CSR:{parsed['csr']}%")
                if parsed['g'] < 75: st.warning(f"⚠️ 警告：G值={parsed['g']} 低于75入库红线。")
                if parsed['y'] < 10.0: st.warning(f"⚠️ 警告：胶质层厚度 Y={parsed['y']}mm 低于10mm交割红线。")
                
                # 打印明细
                with st.expander("查看升贴水扣减细则"):
                    for detail in calc_details:
                        st.write(f"- {detail}")
            with col_res2:
                if deliverable:
                    st.metric(label="📊 标准期货仓单成本", value=f"{round(final_cost)} 元/吨")
                    if len(parsed['missing']) > 0:
                        st.warning(f"⚠️ 指标缺 { '、'.join(parsed['missing']) }，已启用最差档贴水。")
                    else:
                        st.success("✅ 指标完整，具参考价值。")
                    valid_warehouse_costs.append(final_cost)
                else:
                    st.error("🚨 终审结论：包含超标指标，属于无法交割品。")
                    
        st.write("---")
        item_idx += 1

    # ==========================================
    # 📊 全局宏观决策看板
    # ==========================================
    if len(valid_warehouse_costs) > 0:
        st.header("📊 本批次精煤竞拍全局决策看板")
        avg_total = sum(valid_warehouse_costs) / len(valid_warehouse_costs)
        min_total = min(valid_warehouse_costs)
        
        col_m1, col_m2, col_m3 = st.columns(3)
        with col_m1:
            st.metric(label="平均仓单成本", value=f"{round(avg_total)} 元/吨")
        with col_m2:
            st.metric(label="最低仓单成本", value=f"{round(min_total)} 元/吨", delta="最具套利价格边界", delta_color="inverse")
        with col_m3:
            st.metric(label="参与汇总的合格精煤总标的数", value=f"{len(valid_warehouse_costs)} 个")
else:
    st.info("💡 系统正处于待命状态。请直接把包含多行多标的的现货群聊竞拍文字复制粘贴到上方大框中，系统将一秒批量自动完成推演。")
