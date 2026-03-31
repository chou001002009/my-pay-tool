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

# --- 4. 初始化 Session ---
if 'current_results' not in st.session_state: st.session_state.current_results = None
if 'un_results' not in st.session_state: st.session_state.un_results = []
if 'total_amt' not in st.session_state: st.session_state.total_amt = 0
if 'uploaded' not in st.session_state: st.session_state.uploaded = False

all_names_list = ["大孟", "柏盛", "阿廷", "安妮", "宜峰", "育銘", "鴻運", "我"]

# --- 5. 側邊欄 ---
with st.sidebar:
    st.header("⚙️ 系統設定")
    buffer_val = st.slider("每人留底金額", 5000, 10000, 6500, step=500)
    selected_ppl = st.multiselect("參與人員：", options=all_names_list, default=all_names_list)
    if st.button("📝 生成所選人員名單"):
        st.session_state["input_p"] = "\n".join([f"{n} , 0" for n in selected_ppl])
        st.rerun()

# --- 6. 主要介面 ---
st.title("💸 Q哥轉帳自動分配 Pro")
tab1, tab2 = st.tabs(["🚀 分配與微調", "📜 雲端歷史紀錄"])

with tab1:
    col1, col2 = st.columns(2)
    with col1: raw_t = st.text_area("📋 1. 貼上轉帳清單", height=150, key="raw_t_in")
    with col2: raw_p = st.text_area("👥 2. 輸入人員餘額", height=150, key="input_p")

    # 按鈕列
    btn_c1, btn_c2, btn_c3, btn_c4 = st.columns([2, 2, 2, 1])
    
    with btn_c1:
        if st.button("🚀 1. 執行自動分配", use_container_width=True):
            t_list, p_list, total_amt = parse_data(raw_t, raw_p, buffer_val)
            if t_list and p_list:
                t_list.sort(key=lambda x: x['amount']) # 小額優先
                unassigned = []
                for t in t_list:
                    p_list.sort(key=lambda x: x['limit'], reverse=True)
                    if p_list[0]['limit'] >= t['amount']:
                        p_list[0]['tasks'].append(t)
                        p_list[0]['limit'] -= t['amount']; p_list[0]['out'] += t['amount']
                    elif t['amount'] > 65000:
                        splits, rem = 0, t['amount']
                        for p in p_list:
                            if p['limit'] > 0 and rem > 0 and splits < 5:
                                take = (min(rem, p['limit']) // 100 * 100) if (min(rem, p['limit']) < rem and splits < 4) else min(rem, p['limit'])
                                if take > 0:
                                    p['tasks'].append({'info': f"{t['info']} (拆)", 'amount': int(take)})
                                    p['limit'] -= take; p['out'] += take; rem -= take; splits += 1
                        if rem > 0: unassigned.append({'info': t['info'], 'amount': rem})
                    else: unassigned.append(t)
                st.session_state.current_results = p_list
                st.session_state.un_results = unassigned
                st.session_state.total_amt = total_amt
                st.session_state.uploaded = False
                st.success("✅ 系統分配完成！")
            else: st.error("格式錯誤")

    with btn_c2:
        if st.button("📤 2. 確認並上傳雲端", use_container_width=True):
            if st.session_state.current_results:
                try:
                    conn = st.connection("gsheets", type=GSheetsConnection)
                    now = datetime.now().strftime("%Y-%m-%d %H:%M")
                    new_recs = []
                    for p in st.session_state.current_results:
                        for tk in p['tasks']:
                            new_recs.append({"時間": now, "執行人": p['name'], "帳號": f"'{tk['info']}", "金額": tk['amount'], "狀態": "未完成"})
                    if new_recs:
                        ex_df = conn.read(worksheet="Sheet1", ttl=0)
                        final_df = pd.concat([ex_df, pd.DataFrame(new_recs)], ignore_index=True) if not ex_df.empty else pd.DataFrame(new_recs)
                        conn.update(worksheet="Sheet1", data=final_df)
                        st.session_state.uploaded = True
                        st.success("✅ 最終結果已同步至雲端！")
                except Exception as e: st.error(f"上傳失敗: {e}")
            else: st.warning("請先執行分配！")

    with btn_c3:
        if st.button("🎯 3. 同步勾選至雲端", use_container_width=True, type="primary"):
            if st.session_state.uploaded:
                try:
                    conn = st.connection("gsheets", type=GSheetsConnection)
                    df = conn.read(worksheet="Sheet1", ttl=0)
                    up_cnt = 0
                    for p in st.session_state.current_results:
                        for t in p['tasks']:
                            chk_key = f"chk_{t['info']}_{t['amount']}"
                            if st.session_state.get(chk_key, False):
                                t_info, t_amt = clean_num(t['info']), clean_num(t['amount'])
                                mask = ((df['帳號'].apply(clean_num) == t_info) & (df['金額'].apply(clean_num) == t_amt) & (df['狀態'].str.strip() == "未完成"))
                                if mask.any():
                                    idx = df[mask].index[-1]
                                    df.at[idx, '狀態'] = "完成"; df.at[idx, '執行人'] = p['name']; up_cnt += 1
                    if up_cnt > 0:
                        conn.update(worksheet="Sheet1", data=df); st.success(f"🎯 同步成功 {up_cnt} 筆！"); st.rerun()
                except Exception as e: st.error(f"同步失敗: {e}")
            else: st.warning("請先完成第 2 步上傳雲端！")

    with btn_c4:
        if st.button("🗑️ 清空", use_container_width=True):
            st.session_state.current_results = None; st.session_state.un_results = []; st.rerun()

    # --- 8. 顯示與改指派區 ---
    if st.session_state.current_results:
        st.divider()
        un_sum = sum(u['amount'] for u in st.session_state.un_results)
        st.info(f"📊 總額：{st.session_state.total_amt:,} | 已分：{st.session_state.total_amt - un_sum:,}")
        
        results = st.session_state.current_results
        
        # 已分配卡片顯示
        for p_idx, p in enumerate(results):
            if p['tasks']:
                with st.container(border=True):
                    st.success(f"### {p['name']} (今日預計轉出: {p['out']:,})")
                    for t_idx, tk in enumerate(p['tasks']):
                        c_chk, c_txt, c_sel = st.columns([1, 4, 2])
                        with c_chk: st.checkbox("完", key=f"chk_{tk['info']}_{tk['amount']}")
                        with c_txt: st.write(f"**{tk['amount']:,}** ({tk['info']})")
                        with c_sel:
                            new_owner = st.selectbox("指派", options=all_names_list, index=all_names_list.index(p['name']), key=f"mv_{tk['info']}_{p['name']}_{tk['amount']}", label_visibility="collapsed")
                            if new_owner != p['name']:
                                task = results[p_idx]['tasks'].pop(t_idx)
                                results[p_idx]['out'] -= task['amount']
                                for target in results:
                                    if target['name'] == new_owner:
                                        target['tasks'].append(task); target['out'] += task['amount']; break
                                st.session_state.current_results = results; st.rerun()

        # 🚨 未分配區 (加入手動指派與拆帳功能)
        if st.session_state.un_results:
            st.divider()
            st.error(f"⚠️ 未分配總額：{un_sum:,} 元")
            un_list = st.session_state.un_results
            for u_idx, u in enumerate(un_list):
                with st.container(border=True):
                    c_utxt, c_uassign, c_usplit = st.columns([4, 2, 1])
                    with c_utxt:
                        st.write(f"❌ **{u['amount']:,}** ({u['info']})")
                    with c_uassign:
                        target_name = st.selectbox("手動指派給", options=["--請選擇--"] + all_names_list, key=f"u_assign_{u_idx}_{u['amount']}", label_visibility="collapsed")
                        if target_name != "--請選擇--":
                            task_to_assign = un_list.pop(u_idx)
                            for target_p in results:
                                if target_p['name'] == target_name:
                                    target_p['tasks'].append(task_to_assign)
                                    target_p['out'] += task_to_assign['amount']; break
                            st.session_state.un_results = un_list
                            st.session_state.current_results = results; st.rerun()
                    with c_usplit:
                        if st.button("強制拆帳", key=f"u_split_{u_idx}"):
                            task_to_split = un_list.pop(u_idx)
                            rem, splits = task_to_split['amount'], 0
                            results.sort(key=lambda x: x['limit'], reverse=True)
                            for p in results:
                                if p['limit'] > 0 and rem > 0 and splits < 5:
                                    take = (min(rem, p['limit']) // 100 * 100) if (min(rem, p['limit']) < rem and splits < 4) else min(rem, p['limit'])
                                    if take > 0:
                                        p['tasks'].append({'info': f"{task_to_split['info']} (拆)", 'amount': int(take)})
                                        p['limit'] -= take; p['out'] += take; rem -= take; splits += 1
                            if rem > 0: un_list.insert(u_idx, {'info': task_to_split['info'], 'amount': rem})
                            st.session_state.un_results = un_list
                            st.session_state.current_results = results; st.rerun()

with tab2:
    if st.button("🔄 刷新"): st.rerun()
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(worksheet="Sheet1", ttl=0)
        st.dataframe(df.iloc[::-1], use_container_width=True)
    except: st.info("無資料")
