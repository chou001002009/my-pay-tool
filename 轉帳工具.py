import streamlit as st
import re
import pandas as pd
from datetime import datetime

# 1. 網頁基本設定 (手機版優先)
st.set_page_config(page_title="轉帳助手", page_icon="💸", layout="wide")

# --- 2. 定義解析函數 ---
def parse_data(trans_text, people_text, buffer_val):
    trans_list = []
    for line in trans_text.split('\n'):
        if not line.strip(): continue
        # 解析「帳號 轉 金額」
        match = re.search(r'([\d-]+)轉(\d+)', line.replace(" ", ""))
        if match:
            trans_list.append({'info': match.group(1), 'amount': int(match.group(2))})
    
    people_list = []
    for line in people_text.split('\n'):
        if not line.strip(): continue
        # 解析「名字 有 金額」
        match = re.search(r'(\w+)有\s*(\d+)', line)
        if match:
            bal = int(match.group(2))
            people_list.append({
                'name': match.group(1), 
                'bal': bal, 
                'limit': bal - buffer_val, 
                'tasks': [], 
                'out': 0
            })
    return trans_list, people_list

# --- 3. 初始化 Session State (紀錄狀態) ---
if 'history' not in st.session_state:
    st.session_state.history = []
if 'current_results' not in st.session_state:
    st.session_state.current_results = None
if 'unassigned_results' not in st.session_state:
    st.session_state.unassigned_results = []

# --- 4. 側邊欄設定 ---
with st.sidebar:
    st.header("⚙️ 參數設定")
    buffer_val = st.slider("每人留底金額", 5000, 10000, 6500, step=500)
    st.divider()
    if st.button("🗑️ 清空所有歷史紀錄"):
        st.session_state.history = []
        st.rerun()

# --- 5. 主要介面 ---
st.title("💸 轉帳自動化分配工具")

tab1, tab2 = st.tabs(["🚀 開始分配", "📜 歷史紀錄"])

with tab1:
    col1, col2 = st.columns(2)
    with col1:
        raw_trans = st.text_area("📋 1. 貼上轉帳清單", height=150, placeholder="帳號-銀行碼 轉 金額")
    with col2:
        raw_ppl = st.text_area("👥 2. 輸入人員餘額", height=150, placeholder="人名 有 金額")

    # 分配按鈕
    if st.button("🚀 執行智慧分配", use_container_width=True):
        if raw_trans and raw_ppl:
            t_list, p_list = parse_data(raw_trans, raw_ppl, buffer_val)
            
            if t_list and p_list:
                # 執行分配
                t_list.sort(key=lambda x: x['amount'], reverse=True)
                unassigned = []
                for t in t_list:
                    p_list.sort(key=lambda x: x['limit'], reverse=True)
                    if p_list[0]['limit'] >= t['amount']:
                        p_list[0]['tasks'].append(t)
                        p_list[0]['limit'] -= t['amount']
                        p_list[0]['out'] += t['amount']
                    else:
                        unassigned.append(t)
                
                # 存入 Session 供 UI 使用
                st.session_state.current_results = p_list
                st.session_state.unassigned_results = unassigned
                
                # 存入歷史
                now = datetime.now().strftime("%Y-%m-%d %H:%M")
                for p in p_list:
                    for task in p['tasks']:
                        st.session_state.history.append({
                            "時間": now, "執行人": p['name'], "帳號": task['info'], 
                            "金額": task['amount'], "結餘": p['bal'] - p['out']
                        })
            else:
                st.error("格式錯誤，請檢查文字中是否有『轉』字與『有』字。")
        else:
            st.warning("請先輸入清單與人員餘額。")

    # --- 顯示漂亮結果與進度追蹤 ---
    if st.session_state.current_results:
        st.divider()
        st.subheader("🏁 今日執行進度")
        
        results = st.session_state.current_results
        unassigned = st.session_state.unassigned_results
        
        # 手機版建議一行顯示一個，電腦版會自動併排
        for idx, p in enumerate(results):
            final_bal = p['bal'] - p['out']
            with st.container(border=True):
                c1, c2 = st.columns([1, 2])
                with c1:
                    st.success(f"### {p['name']}")
                    st.write(f"持有: {p['bal']:,}")
                    st.write(f"**轉出: {p['out']:,}**")
                    st.write(f"預計結餘: `{final_bal:,}`")
                
                with c2:
                    # 複製訊息
                    msg = f"{p['name']}你好，今日轉帳任務：\n"
                    for i, t in enumerate(p['tasks'], 1):
                        msg += f"{i}. {t['info']} 轉 {t['amount']:,}\n"
                    msg += f"---\n總計：{p['out']:,}\n剩餘：{final_bal:,}"
                    st.code(msg, language="text")
                    
                    # 打勾區域
                    st.write("**完成核對：**")
                    cols = st.columns(2) # 內部分成兩小行打勾
                    for i, t in enumerate(p['tasks']):
                        t_key = f"chk_{p['name']}_{t['info']}_{t['amount']}_{i}"
                        with cols[i % 2]:
                            st.checkbox(f"{t['amount']:,} ({t['info'][-4:]})", key=t_key)

        # 未分配提醒
        if unassigned:
            st.divider()
            st.error(f"⚠️ 還有 {len(unassigned)} 筆未分配：")
            un_text = ""
            for i, u in enumerate(unassigned, 1):
                un_text += f"{i}. {u['info']} 轉 {u['amount']:,}\n"
            st.code(un_text, language="text")

# --- 第二頁：歷史紀錄 ---
with tab2:
    if st.session_state.history:
        df = pd.DataFrame(st.session_state.history)
        st.dataframe(df, use_container_width=True)
        csv = df.to_csv(index=False).encode('utf-8-sig')
        st.download_button("📥 下載完整紀錄 (CSV)", csv, f"轉帳_{datetime.now().strftime('%m%d')}.csv", "text/csv")
    else:
        st.info("尚無歷史紀錄。")
