import streamlit as st
from modules.data_loader import save_allocation_settings

def render_settings():
    st.subheader("🎯 投資配置目標設定")
    
    current_types = set([p['Type'] for p in st.session_state.portfolio])
    default_types = {"美股", "台股", "虛擬貨幣", "稀有金屬"}
    all_types = list(current_types.union(default_types))
    
    new_targets = {}
    total_pct = 0.0
    
    cols = st.columns(4)
    for i, cat in enumerate(all_types):
        col = cols[i % 4]
        cur_val = st.session_state.allocation_targets.get(cat, 0.0)
        val = col.number_input(f"{cat} (%)", 0.0, 100.0, float(cur_val), step=5.0)
        new_targets[cat] = val
        total_pct += val
        
    st.progress(min(total_pct/100, 1.0))
    if abs(total_pct - 100) > 0.1:
        st.warning(f"目前總和: {total_pct:.1f}% (目標應為 100%)")
    else:
        st.success("配置完美 (100%)")
        
    if st.button("💾 儲存設定", type="primary"):
        st.session_state.allocation_targets = new_targets
        save_allocation_settings(new_targets)
        st.success("設定已儲存")