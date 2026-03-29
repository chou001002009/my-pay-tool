import streamlit as st
import re

# 頁面基本設定
st.set_page_config(page_title="轉帳分配助手",page_icon="💰", layout="wide")
st.title("💰 轉帳自動化分配")

# --- 側邊欄：設定預留金額 ---
with st.sidebar:
    st.header("⚙️ 參數設定")
    buffer_amt = st.slider("每人留底金額 (5000-8000)", 5000, 10000, 6500, step=500)
    st.info(f"系統會確保每人轉完後剩下約 {buffer_amt:,} 元。")

# --- 1. 輸入區 ---
col1, col2 = st.columns(2)
with col1:
    st.subheader("📋 1. 貼上轉帳清單")
    raw_transfers = st.text_area("格式：帳號-銀行碼 轉 金額", height=200, placeholder="118540...-822 轉 19260")
with col2:
    st.subheader("👥 2. 輸入人員餘額")
    raw_people = st.text_area("格式：人名有金額", height=200, placeholder="盛, 62215")

# --- 2. 核心邏輯 ---
def parse_data(trans_text, people_text):
    trans_list = []
    for line in trans_text.split('\n'):
        if not line.strip(): continue
        match = re.search(r'([\d-]+)轉(\d+)', line.replace(" ", ""))
        if match: trans_list.append({'info': match.group(1), 'amount': int(match.group(2))})
    
    people_list = []
    for line in people_text.split('\n'):
        if not line.strip(): continue
        match = re.search(r'(\w+),\s*(\d+)', line)
        if match:
            bal = int(match.group(2))
            people_list.append({'name': match.group(1), 'bal': bal, 'limit': bal - buffer_amt, 'tasks': [], 'out': 0})
    return trans_list, people_list

# --- 3. 運算與輸出 ---
if st.button("🚀 開始智慧分配", use_container_width=True):
    trans_list, people_list = parse_data(raw_transfers, raw_people)
    
    if trans_list and people_list:
        # 大額優先分配
        trans_list.sort(key=lambda x: x['amount'], reverse=True)
        
        unassigned = [] # 用來存放分配不下的筆數
        
        for t in trans_list:
            # 每次分配前，重新排序，找「目前剩餘額度最高」的人
            people_list.sort(key=lambda x: x['limit'], reverse=True)
            
            # 如果剩餘額度最高的人也接不下這筆，就代表這筆暫時分不掉
            if people_list[0]['limit'] >= t['amount']:
                people_list[0]['tasks'].append(t)
                people_list[0]['limit'] -= t['amount']
                people_list[0]['out'] += t['amount']
            else:
                unassigned.append(t)

        # --- 4. 畫面呈現 ---
        st.divider()
        
        # 顯示已成功分配的部分
        st.subheader("✅ 已分配任務")
        cols = st.columns(len(people_list))
        for idx, p in enumerate(people_list):
            with cols[idx]:
                final_bal = p['bal'] - p['out']
                with st.container(border=True):
                    st.write(f"### {p['name']}")
                    st.write(f"預計剩餘: `{final_bal:,}`")
                    
                    msg = f"{p['name']}你好，今日轉帳任務：\n"
                    for i, task in enumerate(p['tasks'], 1):
                        msg += f"{i}. {task['info']} 轉 {task['amount']}\n"
                    msg += f"---\n總計：{p['out']:,}\n剩餘：{final_bal:,}"
                    
                    st.code(msg, language="text")

        # --- 5. 顯示未分配的部分 (重點修正) ---
        if unassigned:
            st.divider()
            st.error("⚠️ 注意：以下筆數因額度不足『尚未分配』！")
            
            # 用表格呈現漏掉的筆數，方便你手動加總或檢查
            unassigned_data = []
            total_unassigned = 0
            for u in unassigned:
                unassigned_data.append({"帳號資訊": u['info'], "金額": f"{u['amount']:,}"})
                total_unassigned += u['amount']
            
            st.table(unassigned_data)
            st.warning(f"尚未分配的總金額合計為：{total_unassigned:,} 元")
    else:
        st.warning("請確保輸入格式正確後再點擊分配。")
