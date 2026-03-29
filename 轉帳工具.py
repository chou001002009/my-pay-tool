import streamlit as st
import re
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# 1. 基本設定
st.set_page_config(page_title="轉帳助手 Pro", page_icon="💸", layout="wide")

# --- 2. 解析函數 (強化容錯) ---
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

# --- 3. 雲端同步更新函數 (純數字比對版) ---
def update_gsheet_status(task_info, task_amt, person_name):
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(worksheet="Sheet1", ttl=0)
        
        if df.empty:
            st.warning("雲端無資料。")
            return

        # 把所有符號都刪掉，只留數字的比對工具
        def to_pure_num(val):
            return re.sub(r'\D', '', str(val))

        target_name = person_name.strip()
        target_info = to_pure_num(task_info)
        target_amt = to_pure_num(task_amt)

        # 建立比對條件
        mask = (
            (df['執行人'].astype(str).str.strip() == target_name) & 
            (df['帳號'].apply(to_pure_num) == target_info) & 
            (df['金額'].apply(to_pure_num) == target_amt) & 
            (df['狀態'].astype(str).str.strip() == "未完成")
        )
        
        if mask.any():
            last_index = df[mask].index[-1]
            df.at[last_index, '狀態'] = "完成"
            conn.update(worksheet="Sheet1", data=df)
            st.toast(f"✅ 同步成功：{person_name} 已結清")
        else:
            st.toast("ℹ️ 找不到匹配的『未完成』紀錄，請確認雲端是否有該筆資料。")
            
    except Exception as e:
        st.error(f"同步失敗：{e}")

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
    with col1: raw_trans = st.text_area("📋 1. 貼上轉帳清單", height=150, key="input_t")
    with col2: raw_ppl = st.text_area("👥 2. 輸入人員餘額", height=150, key="input_p")

    c1, c2 = st.columns([3, 1])
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
                
                # --- 初始化雲端寫入 (強制設為文字格式) ---
                try:
                    conn = st.connection("gsheets", type=GSheetsConnection)
                    new_records = []
                    now = datetime.now().strftime("%Y-%m-%d %H:%M")
                    for p in p_list:
                        for task in p['tasks']:
                            # 帳號前加一個單引號，強迫 Google 視為文字，保留開頭的 0
                            new_records.append({"時間": now, "執行人": p['name'], "帳號": f"'{task['info']}", "金額": task['amount'], "狀態": "未完成"})
                    
                    if new_records:
                        new_df = pd.DataFrame(new_records)
                        try:
                            existing_df = conn.read(worksheet="Sheet1", ttl=0)
                            if not existing_df.empty and '執行人' in existing_df.columns:
                                final_df = pd.concat([existing_df, new_df], ignore_index=True)
                            else: final_df = new_df
                        except: final_df = new_df
                        
                        conn.update(worksheet="Sheet1", data=final_df)
                        st.success("✅ 雲端同步完成！")
                except Exception as e: st.error(f"雲端寫入失敗：{e}")
            else: st.error("格式有誤")

    with c2:
        if st.button("🗑️ 清空今日", use_container_width=True):
            st.session_state.current_results = None
            st.rerun()

    if st.session_state.current_results:
        for p in st.session_state.current_results:
            with st.container(border=True):
                st.success(f"### {p['name']} (今日總計: {p['out']:,})")
                msg = f"{p['name']}今日任務：\n" + "\n".join([f"{i+1}. {t['info']} 轉 {t['amount']:,}" for i, t in enumerate(p['tasks'])])
                st.code(msg, language="text")
                for i, t in enumerate(p['tasks']):
                    t_key = f"chk_{p['name']}_{t['info']}_{t['amount']}"
                    if st.checkbox(f"金額 {t['amount']:,} ({t['info']})", key=t_key):
                        if f"done_{t_key}" not in st.session_state:
                            update_gsheet_status(t['info'], t['amount'], p['name'])
                            st.session_state[f"done_{t_key}"] = True

with tab2:
    if st.button("🔄 刷新雲端"): st.rerun()
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(worksheet="Sheet1", ttl=0)
        st.dataframe(df.iloc[::-1], use_container_width=True)
    except: st.info("尚無雲端資料。")
