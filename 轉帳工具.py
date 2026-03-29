import streamlit as st
import re
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection # 需安裝

# 1. 網頁基本設定
st.set_page_config(page_title="Q哥轉帳助手", page_icon="💸", layout="wide")

# --- 2. 初始化 Session State ---
if 'history' not in st.session_state:
    st.session_state.history = []
if 'current_results' not in st.session_state:
    st.session_state.current_results = None

# --- 2. 定義解析函數 (優化版：支援「有」或「逗號」) ---
def parse_data(trans_text, people_text, buffer_val):
    t_list = []
    for line in trans_text.split('\n'):
        if not line.strip(): continue
        match = re.search(r'([\d-]+)轉(\d+)', line.replace(" ", ""))
        if match:
            t_list.append({'info': match.group(1), 'amount': int(match.group(2))})
    
    p_list = []
    for line in people_text.split('\n'):
        if not line.strip(): continue
        # 優化後的正則表達式：支援「大孟 有 100」或「大孟 , 100」
        match = re.search(r'(\w+)\s*(?:,|,)\s*(\d+)', line.replace(" ", ""))
        if match:
            bal = int(match.group(2))
            p_list.append({
                'name': match.group(1), 
                'bal': bal, 
                'limit': bal - buffer_val, 
                'tasks': [], 
                'out': 0
            })
    return t_list, p_list

# --- 3. 側邊欄：常用人員勾選設定 ---
with st.sidebar:
    st.header("⚙️ 系統設定")
    buffer_val = st.slider("每人留底金額", 5000, 10000, 6500, step=500)
    
    st.divider()
    st.subheader("👥 常用人員選擇")
    
    # 這裡定義完整名單
    all_names = ["大孟", "柏盛", "阿廷", "安妮", "宜峰", "育銘", "鴻運"]
    
    # 使用多選框，預設全選 (也可以改成預設不選)
    selected_names = st.multiselect(
        "選擇本次參與人員：",
        options=all_names,
        default=all_names
    )
    
    if st.button("📝 生成所選人員清單"):
        # 根據勾選的人名生成範本，使用你要求的逗號格式
        if selected_names:
            template = "\n".join([f"{name} , 0" for name in selected_names])
            st.session_state["input_p"] = template
            st.rerun()
        else:
            st.warning("請至少選擇一個人喔！")

    st.divider()
    if st.button("🚨 清空所有歷史紀錄"):
        st.session_state.history = []
        st.rerun()

# --- 4. 解析函數 ---
def parse_data(trans_text, people_text, buffer_v):
    t_list = []
    for line in trans_text.split('\n'):
        if not line.strip(): continue
        match = re.search(r'([\d-]+)轉(\d+)', line.replace(" ", ""))
        if match: t_list.append({'info': match.group(1), 'amount': int(match.group(2))})
    
    p_list = []
    for line in people_text.split('\n'):
        if not line.strip(): continue
        match = re.search(r'(\w+),\s*(\d+)', line)
        if match:
            bal = int(match.group(2))
            p_list.append({'name': match.group(1), 'bal': bal, 'limit': bal - buffer_v, 'tasks': [], 'out': 0})
    return t_list, p_list

# --- 5. 主要介面 ---
st.title("💸 轉帳自動化分配工具")

tab1, tab2 = st.tabs(["🚀 開始分配", "📜 雲端歷史紀錄"])

with tab1:
    col1, col2 = st.columns(2)
    with col1:
        raw_trans = st.text_area("📋 1. 貼上轉帳清單", height=150, placeholder="帳號-銀行碼 轉 金額", key="input_t")
    with col2:
        # 這裡的 key 與側邊欄按鈕連動
        raw_ppl = st.text_area("👥 2. 輸入人員餘額", height=150, placeholder="人名 有 金額", key="input_p")

    # 功能按鈕
    c_btn1, c_btn2 = st.columns([3, 1])
    with c_btn1:
        if st.button("🚀 執行智慧分配", use_container_width=True):
            if raw_trans and raw_ppl:
                t_list, p_list = parse_data(raw_trans, raw_ppl, buffer_val)
                if t_list and p_list:
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
                    st.session_state.current_results = p_list
                    st.session_state.unassigned_results = unassigned
                    
                    # 準備寫入紀錄
                    now = datetime.now().strftime("%Y-%m-%d %H:%M")
                    for p in p_list:
                        for task in p['tasks']:
                            st.session_state.history.append({
                                "時間": now, "執行人": p['name'], "帳號": task['info'], 
                                "金額": task['amount'], "結餘": p['bal'] - p['out']
                            })
                else: st.error("格式錯誤")
    with c_btn2:
        if st.button("🗑️ 清空今日", use_container_width=True):
            st.session_state.current_results = None
            st.rerun()

    # 顯示結果 (同前一版)
    if st.session_state.current_results:
        results = st.session_state.current_results
        for idx, p in enumerate(results):
            final_bal = p['bal'] - p['out']
            with st.container(border=True):
                c_left, c_right = st.columns([1, 2])
                with c_left:
                    st.success(f"### {p['name']}")
                    st.write(f"預計結餘: `{final_bal:,}`")
                with c_right:
                    msg = f"{p['name']}今日任務：\n" + "\n".join([f"{i+1}. {t['info']} 轉 {t['amount']:,}" for i, t in enumerate(p['tasks'])])
                    st.code(msg, language="text")
                    # 打勾區
                    for i, t in enumerate(p['tasks']):
                        st.checkbox(f"金額 {t['amount']:,} ({t['info']})", key=f"c_{p['name']}_{i}")

# --- 6. Google Sheets 顯示頁面 ---
with tab2:
    st.subheader("☁️ 雲端同步紀錄")
    try:
        # 這邊是連動 Google Sheets 的語法
        conn = st.connection("gsheets", type=GSheetsConnection)
        # 讀取現有資料 (假設你的試算表名稱叫 'Records')
        # df = conn.read(worksheet="Records")
        # st.dataframe(df)
        st.info("💡 連結完成後，您的歷史紀錄將會自動同步到 Google Sheets。")
    except:
        st.warning("尚未設定 Google Sheets 連線密碼 (Secrets)。")
    
    # 暫時用目前的 Local 紀錄墊一下
    if st.session_state.history:
        st.table(pd.DataFrame(st.session_state.history))

# 在智慧分配按鈕邏輯的最下面加入：
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
    # 讀取現有資料
    existing_data = conn.read(worksheet="Sheet1")
    # 結合新舊資料
    new_df = pd.DataFrame(st.session_state.history)
    updated_df = pd.concat([existing_data, new_df], ignore_index=True)
    # 寫回雲端
    conn.update(worksheet="Sheet1", data=updated_df)
    st.toast("✅ 帳務已同步至 Google Sheets！")
except Exception as e:
    st.error(f"雲端同步失敗：{e}")
