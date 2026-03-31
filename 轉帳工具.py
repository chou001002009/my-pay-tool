import streamlit as st
import re
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# 1. 網頁基本設定
st.set_page_config(page_title="Q哥轉帳助手 Pro", page_icon="💸", layout="wide")

# --- 2. 數據清洗工具 ---
def clean_num(v):
    if pd.isna(v): return ""
    try:
        s = str(v).replace("'", "").replace(",", "").replace("-", "").strip()
        return str(int(float(s)))
    except:
        return re.sub(r'\D', '', str(v))

def clean_txt(v):
    return str(v).replace(" ", "").strip()

# --- 3. 解析函數 ---
def parse_data(trans_text, people_text, buffer_val):
    t_list = []
    total_needed = 0
    for line in trans_text.split('\n'):
        line = line.strip()
        if not line: continue
        match = re.search(r'([\d-]+)\s*轉\s*(\d+)', line)
        if match:
            amt = int(match.group(2))
            t_list.append({'info': match.group(1), 'amount': amt})
            total_needed += amt
    
    p_list = []
    for line in people_text.split('\n'):
        line = line.strip()
        if not line: continue
        match = re.search(r'(.+?)\s*(?:有|,|，)\s*(\d+)', line)
        if match:
            p_list.append({'name': match.group(1).strip(), 'bal': int(match.group(2)), 'limit': int(match.group(2)) - buffer_val, 'tasks': [], 'out': 0})
    return t_list, p_list, total_needed

# --- 4. 核心功能：讀取微調後的結果並同步 ---
def sync_all_checked_to_cloud():
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(worksheet="Sheet1", ttl=0)
        
        if df.empty:
            st.warning("雲端無資料。")
            return

        up_cnt = 0
        df_updated = df.copy()

        # 掃描分配結果
        for p_idx, p in enumerate(st.session_state.current_results):
            for t_idx, t in enumerate(p['tasks']):
                # 取得每個輸入框的唯一 Key
                chk_key = f"chk_{p['name']}_{p_idx}_{t_idx}"
                info_key = f"edit_info_{p['name']}_{p_idx}_{t_idx}"
                amt_key = f"edit_amt_{p['name']}_{p_idx}_{t_idx}"

                # 如果該項目被勾選，則使用微調後的數值進行同步
                if st.session_state.get(chk_key, False):
                    # 抓取畫面上的微調值（若無微調則為原始值）
                    final_info = st.session_state.get(info_key, t['info'])
                    final_amt = st.session_state.get(amt_key, t['amount'])
                    
                    target_name = clean_txt(p['name'])
                    target_info = clean_num(t['info']) # 使用原始 info 去雲端找紀錄
                    target_amt = clean_num(t['amount']) # 使用原始金額去雲端找紀錄

                    mask = (
                        (df_updated['執行人'].astype(str).apply(clean_txt) == target_name) & 
                        (df_updated['帳號'].apply(clean_num) == target_info) & 
                        (df_updated['金額'].apply(clean_num) == target_amt) & 
                        (df_updated['狀態'].astype(str).str.strip() == "未完成")
                    )
                    
                    if mask.any():
                        idx = df_updated[mask].index[-1]
                        df_updated.at[idx, '狀態'] = "完成"
                        # 同步時同時更新雲端上的帳號與金額（反映微調後的結果）
                        df_updated.at[idx, '帳號'] = f"'{final_info}"
                        df_updated.at[idx, '金額'] = final_amt
                        up_cnt += 1
        
        if up_cnt > 0:
            conn.update(worksheet="Sheet1", data=df_updated)
            st.success(f"🎯 成功同步 {up_cnt} 筆任務！")
            st.rerun()
        else:
            st.info("沒有偵測到新勾選的項目。")
            
    except Exception as e:
        st.error(f"同步失敗：{e}")

# --- 5. 初始化 ---
if 'current_results' not in st.session_state: st.session_state.current_results = None
if 'un_results' not in st.session_state: st.session_state.un_results = []
if 'total_amt' not in st.session_state: st.session_state.total_amt = 0

# --- 6. 側邊欄 ---
with st.sidebar:
    st.header("⚙️ 系統設定")
    buffer_val = st.slider("每人留底金額", 2000, 10000, 6500, step=500)
    st.divider()
    st.subheader("👥 常用人員")
    all_names = ["大孟", "柏盛", "阿廷", "安妮", "宜峰", "育銘", "鴻運", "我"]
    selected = st.multiselect("參與人員：", options=all_names, default=all_names)
    if st.button("📝 生成名單"):
        st.session_state["input_p"] = "\n".join([f"{n} , 0" for n in selected])
        st.rerun()

# --- 7. 主要介面 ---
st.title("💸 轉帳自動化分配工具")
tab1, tab2 = st.tabs(["🚀 分配任務", "📜 雲端紀錄"])

with tab1:
    col1, col2 = st.columns(2)
    with col1: raw_t = st.text_area("📋 1. 轉帳清單", height=150, key="raw_t_in")
    with col2: raw_p = st.text_area("👥 2. 人員餘額", height=150, key="input_p")

    c1, c2, c3 = st.columns([2, 2, 1])
    with c1:
        if st.button("🚀 執行分配並同步雲端", use_container_width=True):
            t_list, p_list, total_amt = parse_data(raw_t, raw_p, buffer_val)
            if t_list and p_list:
                t_list.sort(key=lambda x: x['amount']) # 小額優先
                unassigned = []
                for t in t_list:
                    remaining_amt = t['amount']
                    p_list.sort(key=lambda x: x['limit'], reverse=True)
                    if p_list[0]['limit'] >= remaining_amt:
                        p_list[0]['tasks'].append({'info': t['info'], 'amount': remaining_amt})
                        p_list[0]['limit'] -= remaining_amt
                        p_list[0]['out'] += remaining_amt
                        remaining_amt = 0
                    else:
                        if t['amount'] > 65000:
                            splits = 0
                            for p in p_list:
                                if p['limit'] > 0 and remaining_amt > 0 and splits < 5:
                                    potential = min(remaining_amt, p['limit'])
                                    take = (potential // 100 * 100) if (potential < remaining_amt and splits < 4) else potential
                                    if take > 0:
                                        p['tasks'].append({'info': f"{t['info']} (拆)", 'amount': int(take)})
                                        p['limit'] -= take
                                        p['out'] += take
                                        remaining_amt -= take
                                        splits += 1
                        if remaining_amt > 0:
                            unassigned.append({'info': t['info'], 'amount': remaining_amt})
                st.session_state.current_results = p_list
                st.session_state.un_results = unassigned
                st.session_state.total_amt = total_amt
                # 同步初始化雲端資料... (略，維持原邏輯)
                try:
                    conn = st.connection("gsheets", type=GSheetsConnection)
                    now = datetime.now().strftime("%Y-%m-%d %H:%M")
                    new_recs = []
                    for p in p_list:
                        for tk in p['tasks']:
                            new_recs.append({"時間": now, "執行人": p['name'], "帳號": f"'{tk['info']}", "金額": tk['amount'], "狀態": "未完成"})
                    if new_recs:
                        ex_df = conn.read(worksheet="Sheet1", ttl=0)
                        final_df = pd.concat([ex_df, pd.DataFrame(new_recs)], ignore_index=True) if not ex_df.empty else pd.DataFrame(new_recs)
                        conn.update(worksheet="Sheet1", data=final_df)
                        st.success("✅ 分配完成！")
                except: st.error("雲端連線失敗")
            else: st.error("格式錯誤")

    with c2:
        if st.button("🎯 同步勾選狀態至雲端", use_container_width=True, type="primary"):
            if st.session_state.current_results:
                sync_all_checked_to_cloud()

    with c3:
        if st.button("🗑️ 清空", use_container_width=True):
            st.session_state.current_results = None; st.rerun()

    # --- 顯示與手動微調區 ---
    if st.session_state.current_results:
        st.divider()
        for p_idx, p in enumerate(st.session_state.current_results):
            if p['tasks']:
                with st.container(border=True):
                    st.success(f"### {p['name']} (總計: {p['out']:,})")
                    for t_idx, tk in enumerate(p['tasks']):
                        col_chk, col_info, col_amt = st.columns([1, 4, 3])
                        with col_chk:
                            st.checkbox("完成", key=f"chk_{p['name']}_{p_idx}_{t_idx}")
                        with col_info:
                            st.text_input("帳號", value=tk['info'], key=f"edit_info_{p['name']}_{p_idx}_{t_idx}", label_visibility="collapsed")
                        with col_amt:
                            st.number_input("金額", value=int(tk['amount']), step=100, key=f"edit_amt_{p['name']}_{p_idx}_{t_idx}", label_visibility="collapsed")

        if st.session_state.un_results:
            st.error(f"⚠️ 未分配總額：{sum(u['amount'] for u in st.session_state.un_results):,}")

with tab2:
    if st.button("🔄 刷新"): st.rerun()
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(worksheet="Sheet1", ttl=0)
        st.dataframe(df.iloc[::-1], use_container_width=True)
    except: st.info("無資料")
