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

# --- 4. 初始化 Session State ---
if 'current_results' not in st.session_state: st.session_state.current_results = None
if 'un_results' not in st.session_state: st.session_state.un_results = []
if 'total_amt' not in st.session_state: st.session_state.total_amt = 0

# --- 5. 側邊欄 ---
with st.sidebar:
    st.header("⚙️ 系統設定")
    buffer_val = st.slider("每人留底金額", 5000, 10000, 6500, step=500)
    st.divider()
    st.subheader("👥 常用人員勾選")
    all_names = ["大孟", "柏盛", "阿廷", "安妮", "宜峰", "育銘", "鴻運", "我"]
    selected = st.multiselect("參與人員：", options=all_names, default=all_names)
    if st.button("📝 生成所選人員名單"):
        st.session_state["input_p"] = "\n".join([f"{n} , 0" for n in selected])
        st.rerun()

# --- 6. 主要介面 ---
st.title("💸 轉帳自動化分配工具 (整數拆帳版)")
tab1, tab2 = st.tabs(["🚀 開始分配", "📜 雲端歷史紀錄"])

with tab1:
    col1, col2 = st.columns(2)
    with col1: raw_t = st.text_area("📋 1. 貼上轉帳清單", height=150, key="raw_t_in")
    with col2: raw_p = st.text_area("👥 2. 輸入人員餘額", height=150, key="input_p")

    c1, c2, c3 = st.columns([2, 2, 1])
    
    with c1:
        if st.button("🚀 執行分配並同步雲端", use_container_width=True):
            t_list, p_list, total_amt = parse_data(raw_t, raw_p, buffer_val)
            if t_list and p_list:
                # 策略：小額優先分配
                t_list.sort(key=lambda x: x['amount']) 
                unassigned = []

                for t in t_list:
                    remaining_amt = t['amount']
                    p_list.sort(key=lambda x: x['limit'], reverse=True)
                    
                    # A. 優先檢查：是否有人可以一對一全額吃下
                    if p_list[0]['limit'] >= remaining_amt:
                        p_list[0]['tasks'].append({'info': t['info'], 'amount': remaining_amt})
                        p_list[0]['limit'] -= remaining_amt
                        p_list[0]['out'] += remaining_amt
                        remaining_amt = 0
                    else:
                        # B. 沒人能單吃。偵測是否超過 65000 啟動拆帳
                        if t['amount'] > 65000:
                            splits = 0
                            for p in p_list:
                                if p['limit'] > 0 and remaining_amt > 0 and splits < 5:
                                    # 計算這個人「最大能拿多少」
                                    potential_take = min(remaining_amt, p['limit'])
                                    
                                    # --- 整數邏輯更新 ---
                                    # 如果這不是最後一個拆帳的人，就取百位整數
                                    if potential_take < remaining_amt and splits < 4:
                                        take = (potential_take // 100) * 100
                                    else:
