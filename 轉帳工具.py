import streamlit as st
import re
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# 1. 網頁基本設定
st.set_page_config(page_title="Q哥轉帳助手 Pro", page_icon="💸", layout="wide")

# --- 2. 數據清洗工具 (核心組件) ---
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

# --- 4. 核心功能：同步目前畫面上的所有狀態 ---
def sync_to_cloud():
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(worksheet="Sheet1", ttl=0)
        
        if df.empty:
            st.warning("⚠️ 雲端目前沒有任何任務紀錄。請先點擊左側『🚀 執行分配』上傳任務。")
            return

        up_cnt = 0
        df_updated = df.copy()

        # 掃描當前 session 中的所有人員與任務
        for p in st.session_state.current_results:
            for t in p['tasks']:
                # 建立唯一的 Key 來抓取畫面上勾選狀態
                chk_key = f"chk_{t['info']}_{t['amount']}"
                if st.session_state.get(chk_key, False):
                    target_info = clean_num(t['info'])
                    target_amt = clean_num(t['amount'])
                    
                    # 搜尋雲端中該筆帳號與金額且為未完成的紀錄
                    mask = (
                        (df_updated['帳號'].apply(clean_num) == target_info) & 
                        (df_updated['金額'].apply(clean_num) == target_amt) & 
                        (df_updated['狀態'].str.strip() == "未完成")
                    )
                    
                    if mask.any():
                        idx = df_updated[mask].index[-1]
                        df_updated.at[idx, '狀態'] = "完成"
                        # 同步時確保雲端的執行人跟畫面上微調後的人名一致
                        df_updated.at[idx, '執行人'] = p['name']
                        up_cnt += 1
        
        if up_cnt > 0:
            conn.update(worksheet="Sheet1", data=df_updated)
            st.success(f"🎯 成功同步 {up_cnt} 筆任務！")
            st.rerun()
        else:
            st.info("ℹ️ 沒有偵測到勾選『完成』的項目。")
    except Exception as e:
        st.error(f"同步失敗：{e}")

# --- 5. 初始化 Session ---
if 'current_results' not in st.session_state: st.session_state.current_results = None
if 'un_results' not in st.session_state: st.session_state.un_results = []
if 'total_amt' not in st.session_state: st.session_state.total_amt = 0

all_names_list = ["大孟", "柏盛", "阿廷", "安妮", "宜峰", "育銘", "鴻運", "我"]

# --- 6. 側邊欄 ---
with st.sidebar:
    st.header("⚙️ 系統設定")
    buffer_val = st.slider("每人留底金額", 5000, 10000, 6500, step=500)
    selected_ppl = st.multiselect("參與人員：", options=all_names_list, default=all_names_list)
    if st.button("📝 生成所選人員名單"):
        st.session_state["input_p"] = "\n".join([f"{n} , 0" for n in selected_ppl])
        st.rerun()

# --- 7. 主要介面 ---
st.title("💸 Q哥轉帳自動分配 Pro")
tab1, tab2 = st.tabs(["🚀 分配與微調", "📜 雲端歷史紀錄"])

with tab1:
    col1, col2 = st.columns(2)
    with col1: raw_t = st.text_area("📋 1. 貼上轉帳清單", height=150, key="raw_t_in")
    with col2: raw_p = st.text_area("👥 2. 輸入人員餘額", height=150, key="input_p")

    c1, c2, c3 = st.columns([2, 2, 1])
    with c1:
        if st.button("🚀 執行分配並上傳雲端", use_container_width=True):
            t_list, p_list, total_amt = parse_data(raw_t, raw_p, buffer_val)
            if t_list and p_list:
                t_list.sort(key=lambda x: x['amount']) # 小額優先分配
                unassigned = []
                for t in t_list:
                    p_list.sort(key=lambda x: x['limit'], reverse=True)
                    # 優先找單人全額分配
                    if p_list[0]['limit'] >= t['amount']:
                        p_list[0]['tasks'].append(t)
                        p_list[0]['limit'] -= t['amount']
                        p_list[0]['out'] += t['amount']
                    # 沒人能吃下且大於65000，才拆帳
                    elif t['amount'] > 65000:
                        splits, rem = 0, t['amount']
                        for p in p_list:
                            if p['limit'] > 0 and rem > 0 and splits < 5:
                                # 拆帳取整數邏輯
                                take = (min(rem, p['limit']) // 100 * 100) if (min(rem, p['limit']) < rem and splits < 4) else min(rem, p['limit'])
                                if take > 0:
                                    p['tasks'].append({'info': f"{t['info']} (拆)", 'amount': int(take)})
                                    p['limit'] -= take; p['out'] += take; rem -= take; splits += 1
                        if rem > 0: unassigned.append({'info': t['info'], 'amount': rem})
                    else:
                        unassigned.append(t)
                
                st.session_state.current_results = p_list
                st.session_state.un_results = unassigned
                st.session_state.total_amt = total_amt
                
                # 同步初始化上傳雲端
                try:
                    conn = st.connection("gsheets", type=GSheetsConnection)
                    now = datetime.now().strftime("%Y-%m-%d %H:%M")
                    new_recs = []
                    for p in p_list:
                        for tk in p['tasks']:
                            new_recs.append({"時間": now, "執行人": p['name'], "帳號": f"'{tk['info']}", "金額": tk['amount'], "狀態": "未完成"})
                    if new_recs:
                        ex_df = conn.read(worksheet="Sheet1", ttl=0)
                        final_df = pd.concat([ex_df, pd.DataFrame(new_recs)], ignore_index=True) if not ex_df.empty else pd.DataFrame(new_recs)
                        conn.update(worksheet="Sheet1", data=final_df)
                        st.success("✅ 任務已備份至雲端，可開始勾選或改指派人。")
                except: st.error("雲端同步失敗，請檢查權限設定。")
            else: st.error("輸入格式有誤。")

    with c2:
        if st.button("🎯 同步勾選狀態至雲端", use_container_width=True, type="primary"):
            if st.session_state.current_results: sync_to_cloud()
            else: st.warning("請先執行分配！")

    with c3:
        if st.button("🗑️ 清空今日", use_container_width=True):
            st.session_state.current_results = None; st.session_state.un_results = []; st.rerun()

    # --- 8. 顯示與改指派區 ---
    if st.session_state.current_results:
        st.divider()
        un_sum = sum(u['amount'] for u in st.session_state.un_results)
        st.info(f"📊 今日總額：{st.session_state.total_amt:,} | 已分配：{st.session_state.total_amt - un_sum:,}")
        
        results = st.session_state.current_results
        for p_idx, p in enumerate(results):
            if p['tasks']:
                with st.container(border=True):
                    st.success(f"### {p['name']} (今日轉出: {p['out']:,})")
                    for t_idx, tk in enumerate(p['tasks']):
                        c_chk, c_txt, c_sel = st.columns([1, 4, 2])
                        with c_chk:
                            st.checkbox("完成", key=f"chk_{tk['info']}_{tk['amount']}")
                        with c_txt:
                            st.write(f"**{tk['amount']:,}** ({tk['info']})")
                        with c_sel:
                            # 下拉選單改指派
                            new_owner = st.selectbox(
                                "改指派", 
                                options=all_names_list, 
                                index=all_names_list.index(p['name']) if p['name'] in all_names_list else 0,
                                key=f"move_{tk['info']}_{p['name']}_{tk['amount']}",
                                label_visibility="collapsed"
                            )
                            if new_owner != p['name']:
                                task_to_move = results[p_idx]['tasks'].pop(t_idx)
                                results[p_idx]['out'] -= task_to_move['amount']
                                for target in results:
                                    if target['name'] == new_owner:
                                        target['tasks'].append(task_to_move)
                                        target['out'] += task_to_move['amount']; break
                                st.session_state.current_results = results
                                st.rerun()

        if st.session_state.un_results:
            st.divider()
            st.error(f"⚠️ 尚有未分配總額：{un_sum:,} 元")
            st.code("\n".join([f"{u['info']} 缺口 {u['amount']:,}" for u in st.session_state.un_results]))

with tab2:
    if st.button("🔄 刷新雲端資料"): st.rerun()
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(worksheet="Sheet1", ttl=0)
        st.dataframe(df.iloc[::-1], use_container_width=True)
    except: st.info("尚無雲端紀錄。")
