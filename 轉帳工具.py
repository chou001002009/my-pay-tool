import streamlit as st
import re
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# 1. 網頁基本設定
st.set_page_config(page_title="Q哥轉帳助手", page_icon="💸", layout="wide")

# --- 2. 暴力資料清洗工具 ---
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

# --- 4. 側邊欄設定 ---
with st.sidebar:
    st.header("⚙️ 系統設定")
    buffer_val = st.slider("每人留底金額", 5000, 10000, 6500, step=500)
    st.divider()
    st.subheader("👥 常用人員勾選")
    all_names = ["大孟", "柏盛", "阿廷", "安妮", "宜峰", "育銘", "鴻運"]
    selected = st.multiselect("參與人員：", options=all_names, default=all_names)
    if st.button("📝 生成所選人員名單"):
        st.session_state["input_p"] = "\n".join([f"{n} , 0" for n in selected])
        st.rerun()

# --- 5. 初始化 Session State ---
if 'current_results' not in st.session_state: 
    st.session_state.current_results = None

# --- 6. 主要介面 ---
st.title("💸 轉帳自動化分配工具 (穩定同步版)")
tab1, tab2 = st.tabs(["🚀 開始分配", "📜 雲端歷史紀錄"])

with tab1:
    col1, col2 = st.columns(2)
    with col1: 
        raw_t = st.text_area("📋 1. 貼上轉帳清單", height=150, key="raw_t_in")
    with col2: 
        raw_p = st.text_area("👥 2. 輸入人員餘額", height=150, key="input_p")

    # 按鈕列
    c1, c2, c3 = st.columns([2, 2, 1])
    
    with c1:
        if st.button("🚀 執行分配並同步雲端", use_container_width=True):
            t_list, p_list = parse_data(raw_t, raw_p, buffer_val)
            if t_list and p_list:
                t_list.sort(key=lambda x: x['amount'], reverse=True)
                for t in t_list:
                    p_list.sort(key=lambda x: x['limit'], reverse=True)
                    if p_list[0]['limit'] >= t['amount']:
                        p_list[0]['tasks'].append(t)
                        p_list[0]['limit'] -= t['amount']
                        p_list[0]['out'] += t['amount']
                
                st.session_state.current_results = p_list
                
                try:
                    conn = st.connection("gsheets", type=GSheetsConnection)
                    now = datetime.now().strftime("%Y-%m-%d %H:%M")
                    new_recs = []
                    for p in p_list:
                        for t in p['tasks']:
                            new_recs.append({"時間": now, "執行人": p['name'], "帳號": f"'{t['info']}", "金額": t['amount'], "狀態": "未完成"})
                    
                    if new_recs:
                        new_df = pd.DataFrame(new_recs)
                        try:
                            ex_df = conn.read(worksheet="Sheet1", ttl=0)
                            final_df = pd.concat([ex_df, new_df], ignore_index=True) if not ex_df.empty else new_df
                        except: final_df = new_df
                        conn.update(worksheet="Sheet1", data=final_df)
                        st.success("✅ 雲端任務已建立！")
                except Exception as e: 
                    st.error(f"雲端連線失敗: {e}")
            else: 
                st.error("輸入格式有誤")

    with c2:
        if st.button("🎯 同步勾選狀態至雲端", use_container_width=True, type="primary"):
            if st.session_state.current_results:
                try:
                    conn = st.connection("gsheets", type=GSheetsConnection)
                    df = conn.read(worksheet="Sheet1", ttl=0)
                    if df.empty: 
                        st.warning("雲端目前沒有資料可更新")
                    else:
                        up_cnt = 0
                        for p in st.session_state.current_results:
                            for t in p['tasks']:
                                t_key = f"chk_{p['name']}_{t['info']}_{t['amount']}"
                                if st.session_state.get(t_key, False):
                                    m = (
                                        (df['執行人'].astype(str).apply(clean_txt) == clean_txt(p['name'])) &
                                        (df['帳號'].apply(clean_num) == clean_num(t['info'])) &
                                        (df['金額'].apply(clean_num) == clean_num(t['amount'])) &
                                        (df['狀態'].str.strip() == "未完成")
                                    )
                                    if m.any():
                                        df.at[df[m].index[-1], '狀態'] = "完成"
                                        up_cnt += 1
                        if up_cnt > 0:
                            conn.update(worksheet="Sheet1", data=df)
                            st.success(f"🎯 成功將 {up_cnt} 筆任務同步為完成！")
                            st.rerun()
                        else: 
                            st.info("沒有偵測到新勾選的未完成項目。")
                except Exception as e: 
                    st.error(f"更新失敗: {e}")
            else: 
                st.warning("請先執行分配。")

    with c3:
        if st.button("🗑️ 清空", use_container_width=True):
            st.session_state.current_results = None
            st.rerun()

    # --- 顯示分配卡片 ---
    if st.session_state.current_results:
        st.divider()
        for p in st.session_state.current_results:
            with st.container(border=True):
                st.success(f"### {p['name']} (總計: {p['out']:,})")
                
                # 任務文字預覽 (修正後的行號)
                task_lines = []
                for i, tk in enumerate(p['tasks']):
                    task_lines.append(f"{i+1}. {tk['info']} 轉 {tk['amount']:,}")
                
                msg = f"{p['name']}任務：\n" + "\n".join(task_lines)
                st.code(msg, language="text")
                
                # 手動核對打勾
                for tk in p['tasks']:
                    st.checkbox(f"金額 {tk['amount']:,} ({tk['info']})", key=f"chk_{p['name']}_{tk['info']}_{tk['amount']}")

with tab2:
    if st.button("🔄 刷新雲端顯示"): 
        st.rerun()
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(worksheet="Sheet1", ttl=0)
        st.dataframe(df.iloc[::-1], use_container_width=True)
    except: 
        st.info("尚無雲端資料。")
