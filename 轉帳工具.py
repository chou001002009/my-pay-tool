import streamlit as st
import re
import pandas as pd
from datetime import datetime

# 1. 網頁基本設定 (放在最前面)
st.set_page_config(page_title="轉帳分配助手", page_icon="💸", layout="wide")

# --- 定義解析函數 (放在前面，確保後面呼叫得到) ---
def parse_data(trans_text, people_text):
    trans_list = []
    for line in trans_text.split('\n'):
        if not line.strip(): continue
        match = re.search(r'([\d-]+)轉(\d+)', line.replace(" ", ""))
        if match:
            trans_list.append({'info': match.group(1), 'amount': int(match.group(2))})
    
    people_list = []
    for line in people_text.split('\n'):
        if not line.strip(): continue
        match = re.search(r'(\w+),\s*(\d+)', line)
        if match:
            bal = int(match.group(2))
            # 注意：這裡的 buffer_amt 是從側邊欄讀取的
            people_list.append({
                'name': match.group(1), 
                'bal': bal, 
                'limit': bal - st.session_state.get('buffer_val', 6500), 
                'tasks': [], 
                'out': 0
            })
    return trans_list, people_list

# --- 初始化 Session State (紀錄狀態用) ---
if 'history' not in st.session_state:
    st.session_state.history = []
if 'current_results' not in st.session_state:
    st.session_state.current_results = None
if 'unassigned_results' not in st.session_state:
    st.session_state.unassigned_results = []

st.title("💰 轉帳自動化分配工具")

# --- 側邊欄：參數設定 ---
with st.sidebar:
    st.header("⚙️ 參數設定")
    buffer_val = st.slider("每人留底金額", 5000, 10000, 6500, step=500, key='buffer_val')
    st.divider()
    if st.button("🗑️ 清空歷史紀錄"):
        st.session_state.history = []
        st.rerun()

# --- 主要分頁設計 ---
tab1, tab2 = st.tabs(["🚀 開始分配", "📜 歷史紀錄"])

with tab1:
    col1, col2 = st.columns(2)
    with col1:
        # 使用 key 讓 Streamlit 記住輸入內容
        raw_transfers = st.text_area("📋 1. 貼上轉帳清單", height=150, key="raw_trans")
    with col2:
        raw_people = st.text_area("👥 2. 輸入人員餘額", height=150, key="raw_ppl")

    # 分配按鈕邏輯
    if st.button("🚀 執行智慧分配", use_container_width=True):
        if raw_transfers and raw_people:
            trans_list, people_list = parse_data(raw_transfers, raw_people)
            
            if trans_list and people_list:
                # 執行智慧分配邏輯 (大額優先)
                trans_list.sort(key=lambda x: x['amount'], reverse=True)
                unassigned = []
                for t in trans_list:
                    people_list.sort(key=lambda x: x['limit'], reverse=True)
                    if people_list[0]['limit'] >= t['amount']:
                        people_list[0]['tasks'].append(t)
                        people_list
