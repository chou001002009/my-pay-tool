import streamlit as st
import re
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# 1. 網頁基本設定
st.set_page_config(page_title="轉帳助手", page_icon="💸", layout="wide")

# --- 2. 強化版解析函數 (超強容錯) ---
def parse_data(trans_text, people_text, buffer_val):
    t_list = []
    # 支援「帳號 轉 金額」，忽略所有空格
    for line in trans_text.split('\n'):
        line = line.strip()
        if not line: continue
        match = re.search(r'([\d-]+)\s*轉\s*(\d+)', line)
        if match:
            t_list.append({'info': match.group(1), 'amount': int(match.group(2))})
    
    p_list = []
    # 支援「名字 有 金額」或「名字 , 100」或「名字，100」
    for line in people_text.split('\n'):
        line = line.strip()
        if not line: continue
        # [核心修正] 同時支援中文/英文逗號與「有」
        match = re.search(r'(.+?)\s*(?:有|,|，)\s*(\d+)', line)
        if match:
            name = match.group(1).strip()
            bal = int(match.group(2))
            p_list.append({
                'name': name, 'bal': bal, 'limit': bal - buffer_val, 'tasks': [], 'out': 0
            })
    return t_list, p_list

# --- 3. 初始化 Session ---
if 'history' not in st.session_state: st.session_state.history = []
if 'current_results' not in st.session_state: st.session_state.current_results = None

# --- 4. 側邊欄 ---
with st.sidebar:
    st.header("⚙️ 參數設定")
    buffer_val = st.slider("每人留底金額", 5000, 10000, 6500, step=500)
    st.divider()
    st.subheader("👥 常用人員選擇")
    all_names = ["大孟", "柏盛", "阿廷", "安妮", "宜峰", "育銘", "鴻運"]
    selected_names = st.multiselect("選擇本次人員：", options=all_names, default=all_names)
    if st.button("📝 生成人員清單"):
        if selected_names:
            st.session_state["input_p"] = "\n".join([f"{n} , 0" for n in selected_names])
            st.rerun()

# --- 5. 主要介面 ---
st.title("💸 轉帳自動化分配工具")
tab1, tab2 = st.tabs(["🚀 開始分配", "📜 雲端歷史紀錄"])

with tab1:
    col1, col2 = st.columns(2)
    with col1: raw_trans = st.text_area("📋 1. 貼上轉帳清單", height=200, key="input_t")
    with col2: raw_ppl = st.text_area("👥 2. 輸入人員餘額", height=200, key="input_p")

    c1, c2 = st.columns([3, 1])
    with c1:
        if st.button("🚀 執行智慧分配", use_container_width=True):
            t_list, p_list = parse_data(raw_trans, raw_ppl, buffer_val)
            if not t_list or not p_list:
                st.error("❌ 格式解析失敗！請確保：\n1. 清單包含『轉』\n2. 人員包含『,』或『有』")
            else:
                # 執行分配
                t_list.sort(key=lambda x: x['amount'], reverse=True)
                unassigned = []
                for t in t_list:
                    p_list.sort(key=lambda x: x['limit'], reverse=True)
                    if p_list[0]['limit'] >= t['amount']:
                        p_list[0]['tasks'].append(t)
                        p_list[0]['limit'] -= t['amount']
                        p_list[0]['out'] += t['amount']
                    else: unassigned.append(t)
                
                st.session_state.current_results = p_list
                st.session_state.un_results = unassigned
                
                # --- 雲端同步邏輯 ---
                try:
                    conn = st.connection("gsheets", type=GSheetsConnection)
                    new_records = []
                    now = datetime.now().strftime("%Y-%m-%d %H:%M")
                    for p in p_list:
                        for task in p['tasks']:
                            new_records.append({"時間": now, "執行人": p['name'], "帳號": task['info'], "金額": task['amount'], "結餘": p['bal'] - p['out']})
                    
                    if new_records:
                        new_df = pd.DataFrame(new_records)
                        # 嘗試讀取，如果 Sheet1 不存在會報錯
                        try:
                            existing_df = conn.read(worksheet="Sheet1")
                            final_df = pd.concat([existing_df, new_df], ignore_index=True)
                        except:
                            final_df = new_df
                        
                        conn.update(worksheet="Sheet1", data=final_df)
                        st.toast("✅ 雲端同步成功！")
                except Exception as e:
                    st.error(f"☁️ 雲端同步失敗：{str(e)}。請確認 Google 試算表的分頁名稱是否為『Sheet1』。")

    with c2:
        if st.button("🗑️ 清空今日", use_container_width=True):
            st.session_state.current_results = None
            st.rerun()

    if st.session_state.current_results:
        results = st.session_state.current_results
        for p in results:
            with st.container(border=True):
                cl, cr = st.columns([1, 2])
                with cl:
                    st.success(f"### {p['name']}")
                    st.write(f"預計結餘: `{p['bal']-p['out']:,}`")
                with cr:
                    msg = f"{p['name']}今日任務：\n" + "\n".join([f"{i+1}. {t['info']} 轉 {t['amount']:,}" for i, t in enumerate(p['tasks'])])
                    st.code(msg, language="text")
                    for i, t in enumerate(p['tasks']):
                        st.checkbox(f"金額 {t['amount']:,} ({t['info']})", key=f"c_{p['name']}_{i}")

with tab2:
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(worksheet="Sheet1")
        st.dataframe(df, use_container_width=True)
    except: st.info("目前雲端尚無資料。")
