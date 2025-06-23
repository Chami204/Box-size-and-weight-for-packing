import streamlit as st
import pandas as pd
from math import ceil
from io import BytesIO

st.set_page_config(page_title="📦 Profile Packing Optimizer", page_icon="📦")
st.title("📦 Profile Packing Optimizer - Optimize Box & Pallet")

# 1. Gaylord Constraints
st.header("1️⃣ Gaylord Constraints")
col1, col2, col3 = st.columns(3)
with col1:
    max_weight = st.number_input("Maximum Gaylord Weight (kg)", min_value=0.1, value=1000.0)
with col2:
    max_gaylord_width = st.number_input("Maximum Gaylord Width (mm)", min_value=1, value=1200)
with col3:
    max_gaylord_height = st.number_input("Maximum Gaylord Height (mm)", min_value=1, value=1200)
max_gaylord_length = st.number_input("Maximum Gaylord Length (mm)", min_value=1, value=1200)

# 2. Pallet Constraints
st.header("2️⃣ Pallet Constraints")
col1, col2, col3 = st.columns(3)
with col1:
    pallet_width = st.number_input("Pallet Width (mm)", min_value=1, value=1100)
with col2:
    pallet_length = st.number_input("Pallet Length (mm)", min_value=1, value=1100)
with col3:
    pallet_max_height = st.number_input("Pallet Max Height (mm)", min_value=1, value=2000)

# 3. Input Table
def convert_to_mm(length, unit):
    return {'mm': length, 'cm': length*10, 'm': length*1000, 'inches': length*25.4}.get(unit, length)
st.header("3️⃣ Profile + Cut Lengths Input Table")
uploaded = st.file_uploader("Upload .csv or .xlsx", type=["csv","xlsx"])
if uploaded:
    df_input = pd.read_csv(uploaded) if uploaded.name.endswith('.csv') else pd.read_excel(uploaded)
else:
    df_input = pd.DataFrame({
        'Profile Name': ['A','B'],
        'Unit Weight (kg/m)': [1.5,2.0],
        'Profile Width (mm)': [50,60],
        'Profile Height (mm)': [60,70],
        'Cut Length': [585,737],
        'Cut Unit': ['mm','mm']
    })
    df_input = st.data_editor(df_input, use_container_width=True,
        column_config={'Cut Unit': st.column_config.SelectboxColumn(label='Unit', options=['mm','cm','m','inches'])})

# 4. Run Optimization
if st.button("🚀 Run Optimization"):
    if df_input.empty:
        st.warning("Enter data to proceed")
    else:
        # Preliminary best per-profile cross-section
        best_sections = []
        for _, r in df_input.iterrows():
            cut_mm = convert_to_mm(r['Cut Length'], r['Cut Unit'])
            uw = r['Unit Weight (kg/m)']
            pw = r['Profile Width (mm)']; ph = r['Profile Height (mm)']
            # number of items by dimension
            n_w = max_gaylord_width // pw
            n_h = max_gaylord_height // ph
            n_l = max_gaylord_length // cut_mm
            w_box = n_w * pw; h_box = n_h * ph
            best_sections.append((w_box, h_box))
        # find two most common
        sec_series = pd.Series(best_sections)
        common = sec_series.value_counts().index[:2]
        common_dims = list(common)

        results = []
        # evaluate each profile against common dims
        for _, r in df_input.iterrows():
            cut_mm = convert_to_mm(r['Cut Length'], r['Cut Unit'])
            uw = r['Unit Weight (kg/m)']
            pw = r['Profile Width (mm)']; ph = r['Profile Height (mm)']
            best_opt = None
            for w_box, h_box in common_dims:
                # profiles per box by dims
                n_w = w_box // pw
                n_h = h_box // ph
                n_l = max_gaylord_length // cut_mm
                count_dim = n_w * n_h * n_l
                # cap by weight
                max_by_wt = int(max_weight // (uw * (cut_mm/1000)))
                total = min(count_dim, max_by_wt)
                if total <= 0:
                    continue
                # density
                vol_box = (w_box * h_box * (n_l*cut_mm)) / 1e9
                used_vol = (pw * ph * cut_mm * total) / 1e9
                density = used_vol/vol_box if vol_box>0 else 0
                if best_opt is None or density > best_opt['density']:
                    best_opt = dict(
                        Profile=r['Profile Name'],
                        **{'Cut length/mm': cut_mm,
                           'Box Width/mm': w_box,
                           'Box Height/mm': h_box,
                           'Box Length/mm': n_l*cut_mm,
                           'Number of profiles/box': total,
                           'Box density comment': '🏆 Good density' if density>=0.7 else '⚠️ Low density',
                           'density': density}
                    )
            if best_opt:
                bw = best_opt['Box Width/mm']; bh = best_opt['Box Height/mm']; bl = best_opt['Box Length/mm']
                wf = pallet_width//bw; lf = pallet_length//bl; hf = pallet_max_height//bh
                boxes_pallet = wf*lf*hf
                best_opt.update({
                    'Pallet W (mm)': pallet_width,
                    'Pallet H (mm)': pallet_max_height,
                    'Pallet L (mm)': pallet_length,
                    'Number of Boxes/pallet': boxes_pallet,
                    'pallet density comment': '✅ Efficient pallet usage' if boxes_pallet>0 else '❌ Does not fit'
                })
                results.append(best_opt)

        df_out = pd.DataFrame(results)[[
            'Profile','Cut length/mm','Box Width/mm','Box Height/mm','Box Length/mm',
            'Number of profiles/box','Box density comment',
            'Pallet W (mm)','Pallet H (mm)','Pallet L (mm)',
            'Number of Boxes/pallet','pallet density comment'
        ]]
        st.success("✅ Optimization Complete")
        st.dataframe(df_out, use_container_width=True)

        outbuf=BytesIO()
        with pd.ExcelWriter(outbuf, engine='openpyxl') as w:
            df_out.to_excel(w, index=False, sheet_name='Results')
        st.download_button("📥 Download Results", outbuf.getvalue(), "optimized_packing.xlsx",
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
