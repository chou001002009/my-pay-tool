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

# --- 3. 核心功能：暴力比對並同步 ---
def sync_all_checked_to_cloud():
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        # 強制刷新的關鍵：ttl=0
        df = conn.read(worksheet="Sheet1", ttl=0)
        
        if df.empty:
            st.warning("雲端目前的表單是空的，請先按左邊的『執行分配』上傳任務。")
            return

        # 定義「純化」函數：只留文字和數字，去掉所有符號
        def clean_val(v): return re.sub(r'[^a-zA-Z0-9\u4e00-\u9fa5]', '', str(v)).strip()
        def only_num(v): return re.sub(r'\D', '', str(v))

        updated_count = 0
        df_updated = df.copy()

        # 掃描目前的勾選狀態
        for p in st.session_state.current_results:
            for t in p['tasks']:
                t_key = f"chk_{p['name']}_{t['info']}_{t['amount']}"
                
                # 如果手機上這格是勾選的
                if st.session_state.get(t_key, False):
                    t_name = clean_val(p['name'])
                    t_info = only_num(t['info'])
                    t_amt = only_num(t['amount'])

                    # 在雲端 DF 裡找匹配行
                    mask = (
                        (df_updated['執行人'].apply(clean_val) == t_name) & 
                        (df_updated['帳號'].apply(only_num) == t_info) & 
                        (df_updated['金額'].apply(only_num) == t_amt) & 
                        (df_updated['狀態'].str.strip() == "未完成")
                    )
                    
                    if mask.any():
                        target_idx = df_updated[mask].index[-1]
                        df_updated.at[target_idx, '狀態'] = "完成"
                        updated_count += 1
        
        if updated_count > 0:
            conn.update(worksheet="Sheet1", data=df_updated)
            st.success(f"🎯 成功！已將 {updated_count} 筆任務更新為『完成』！")
            # 成功後自動刷新畫面
            st.rerun()
        else:
            st.info("⚠️ 沒有偵測到『新勾選』且『雲端狀態為未完成』的項目。")
            with st.expander("🔍 點我看為什麼對不準 (偵錯資訊)"):
                st.write("手機抓到的最後一筆：", p['name'], t['info'], t['amount'])
                st.write("雲端目前的內容：", df[['執行人', '帳號', '金額', '狀態']].head())
            
    except Exception as e:
        st.error(f"同步過程發生錯誤：{e}")

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

    # 功能按鈕
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
                # 寫入雲端
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
                        st.success("✅ 任務已同步！請在下方打勾後按『同步狀態』。")
                except Exception as e: st.error(f"寫入雲端失敗：{e}")
            else: st.error("輸入格式有誤")

    with c2:
        # [重點] 這裡使用了紅色醒目按鈕
        if st.button("🎯 同步勾選狀態至雲端", use_container_width=True, type="primary"):
            if st.session_state.current_results:
                sync_all_checked_to_cloud()
            else: st.warning("請先執行分配並出現卡片。")

    with c3:
        if st.button("🗑️ 清空", use_container_width=True):
            st.session_state.current_results = None
            st.rerun()

    # --- 顯示卡片 ---
    if st.session_state.current_results:
        st.divider()
        for p in st.session_state.current_results:
            with st.container(border=True):
                st.success(f"### {p['name']} (今日總計: {p['out']:,})")
                for i, t in enumerate(p['tasks']):
                    t_key = f"chk_{p['name']}_{t['info']}_{t['amount']}"
                    # 這裡是關鍵：打勾的狀態會被存在 session_state 裡
                    st.checkbox(f"金額 {t['amount']:,} ({t['info']})", key=t_key)

with tab2:
    if st.button("🔄 刷新顯示"): st.rerun()
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(worksheet="Sheet1", ttl=0)
        st.dataframe(df.iloc[::-1], use_container_width=True)
    except: st.info("尚無資料。")
