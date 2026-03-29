import streamlit as st
import re
import pandas as pd
from datetime import datetime

# 1. 設定 App 圖示與標題 (換成錢包 Emoji 💸)
st.set_page_config(
    page_title="轉帳分配助手", 
    page_icon="💸", 
    layout="wide"
)

st.title("💰 轉帳自動化分配工具")

# 初始化歷史紀錄 (存放在 Session 內)
if 'history' not in st.session_state:
    st.session_state.history = []

# 使用分頁：將功能分開
tab1, tab2 = st.tabs(["🚀 開始分配", "📜 歷史紀錄"])

# --- 側邊欄：設定 ---
with st.sidebar:
    st.header("⚙️ 參數設定")
    buffer_amt = st.slider("每人留底金額", 5000, 10000, 6500, step=500)
    if st.button("🗑️ 清空所有歷史紀錄"):
        st.session_state.history = []
        st.rerun()

# --- 第一頁：分配功能 ---
with tab1:
    col1, col2 = st.columns(2)
    with col1:
        raw_transfers = st.text_area("📋 1. 貼上轉帳清單", height=200)
    with col2:
        raw_people = st.text_area("👥 2. 輸入人員餘額", height=200)

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

    if st.button("🚀 執行智慧分配", use_container_width=True):
        trans_list, people_list = parse_data(raw_transfers, raw_people)
        
        if trans_list and people_list:
            trans_list.sort(key=lambda x: x['amount'], reverse=True)
            unassigned = []
            
            for t in trans_list:
                people_list.sort(key=lambda x: x['limit'], reverse=True)
                if people_list[0]['limit'] >= t['amount']:
                    people_list[0]['tasks'].append(t)
                    people_list[0]['limit'] -= t['amount']
                    people_list[0]['out'] += t['amount']
                else:
                    unassigned.append(t)

            # 記錄到歷史清單
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            for p in people_list:
                if p['tasks']:
                    for t in p['tasks']:
                        st.session_state.history.append({
                            "日期時間": now,
                            "執行人": p['name'],
                            "帳號資訊": t['info'],
                            "轉帳金額": t['amount'],
                            "執行後餘額": p['bal'] - p['out']
                        })

            # 呈現結果 (略縮顯示)
            st.divider()
            cols = st.columns(len(people_list))
            for idx, p in enumerate(people_list):
                with cols[idx]:
                    final_bal = p['bal'] - p['out']
                    with st.container(border=True):
                        st.write(f"### {p['name']}")
                        msg = f"{p['name']}你好，今日轉帳任務：\n"
                        for i, task in enumerate(p['tasks'], 1):
                            msg += f"{i}. {task['info']} 轉 {task['amount']}\n"
                        msg += f"---\n總計：{p['out']:,}\n剩餘：{final_bal:,}"
                        st.code(msg, language="text")

            # --- 5. 顯示未分配的部分 (重點修正) ---
            if unassigned:
            st.divider()
            st.error(f"⚠️ 額度不足！剩餘 {len(unassigned)} 筆未分配。")
            
            # 建立未分配清單的文字
            un_msg = "❌ 以下帳號因額度不足尚未分配：\n"
            total_un = 0
            for i, u in enumerate(unassigned, 1):
                un_msg += f"{i}. {u['info']} 轉 {u['amount']:,}\n"
                total_un += u['amount']
            un_msg += f"---\n待分配總額：{total_un:,}"
            
            # 使用 st.code 顯示，方便你複製或對帳
            st.code(un_msg, language="text")
            
            # 也可以額外加一個小提示，告訴你目前還差多少錢
            st.warning(f"💡 建議：你需要再補大約 {total_un:,} 元的額度，或調低左側的「留底金額」。")
            else:
               st.warning("請輸入內容。")

# --- 第二頁：歷史紀錄 ---
with tab2:
    st.subheader("📝 歷史分配紀錄")
    if st.session_state.history:
        df = pd.DataFrame(st.session_state.history)
        
        # 顯示表格
        st.dataframe(df, use_container_width=True)
        
        # 讓使用者可以下載成 CSV 存檔 (最保險)
        csv = df.to_csv(index=False).encode('utf-8-sig') # utf-8-sig 解決 Excel 中文亂碼
        st.download_button(
            label="📥 下載完整歷史紀錄 (CSV)",
            data=csv,
            file_name=f"轉帳紀錄_{datetime.now().strftime('%Y%m%d')}.csv",
            mime='text/csv',
            use_container_width=True
        )
    else:
        st.info("目前還沒有任何分配紀錄。")
