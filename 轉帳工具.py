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
        raw_transfers = st.text_area("📋 1. 貼上轉帳清單", height=200, key="input_trans")
    with col2:
        raw_people = st.text_area("👥 2. 輸入人員餘額", height=200, key="input_people")

    # 點擊按鈕後，將結果存入 session_state
    if st.button("🚀 執行智慧分配", use_container_width=True):
        trans_list, people_list = parse_data(raw_transfers, raw_people)
        
        if trans_list and people_list:
            # 這裡執行你原本的分配邏輯 (大額優先...)
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
            
            # --- 重要：將結果存起來，這樣勾選時才不會消失 ---
            st.session_state.current_results = people_list
            st.session_state.unassigned_results = unassigned
            # 清空舊的勾選紀錄
            st.session_state.done_tasks = {} 
        else:
            st.warning("請輸入內容。")

    # --- 顯示結果與打勾區塊 ---
    if 'current_results' in st.session_state:
        people_results = st.session_state.current_results
        unassigned_results = st.session_state.unassigned_results

        st.divider()
        st.subheader("🏁 執行進度追蹤")
        
        # 建立三行顯示每個人
        res_cols = st.columns(len(people_results))
        total_tasks_count = 0
        finished_tasks_count = 0

        for idx, p in enumerate(people_results):
            with res_cols[idx]:
                final_bal = p['bal'] - p['out']
                st.success(f"### {p['name']}")
                
                # 1. 複製訊息區
                msg = f"{p['name']}你好，今日轉帳任務：\n"
                for i, task in enumerate(p['tasks'], 1):
                    msg += f"{i}. {task['info']} 轉 {task['amount']:,}\n"
                msg += f"---\n總計：{p['out']:,}\n剩餘：{final_bal:,}"
                st.code(msg, language="text")

                # 2. 手動打勾確認區
                st.write("**核對清單：**")
                for i, task in enumerate(p['tasks']):
                    total_tasks_count += 1
                    # 建立唯一的 Key 用來紀錄打勾狀態
                    t_key = f"check_{p['name']}_{task['info']}_{task['amount']}"
                    if st.checkbox(f"{task['amount']:,} ({task['info'][-4:]})", key=t_key):
                        finished_tasks_count += 1
        
        # 3. 總進度條
        if total_tasks_count > 0:
            progress_val = finished_tasks_count / total_tasks_count
            st.write(f"📊 **今日總進度：{finished_tasks_count} / {total_tasks_count} 筆已完成**")
            st.progress(progress_val)
            if progress_val == 1.0:
                st.balloons()
                st.success("🎉 太棒了！今日轉帳任務已全數結清！")

        # 4. 未分配顯示
        if unassigned_results:
            st.divider()
            st.error(f"⚠️ 還有 {len(unassigned_results)} 筆未分配，請檢查額度。")

          

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
