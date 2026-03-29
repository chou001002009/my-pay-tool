import streamlit as st
import re
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# 1. 基本設定
st.set_page_config(page_title="轉帳助手 Pro", page_icon="💸", layout="wide")

# --- 2. 解析函數 ---
def parse_data(trans_text, people_text, buffer_val):
    t_list = []
    for line in trans_text.split('\n'):
        line = line.strip()
        if not line: continue
        match = re.search(r'([\d-]+)\s*轉\s*(\d+)', line)
        if match: t_list.append({'info': match.group(1), 'amount': int(match.group(2))})
    
    p_list = []
    for line in people_text.split('\n'):
        line = line.strip()
        if not line: continue
        match = re.search(r'(.+?)\s*(?:有|,|，)\s*(\d+)', line)
        if match:
            p_list.append({'name': match.group(1).strip(), 'bal': int(match.group(2)), 'limit': int(match.group(2)) - buffer_val, 'tasks': [], 'out': 0})
    return t_list, p_list

# --- 3. 核心功能：地表最強比對同步 ---
def sync_all_checked_to_cloud():
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(worksheet="Sheet1", ttl=0)
        
        if df.empty:
            st.warning("雲端無資料。")
            return

        # [核心優化] 只留數字的比對工具，並先處理小數點問題
        def to_clean_num_str(v):
            if pd.isna(v): return ""
            # 先轉成浮點數再轉整數，徹底去掉小數點後面的 .0
            try:
                num = int(float(str(v).replace("'", "").replace(",", "").strip()))
                return str(num)
            except:
                return re.sub(r'\D', '', str(v))

        def clean_text(v): return str(v).replace(" ", "").strip()

        updated_count = 0
        df_updated = df.copy()

        # 遍歷目前顯示的人員任務
        for p in st.session_state.current_results:
            for t in p['tasks']:
                t_key = f"chk_{p['name']}_{t['info']}_{t['amount']}"
                
                # 如果這格被勾選了
                if st.session_state.get(t_key, False):
                    t_name = clean_text(p['name'])
                    t_info = to_clean_num_str(t['info'])
                    t_amt = to_clean_num_str(t['amount'])

                    # 暴力比對條件
                    mask = (
                        (df_updated['執行人'].astype(str).apply(clean_text) == t_name) & 
                        (df_updated['帳號'].apply(to_clean_num_str) == t_info) & 
                        (df_updated['金額'].apply(to_clean_num_str) == t_amt) & 
                        (df_updated['狀態'].astype(str).str.strip() == "未完成")
                    )
                    
                    if mask.any():
                        target_idx = df_updated[mask].index[-1]
                        df_updated.at[target_idx, '狀態'] = "完成"
                        updated_count += 1
        
        if updated_count > 0:
            conn.update(worksheet="Sheet1", data=df_updated)
            st.success(f"🎯 成功同步！已將 {updated_count} 筆任務更新為『完成』！")
            st.rerun()
        else:
            st.info("⚠️ 勾選的項目在雲端可能已經是『完成』狀態，或是找不到對應資料。")
            
    except Exception as e:
        st.error(f"同步過程發生錯誤：{e}")

# 初始化
if 'current_results' not in st.session_state: st.session_state.current_results = None

# --- 4. 側邊欄 ---
with st.sidebar:
    st.header("⚙️ 設定")
    buffer_val = st.slider("每人留底金額", 5000, 10000, 6500, step=500)
    all_names = ["大孟", "柏盛", "阿廷", "安妮", "宜峰", "育銘", "鴻運"]
    selected = st.multiselect("參與人員：", options=all_names, default=all_names)
    if st.button("📝 生成名單範本"):
        st.session_state["input_p"] = "\n".join([f"{n} , 0" for n in selected])
        st.rerun()

# --- 5. 主要介面 ---
st.title("💸 轉帳自動化分配工具")
tab1, tab2 = st.tabs(["🚀 開始分配", "📜 雲端紀錄"])

with tab1:
    col1, col2 = st.columns(2)
    with col1: raw_trans = st.text_area("📋 1. 貼上轉帳清單", height=150, key="raw_trans_in")
    with col2: raw_ppl = st.text_area("👥 2. 輸入人員餘額", height=150, key="raw_ppl_in")

    c1, c2, c3 = st.columns([2, 2, 1])
    with c1:
        if st.button("🚀 執行分配並同步雲端", use_container_width=True):
            t_list, p_list = parse_data(raw_trans, raw_ppl, buffer_val)
            if t_list and p_list:
                t_list.sort(key=lambda x: x['amount'], reverse=True)
                for t in t_list:
                    p_list.sort(key=lambda x: x['limit'], reverse=True)
                    if p_list[0]['limit'] >= t['amount']:
                        p_list[0]['tasks'].append(t)
                        p_list[0]['limit'] -= t['amount']
                        p_list[0]['out'] += t['amount']
                st.session_state.current_results = p_list
                try:
                    conn = st.connection("gsheets", type=GSheetsConnection)
                    new_records = []
                    now = datetime.now().strftime("%Y-%m-%d %H:%M")
                    for p in p_list:
                        for task in p['tasks']:
                            new_records.append({"時間": now, "執行人": p['name'], "帳號": f"'{task['info']}", "金額": task['amount'], "狀態": "未完成"})
                    if new_records:
                        new_df = pd.DataFrame(new_records)
                        try:
                            ex_df = conn.read(worksheet="Sheet1", ttl=0)
                            final_df = pd.concat([ex_df, new_df], ignore_index=True) if not ex_df.empty else new_df
                        except: final_df = new_df
                        conn.update(worksheet="Sheet1", data=final_df)
                        st.success("✅ 任務已同步雲端！")
                except Exception as e: st.error(f"寫入雲端失敗：{e}")
            else: st.error("格式有誤")

    with c2:
        if st.button("🎯 同步勾選狀態至雲端", use_container_width=True, type="primary"):
            if st.session_state.current_results:
                sync_all_checked_to_cloud()
            else: st.warning("請先執行分配。")

    with c3:
        if st.button("🗑️ 清空", use_container_width=True):
            st.session_state.current_results = None
            st.rerun()

    if st.session_state.current_results:
        st.divider()
        for p in st.session_state.current_results:
            with st.container(border=True):
                st.success(f"### {p['name']} (總計: {p['out']:,})")
                for i, t in enumerate(p['tasks']):
                    t_key = f"chk_{p['name']}_{t['info']}_{t['amount']}"
                    st.checkbox(f"金額 {t['amount']:,} ({t['info']})", key=t_key)

with tab2:
    if st.button("🔄 刷新顯示"): st.rerun()
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(worksheet="Sheet1", ttl=0)
        st.dataframe(df.iloc[::-1], use_container_width=True)
    except: st.info("尚無資料。")
