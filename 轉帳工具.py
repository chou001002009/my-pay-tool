import streamlit as st
import re

# 頁面基本設定：讓介面在手機上自動填滿寬度
st.set_page_config(page_title="轉帳分配助手", layout="wide")
st.title("💰 轉帳自動化分配")

# --- 側邊欄：設定預留金額 ---
with st.sidebar:
    st.header("⚙️ 參數設定")
    buffer_amt = st.slider("每人留底金額", 5000, 10000, 6500, step=500)
    st.info(f"系統會確保每人轉完後剩下約 {buffer_amt:,} 元。")

# --- 1. 輸入區 ---
col1, col2 = st.columns(2)
with col1:
    raw_transfers = st.text_area("📋 1. 貼上轉帳清單", height=200, placeholder="118540...-822 轉 19260")
with col2:
    raw_people = st.text_area("👥 2. 輸入人員餘額", height=200, placeholder="盛, 62215")

# --- 2. 核心邏輯 ---
def parse_data(trans_text, people_text):
    trans_list = []
    for line in trans_text.split('\n'):
        if not line.strip(): continue
        # 解析帳號與金額
        match = re.search(r'([\d-]+)轉(\d+)', line.replace(" ", ""))
        if match: trans_list.append({'info': match.group(1), 'amount': int(match.group(2))})
    
    people_list = []
    for line in people_text.split('\n'):
        if not line.strip(): continue
        # 解析名字與持金
        match = re.search(r'(\w+),\s*(\d+)', line)
        if match:
            bal = int(match.group(2))
            people_list.append({'name': match.group(1), 'bal': bal, 'limit': bal - buffer_amt, 'tasks': [], 'out': 0})
    return trans_list, people_list

# --- 3. 運算與輸出 ---
if st.button("🚀 開始智慧分配", use_container_width=True):
    trans_list, people_list = parse_data(raw_transfers, raw_people)
    
    if trans_list and people_list:
        # 大額優先
        trans_list.sort(key=lambda x: x['amount'], reverse=True)
        for t in trans_list:
            people_list.sort(key=lambda x: x['limit'], reverse=True)
            if people_list[0]['limit'] >= t['amount']:
                people_list[0]['tasks'].append(t)
                people_list[0]['limit'] -= t['amount']
                people_list[0]['out'] += t['amount']

        st.divider()
        st.metric("今日總計轉出", f"{sum(p['out'] for p in people_list):,} 元")
        
        # 顯示分配卡片
        for p in people_list:
            with st.container(border=True):
                final_bal = p['bal'] - p['out']
                st.write(f"### {p['name']} (餘額: {final_bal:,})")
                
                # 組合文字訊息
                msg = f"{p['name']}你好，今日轉帳任務：\n"
                for i, task in enumerate(p['tasks'], 1):
                    msg += f"{i}. {task['info']} 轉 {task['amount']}\n"
                msg += f"---\n總計：{p['out']:,}\n剩餘：{final_bal:,}"
                
                # 一鍵複製區塊
                st.code(msg, language="text")
                st.caption("👆 點擊右上角小方塊即可複製訊息")