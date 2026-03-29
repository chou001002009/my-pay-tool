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

# --- 3. 核心功能：批次更新狀態至雲端 ---
def sync_all_checked_to_cloud():
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(worksheet="Sheet1", ttl=0)
        
        if df.empty:
            st.warning("雲端無資料可更新。")
            return

        def to_pure_num(val): return re.sub(r'\D', '', str(val))
        
        updated_count = 0
        # 掃描當前所有分配的人員與任務
        for p in st.session_state.current_results:
            for i, t in enumerate(p['tasks']):
                t_key = f"chk_{p['name']}_{t['info']}_{t['amount']}"
                # 如果這個 Checkbox 在介面上是被勾選的
                if st.session_state.get(t_key, False):
                    target_name = p['name'].strip()
                    target_info = to_pure_num(t['info'])
                    target_amt = to_pure_num(t['amount'])

                    # 尋找雲端中尚未完成的對應紀錄
                    mask = (
                        (df['執行人'].astype(str).str.strip() == target_name) & 
                        (df['帳號'].apply(to_pure_num) == target_info) & 
                        (df['金額'].apply(to_pure_num) == target_amt) & 
                        (df['狀態'].astype(str).str.strip() == "未完成")
                    )
                    
                    if mask.any():
                        last_index = df[mask].index[-1]
                        df.at[last_index, '狀態'] = "完成"
                        updated_count += 1
        
        if updated_count > 0:
            conn.update(worksheet="Sheet1", data=df)
            st.success(f"🎊 成功同步 {updated_count} 筆資料至雲端！")
        else:
            st.info("沒有偵測到新勾選的未完成項目。")
            
    except Exception as e:
        st.error(f"同步失敗：{e}")

# --- 4. 初始化 ---
if 'current_results' not in st.session_state: st.session_state.current_results = None

# --- 5. 側邊欄 ---
with st.sidebar:
    st.header("⚙️ 設定")
    buffer_val = st.slider("每人留底金額", 5000, 10000, 6500, step=500)
    all_names = ["大孟", "柏盛", "阿廷", "安妮", "宜峰", "育銘", "鴻運"]
    selected = st.multiselect("參與人員：", options=all_names, default=all_names)
    if st.button("📝 生成名單範本"):
        st.session_state["input_p"] = "\n".join([f"{n} , 0" for n in selected])
        st.rerun()

# --- 6. 主要介面 ---
st.title("💸 轉帳自動化分配工具")
tab1, tab2 = st.tabs(["🚀 開始分配", "📜 雲端紀錄"])

with tab1:
    col1, col2 = st.columns(2)
    with col1: raw_trans = st.text_area("📋 1. 貼上轉帳清單", height=150, key="input_t")
    with col2: raw_ppl = st.text_area("👥 2. 輸入人員餘額", height=150, key="input_p")

    # 分配按鈕區
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
                # 初始同步寫入
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
                            existing_df = conn.read(worksheet="Sheet1", ttl=0)
                            final_df = pd.concat([existing_df, new_df], ignore_index=True) if not existing_df.empty else new_df
                        except: final_df = new_df
                        conn.update(worksheet="Sheet1", data=final_df)
                        st.success("✅ 雲端任務已同步！")
                except Exception as e: st.error(f"寫入失敗：{e}")
            else: st.error("格式錯誤")

    with c2:
        # --- [新增] 手動同步按鈕 ---
        if st.button("🎯 同步勾選狀態至雲端", use_container_width=True, type="primary"):
            if st.session_state.current_results:
                sync_all_checked_to_cloud()
            else:
                st.warning("請先執行分配。")

    with c3:
        if st.button("🗑️ 清空今日", use_container_width=True):
            st.session_state.current_results = None
            st.rerun()

    # --- 顯示結果 ---
    if st.session_state.current_results:
        st.divider()
        for p in st.session_state.current_results:
