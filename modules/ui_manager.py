import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
from modules.data_loader import save_portfolio, save_allocation_settings
from modules.market_service import search_yahoo_ticker, fetch_single_price

# ===========================
# 輔助函式與 CSS
# ===========================


def check_is_outdated(last_update_str):
    if not last_update_str or last_update_str == "N/A":
        return True
    try:
        last_update_dt = datetime.strptime(last_update_str, "%Y-%m-%d %H:%M")
        return datetime.now() - last_update_dt > timedelta(days=1)
    except:
        return True


def inject_custom_css():
    st.markdown(
        """
    <style>
    .fab-container { position: fixed; bottom: 40px; right: 40px; z-index: 9999; }
    .fab-container button {
        background-color: #FF4B4B; color: white; border-radius: 50%;
        width: 60px; height: 60px; font-size: 24px;
        box-shadow: 2px 2px 10px rgba(0,0,0,0.3); border: none; transition: transform 0.2s;
    }
    .fab-container button:hover { transform: scale(1.1); background-color: #FF2B2B; }
    .highlight-box { background-color: #f0f2f6; padding: 15px; border-radius: 10px; margin-bottom: 10px; }
    </style>
    """,
        unsafe_allow_html=True,
    )


# ===========================
# 邏輯核心：再平衡計算
# ===========================
def calculate_base_suggestions(df_market_data, total_val, new_fund):
    """計算系統建議的原始分配"""
    if not df_market_data.empty:
        current_alloc = df_market_data.groupby("Type")["Market_Value"].sum()
    else:
        current_alloc = pd.Series(dtype=float)

    targets = st.session_state.allocation_targets
    all_types = list(targets.keys())

    final_total_val = total_val + new_fund
    suggestions = []

    for cat in all_types:
        target_pct = targets.get(cat, 0.0) / 100.0
        current_val = current_alloc.get(cat, 0.0)
        ideal_val = final_total_val * target_pct
        gap = ideal_val - current_val
        suggestions.append({"Type": cat, "Gap": gap if gap > 0 else 0})

    df_sug = pd.DataFrame(suggestions)
    total_gap = df_sug["Gap"].sum()

    if total_gap > new_fund and total_gap > 0:
        df_sug["Suggested"] = df_sug.apply(
            lambda x: (x["Gap"] / total_gap * new_fund), axis=1
        )
    else:
        remaining = new_fund - total_gap
        df_sug["Suggested"] = df_sug.apply(
            lambda x: x["Gap"] + (remaining * (targets.get(x["Type"], 0) / 100)), axis=1
        )

    return df_sug.set_index("Type")["Suggested"].to_dict()


# ===========================
# 彈窗與操作邏輯
# ===========================


@st.dialog("⚙️ 資產管理與交易")
def asset_action_dialog(index, asset):
    # (維持原樣，為節省篇幅省略內容，請保留您原本的程式碼)
    st.caption(f"管理：**{asset['Ticker']}**")
    tab_buy, tab_sell, tab_edit, tab_del = st.tabs(
        ["➕ 加倉", "➖ 減倉", "✏️ 修正", "🗑️ 刪除"]
    )

    with tab_buy:
        c1, c2 = st.columns(2)
        add_qty = c1.number_input("數量", 0.0, 1.0, 0.1, key=f"bq_{index}")
        add_price = c2.number_input(
            f"單價 ({asset['Currency']})",
            0.0,
            float(asset["Avg_Cost"]),
            key=f"bp_{index}",
        )
        if st.button("確認加倉", key=f"btn_buy_{index}", type="primary"):
            old_cost = asset["Quantity"] * asset["Avg_Cost"]
            new_qty = asset["Quantity"] + add_qty
            asset["Avg_Cost"] = (
                (old_cost + (add_qty * add_price)) / new_qty if new_qty else 0
            )
            asset["Quantity"] = new_qty
            save_portfolio(st.session_state.portfolio)
            st.session_state["force_refresh_market_data"] = True
            st.success("成功")
            st.rerun()

    with tab_sell:
        sell_qty = st.number_input(
            "賣出數量", 0.0, float(asset["Quantity"]), 0.0, key=f"sq_{index}"
        )
        if st.button("確認減倉", key=f"btn_sell_{index}", type="primary"):
            asset["Quantity"] -= sell_qty
            save_portfolio(st.session_state.portfolio)
            st.session_state["force_refresh_market_data"] = True
            st.success("成功")
            st.rerun()

    with tab_edit:
        c1, c2 = st.columns(2)
        fq = c1.number_input(
            "修正數量", value=float(asset["Quantity"]), key=f"fq_{index}"
        )
        fc = c2.number_input(
            "修正成本", value=float(asset["Avg_Cost"]), key=f"fc_{index}"
        )
        if st.button("保存", key=f"btn_fix_{index}"):
            asset["Quantity"] = fq
            asset["Avg_Cost"] = fc
            save_portfolio(st.session_state.portfolio)
            st.session_state["force_refresh_market_data"] = True
            st.rerun()

    with tab_del:
        if st.button("❌ 確認刪除", key=f"btn_del_{index}", type="primary"):
            st.session_state.portfolio.pop(index)
            save_portfolio(st.session_state.portfolio)
            st.session_state["force_refresh_market_data"] = True
            st.rerun()


@st.dialog("➕ 新增資產")
def add_asset_dialog():
    st.caption("搜尋代號 (如: TSLA, 2330)")
    c_s, c_r = st.columns([2, 3])
    q = c_s.text_input("搜尋", placeholder="輸入代號...")
    sel = c_r.selectbox("結果", search_yahoo_ticker(q) if q else [])
    st.markdown("---")
    c1, c2 = st.columns(2)
    auto_t = sel.split(" | ")[0] if sel else ""
    with c1:
        ticker = st.text_input("代號", value=auto_t).upper()
        atype = st.selectbox("類別", ["美股", "台股", "虛擬貨幣", "稀有金屬"])
    with c2:
        qty = st.number_input("數量", 0.0, 1.0)
        curr = st.selectbox("幣別", ["USD", "TWD"], index=1 if ".TW" in ticker else 0)
        cost = st.number_input("成本", 0.0, 100.0)

    if st.button("確認新增", type="primary", use_container_width=True):
        if ticker:
            st.session_state.portfolio.append(
                {
                    "Type": atype,
                    "Ticker": ticker,
                    "Quantity": qty,
                    "Avg_Cost": cost,
                    "Currency": curr,
                    "Manual_Price": 0.0,
                    "Last_Update": "N/A",
                }
            )
            save_portfolio(st.session_state.portfolio)
            st.session_state["force_refresh_market_data"] = True
            st.success(f"已新增 {ticker}")
            st.rerun()


# ===========================
# 1. 優化後的投資配置設定
# ===========================
def render_allocation_section():
    st.subheader("🎯 投資配置目標設定")
    current_types = set([p["Type"] for p in st.session_state.portfolio])
    all_types = list(current_types.union({"美股", "台股", "虛擬貨幣", "稀有金屬"}))
    new_targets = {}
    total_pct = 0.0

    cols = st.columns(4)
    for i, cat in enumerate(all_types):
        col = cols[i % 4]
        cur_val = st.session_state.allocation_targets.get(cat, 0.0)
        val = col.number_input(
            f"{cat} (%)", 0.0, 100.0, float(cur_val), step=5.0, key=f"alloc_{cat}"
        )
        new_targets[cat] = val
        total_pct += val

    st.divider()

    # --- 進度條與數值顯示 ---
    c_bar, c_info = st.columns([4, 1])
    with c_bar:
        # 超過 100% 用紅色，否則用預設藍色
        bar_color = "red" if total_pct > 100 else "blue"
        # Streamlit progress bar color 只能透過 theme 設定，這裡用 value 限制視覺
        st.progress(min(total_pct / 100, 1.0))

    with c_info:
        if total_pct > 100:
            st.markdown(f"🚫 :red[**{total_pct:.1f}%**]")
        elif total_pct == 100:
            st.markdown(f"✅ :green[**{total_pct:.1f}%**]")
        else:
            st.markdown(f"⚠️ **{total_pct:.1f}%**")

    # 儲存按鈕邏輯
    if total_pct > 100:
        st.error("總配置比例超過 100%，請調整後再儲存。")
        st.button("💾 儲存配置設定", disabled=True)
    else:
        if st.button("💾 儲存配置設定"):
            st.session_state.allocation_targets = new_targets
            save_allocation_settings(new_targets)
            st.success("設定已儲存")


# ===========================
# 3. 資金投入試算與執行 (Smart Deployment)
# ===========================
def render_calculator_section(df_market_data, c_symbol, total_val):
    st.subheader("💰 資金投入與部署")

    # 初始化 Session State
    if "draft_actions" not in st.session_state:
        st.session_state.draft_actions = []

    # --- Step 1: 試算與規劃 ---
    with st.expander(
        "1️⃣ 規劃資金分配 (Step 1)", expanded=not bool(st.session_state.draft_actions)
    ):
        col_in1, col_in2 = st.columns([1, 2])
        new_fund = col_in1.number_input(
            f"預計投入金額 ({c_symbol})",
            min_value=0.0,
            value=10000.0,
            step=1000.0,
            key="calc_fund_input",
        )

        # 初始化建議
        if (
            "calc_base_suggestions" not in st.session_state
            or new_fund != st.session_state.get("last_calc_fund", 0)
        ):
            base_sug = calculate_base_suggestions(df_market_data, total_val, new_fund)
            st.session_state.calc_base_suggestions = base_sug
            st.session_state.calc_manual_adjust = base_sug.copy()
            st.session_state.last_calc_fund = new_fund

        current_plan = st.session_state.calc_manual_adjust

        c_adjust, c_charts = st.columns([1, 1.2])

        with c_adjust:
            st.markdown("#### 🛠️ 調整預算")
            if st.button("↺ 重置建議"):
                reset_data = st.session_state.calc_base_suggestions.copy()
                st.session_state.calc_manual_adjust = reset_data
                # Clear the widget keys so they can be recreated with new values
                for cat in reset_data.keys():
                    key = f"man_adj_{cat}"
                    if key in st.session_state:
                        del st.session_state[key]
                st.rerun()

            total_manual = 0
            for cat in current_plan.keys():
                key = f"man_adj_{cat}"
                default_val = float(current_plan[cat])
                new_amt = st.number_input(
                    f"{cat}", 0.0, value=default_val, step=1000.0, key=key
                )
                current_plan[cat] = new_amt
                total_manual += new_amt

            diff = total_manual - new_fund
            if abs(diff) > 1:
                st.caption(f"差額: {c_symbol}{diff:+,.0f}")
            else:
                st.success(f"已分配: {c_symbol}{total_manual:,.0f}")

        with c_charts:
            labels = list(current_plan.keys())
            vals = list(current_plan.values())
            # 圖 1: 本次分配
            fig1 = go.Figure(
                data=[go.Pie(labels=labels, values=vals, hole=0.4, title="本次配置")]
            )
            fig1.update_layout(
                margin=dict(t=30, b=0, l=0, r=0), height=180, showlegend=False
            )
            st.plotly_chart(fig1, use_container_width=True)

            # 圖 2: 預期總資產
            if not df_market_data.empty:
                cur_vals = (
                    df_market_data.groupby("Type")["Market_Value"].sum().to_dict()
                )
            else:
                cur_vals = {}
            final_vals = {
                cat: cur_vals.get(cat, 0) + current_plan.get(cat, 0)
                for cat in set(list(cur_vals.keys()) + labels)
            }
            fig2 = go.Figure(
                data=[
                    go.Pie(
                        labels=list(final_vals.keys()),
                        values=list(final_vals.values()),
                        hole=0.4,
                        title="預期總覽",
                    )
                ]
            )
            fig2.update_layout(
                margin=dict(t=30, b=0, l=0, r=0), height=180, showlegend=True
            )
            st.plotly_chart(fig2, use_container_width=True)

    st.divider()

    # --- Step 2: 建立部署清單 ---
    st.markdown("### 2️⃣ 建立交易清單 (Step 2)")
    st.caption("請根據上方的預算，將資金分配到具體的資產上。")

    # 選擇要操作的類別 (只顯示有預算的)
    active_cats = [c for c, v in current_plan.items() if v > 0]
    if not active_cats:
        st.info("請先在上方規劃預算。")
    else:
        sel_cat = st.selectbox("選擇要配置的類別", active_cats)
        budget = current_plan.get(sel_cat, 0)

        # 計算該類別已規劃多少
        planned_in_cat = sum(
            [d["Total"] for d in st.session_state.draft_actions if d["Type"] == sel_cat]
        )
        remaining = budget - planned_in_cat

        st.markdown(
            f"**{sel_cat}** 預算: `{c_symbol}{budget:,.0f}` | 已規劃: `{c_symbol}{planned_in_cat:,.0f}` | 剩餘: :blue[**{c_symbol}{remaining:,.0f}**]"
        )

        # 操作區塊
        with st.container(border=True):
            col_act1, col_act2, col_act3, col_act4 = st.columns([1.5, 1, 1, 1])

            # 選擇資產 (現有 or 新增)
            existing_assets = [
                p["Ticker"] for p in st.session_state.portfolio if p["Type"] == sel_cat
            ]
            asset_opt = col_act1.selectbox(
                "選擇資產", ["➕ 新增資產..."] + existing_assets, key="deploy_asset_sel"
            )

            target_ticker = ""
            if asset_opt == "➕ 新增資產...":
                target_ticker = col_act1.text_input(
                    "輸入新代號", placeholder="如 AAPL", key="deploy_new_ticker"
                ).upper()
            else:
                target_ticker = asset_opt

            # 輸入交易細節
            # 預設單價 (若是現有資產，抓一下成本當參考)
            ref_price = 100.0
            if asset_opt != "➕ 新增資產...":
                ref_item = next(
                    (p for p in st.session_state.portfolio if p["Ticker"] == asset_opt),
                    None,
                )
                if ref_item:
                    ref_price = float(ref_item["Avg_Cost"])

            d_price = col_act2.number_input(
                "單價", 0.0, value=ref_price, key="deploy_price"
            )
            d_qty = col_act3.number_input("數量", 0.0, value=1.0, key="deploy_qty")

            d_total = d_price * d_qty
            col_act4.markdown(f"總額: **{d_total:,.0f}**")

            if col_act4.button("加入清單", type="primary", disabled=d_total <= 0):
                if not target_ticker:
                    st.error("請輸入代號")
                else:
                    st.session_state.draft_actions.append(
                        {
                            "Type": sel_cat,
                            "Ticker": target_ticker,
                            "Price": d_price,
                            "Qty": d_qty,
                            "Total": d_total,
                            "Is_New": asset_opt == "➕ 新增資產...",
                        }
                    )
                    st.success(f"已加入 {target_ticker}")
                    st.rerun()

    # --- Step 3: 總結與送出 ---
    if st.session_state.draft_actions:
        st.divider()
        st.markdown("### 3️⃣ 確認並執行 (Step 3)")

        # 顯示清單表格
        draft_df = pd.DataFrame(st.session_state.draft_actions)
        st.dataframe(draft_df, use_container_width=True)

        total_planned = draft_df["Total"].sum()
        st.markdown(f"#### 總計畫投入金額: :green[{c_symbol}{total_planned:,.0f}]")

        c_sub1, c_sub2 = st.columns([1, 4])
        if c_sub1.button("🗑️ 清空清單"):
            st.session_state.draft_actions = []
            st.rerun()

        if c_sub2.button("🚀 確認送出 (寫入投資組合)", type="primary"):
            # 執行寫入邏輯
            for action in st.session_state.draft_actions:
                ticker = action["Ticker"]
                # 檢查是否已存在
                existing_idx = next(
                    (
                        i
                        for i, p in enumerate(st.session_state.portfolio)
                        if p["Ticker"] == ticker
                    ),
                    -1,
                )

                if existing_idx >= 0:
                    # 更新現有
                    item = st.session_state.portfolio[existing_idx]
                    old_cost = item["Quantity"] * item["Avg_Cost"]
                    new_qty = item["Quantity"] + action["Qty"]
                    new_avg = (old_cost + action["Total"]) / new_qty if new_qty else 0
                    st.session_state.portfolio[existing_idx]["Quantity"] = new_qty
                    st.session_state.portfolio[existing_idx]["Avg_Cost"] = new_avg
                else:
                    # 新增
                    # 需猜測幣別 (簡單邏輯)
                    curr = "TWD" if ".TW" in ticker else "USD"
                    st.session_state.portfolio.append(
                        {
                            "Type": action["Type"],
                            "Ticker": ticker,
                            "Quantity": action["Qty"],
                            "Avg_Cost": action["Price"],
                            "Currency": curr,
                            "Manual_Price": 0.0,
                            "Last_Update": "N/A",
                        }
                    )

            save_portfolio(st.session_state.portfolio)
            st.session_state["force_refresh_market_data"] = True
            st.session_state.draft_actions = []  # 清空
            st.success("交易已成功執行！請至資產清單查看。")
            st.balloons()
            # 這裡可以選擇是否 rerun，或讓使用者自己切換頁面

    else:
        st.info("尚未加入任何交易計畫。")


# ===========================
# 主入口
# ===========================
def render_asset_list_section(df_market_data, c_symbol):
    # (維持原樣，請保留原程式碼)
    st.subheader("📋 資產清單管理")
    if not st.session_state.portfolio:
        st.info("目前無資產。")
        return
    # ... (略) ...
    # 這裡請將上一版 render_asset_list_section 的內容完整貼上
    # 為節省篇幅，假設此處已有完整程式碼
    pass


# 重新補上 render_asset_list_section 的核心邏輯以免出錯 (簡化版，請用您手上的完整版)
def render_asset_list_section(df_market_data, c_symbol):
    st.subheader("📋 資產清單管理")
    col_search, col_filter, col_sort = st.columns([2, 1.5, 1.5])
    search_txt = col_search.text_input(
        "🔍 搜尋資產", placeholder="輸入代號或類別...", label_visibility="collapsed"
    )
    all_cats = (
        ["所有類別"] + list(set([p["Type"] for p in st.session_state.portfolio]))
        if st.session_state.portfolio
        else []
    )
    filter_cat = col_filter.selectbox(
        "篩選類別", all_cats, label_visibility="collapsed"
    )
    sort_opts = ["預設 (加入順序)", "市值 (高→低)", "成本 (高→低)", "更新時間 (新→舊)"]
    sort_by = col_sort.selectbox("排序方式", sort_opts, label_visibility="collapsed")
    st.divider()

    df_raw = pd.DataFrame(st.session_state.portfolio)
    if df_raw.empty:
        st.info("目前無資產。")
        return
    df_raw["Original_Index"] = df_raw.index

    if not df_market_data.empty:
        # Select only columns that exist in df_market_data
        merge_cols = ["Ticker", "Market_Value"]
        if "Current_Price" in df_market_data.columns:
            merge_cols.append("Current_Price")
        if "Last_Update" in df_market_data.columns:
            merge_cols.append("Last_Update")
        
        df_merged = pd.merge(
            df_raw, df_market_data[merge_cols], on="Ticker", how="left"
        )
        df_merged["Market_Value"] = df_merged["Market_Value"].fillna(0)
        
        # Add missing columns if they weren't in the merge
        if "Current_Price" not in df_merged.columns:
            df_merged["Current_Price"] = 0
        else:
            df_merged["Current_Price"] = df_merged["Current_Price"].fillna(0)
        
        if "Last_Update" not in df_merged.columns:
            df_merged["Last_Update"] = "N/A"
        else:
            df_merged["Last_Update"] = df_merged["Last_Update"].fillna("N/A")
    else:
        df_merged = df_raw
        df_merged["Market_Value"] = 0
        df_merged["Current_Price"] = 0
        df_merged["Last_Update"] = "N/A"

    if filter_cat != "所有類別":
        df_merged = df_merged[df_merged["Type"] == filter_cat]
    if search_txt:
        df_merged = df_merged[df_merged["Ticker"].str.contains(search_txt.upper())]

    if "市值" in sort_by:
        df_merged = df_merged.sort_values(by="Market_Value", ascending=False)

    # Header row
    h1, h2, h3, h4, h5, h6 = st.columns([1.2, 0.8, 1, 1.2, 0.6, 0.8])
    h1.caption("**代號**")
    h2.caption("**數量**")
    h3.caption("**成本**")
    h4.caption("**現價 & 更新時間**")
    h5.caption("**同步**")
    h6.caption("**操作**")
    st.divider()

    # 簡易渲染
    for _, row in df_merged.iterrows():
        idx = row["Original_Index"]
        item = st.session_state.portfolio[idx]
        
        # Safely get Last_Update - try from merged data first, then from original item
        if "Last_Update" in row and pd.notna(row["Last_Update"]) and row["Last_Update"] != "N/A":
            last_update = row["Last_Update"]
        else:
            last_update = item.get("Last_Update", "N/A")
        
        # Safely get Current_Price
        if "Current_Price" in row and pd.notna(row["Current_Price"]):
            current_price = row["Current_Price"]
        else:
            current_price = 0
        
        # Check if outdated
        is_outdated = check_is_outdated(last_update)
        update_color = "#FF8C00" if is_outdated else "#28a745"
        
        with st.container():
            c1, c2, c3, c4, c5, c6 = st.columns([1.2, 0.8, 1, 1.2, 0.6, 0.8])
            c1.markdown(f"**{item['Ticker']}**")
            c1.caption(f"{item['Type']}")
            c2.write(f"{item['Quantity']}")
            c3.write(f"{item['Avg_Cost']}")
            
            # Display current price and last update
            with c4:
                if current_price > 0:
                    st.markdown(f"**{c_symbol}{current_price:,.2f}**")
                else:
                    st.markdown("_N/A_")
                st.markdown(
                    f"<span style='color:{update_color}; font-size:11px'>🕒 {last_update}</span>", 
                    unsafe_allow_html=True
                )
            
            # Sync button to fetch individual price
            if c5.button("🔄", key=f"sync_{idx}", help="同步最新價格"):
                from modules.market_service import fetch_single_price
                from modules.data_loader import save_portfolio
                from datetime import datetime
                
                with st.spinner(f"正在更新 {item['Ticker']} 價格..."):
                    success, price, error = fetch_single_price(item['Ticker'])
                    if success:
                        st.session_state.portfolio[idx]["Manual_Price"] = price
                        st.session_state.portfolio[idx]["Last_Update"] = datetime.now().strftime("%Y-%m-%d %H:%M")
                        save_portfolio(st.session_state.portfolio)
                        # Force refresh market data
                        st.session_state["force_refresh_market_data"] = True
                        st.success(f"✅ {item['Ticker']} 價格已更新: {price:.2f}")
                        st.rerun()
                    else:
                        st.error(f"❌ 更新失敗: {error}")
            
            if c6.button("⚙️", key=f"m_{idx}"):
                asset_action_dialog(idx, item)
        st.divider()


def render_manager(df_market_data, c_symbol, total_val):
    inject_custom_css()
    sub_tab1, sub_tab2, sub_tab3 = st.tabs(
        ["📝 資產清單管理", "💰 資金投入與部署", "🎯 配置目標設定"]
    )

    with sub_tab1:
        render_asset_list_section(df_market_data, c_symbol)
    with sub_tab2:
        render_calculator_section(df_market_data, c_symbol, total_val)
    with sub_tab3:
        render_allocation_section()

    st.markdown('<div class="fab-container">', unsafe_allow_html=True)
    if st.button("➕", key="fab_add"):
        add_asset_dialog()
    st.markdown("</div>", unsafe_allow_html=True)
