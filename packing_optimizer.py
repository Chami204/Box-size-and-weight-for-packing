import streamlit as st
import pandas as pd
from math import ceil
from itertools import permutations
from io import BytesIO

try:
    import matplotlib.pyplot as plt
except ImportError:
    plt = None
    st.warning("matplotlib is not installed. Pallet visualization is disabled.")

st.set_page_config(page_title="📦 Profile Packing Optimizer", page_icon="📦")
st.title("📦 Profile Packing Optimizer - Maximize Fit by Weight & Pallet Layout")

# ---------- 1. GAYLORD CONSTRAINTS ----------
st.header("1️⃣ Gaylord Constraints")
col1, col2, col3 = st.columns(3)
with col1:
    max_weight = st.number_input("Maximum Gaylord Weight (kg)", min_value=0.1, value=1000.0, format="%.2f")
with col2:
    max_gaylord_width = st.number_input("Maximum Gaylord Width (mm)", min_value=1, value=1200)
with col3:
    max_gaylord_height = st.number_input("Maximum Gaylord Height (mm)", min_value=1, value=1200)
max_gaylord_length = st.number_input("Maximum Gaylord Length (mm)", min_value=1, value=1200)

# ---------- 2. PALLET CONSTRAINTS ----------
st.header("2️⃣ Pallet Constraints")
col1, col2, col3 = st.columns(3)
with col1:
    pallet_width = st.number_input("Pallet Width (mm)", min_value=1, value=1100)
with col2:
    pallet_length = st.number_input("Pallet Length (mm)", min_value=1, value=1100)
with col3:
    pallet_max_height = st.number_input("Pallet Max Height (mm)", min_value=1, value=2000)
used_pallet_size = f"{pallet_width}×{pallet_length}×{pallet_max_height} mm"

# ---------- 3. PROFILE + CUT LENGTH INPUT ----------
st.header("3️⃣ Profile + Cut Lengths Input Table")
uploaded_file = st.file_uploader("Upload Profile Data (.csv or .xlsx)", type=["csv", "xlsx"])
if uploaded_file:
    if uploaded_file.name.endswith('.csv'):
        editable_data = pd.read_csv(uploaded_file)
    else:
        editable_data = pd.read_excel(uploaded_file)
else:
    default_data = pd.DataFrame({
        "Profile Name": ["Profile A", "Profile B"],
        "Unit Weight (kg/m)": [1.5, 2.0],
        "Profile Width (mm)": [50.0, 60.0],
        "Profile Height (mm)": [60.0, 70.0],
        "Cut Length": [2500, 3000],
        "Cut Unit": ["mm", "mm"],
    })
    editable_data = st.data_editor(default_data, num_rows='dynamic', use_container_width=True,
        column_config={"Cut Unit": st.column_config.SelectboxColumn(label="Cut Unit", options=["mm", "cm", "m", "inches"])})

# Helpers
def convert_to_mm(length, unit):
    return {'mm': length, 'cm': length * 10, 'm': length * 1000, 'inches': length * 25.4}.get(unit, length)

# ---------- 4. RUN & OPTIMIZATION ----------
if st.button("🚀 Run Optimization"):
    if editable_data.empty:
        st.warning("⚠️ Please upload or enter profiles to proceed.")
    else:
        with st.spinner("Optimizing box & pallet...\nThis may take a moment."):
            results = []
            for _, row in editable_data.iterrows():
                if row['Cut Length'] <= 0 or row['Unit Weight (kg/m)'] <= 0:
                    continue
                name = row['Profile Name']
                uw = row['Unit Weight (kg/m)']
                w = row['Profile Width (mm)']
                h = row['Profile Height (mm)']
                cut = convert_to_mm(row['Cut Length'], row['Cut Unit'])
                weight_item = uw * (cut / 1000)

                best = None
                for base_w, base_h in [(w, h), (h, w)]:
                    if base_w <= 0 or base_h <= 0:
                        continue
                    lw_max = max_gaylord_width // base_w
                    lh_max = max_gaylord_height // base_h
                    ll_max = max_gaylord_length // cut
                    for lw in range(1, lw_max + 1):
                        for lh in range(1, lh_max + 1):
                            for ll in range(1, ll_max + 1):
                                bw = lw * base_w
                                bh = lh * base_h
                                bl = ll * cut
                                total_profiles = lw * lh * ll
                                total_weight = total_profiles * weight_item
                                if total_weight > max_weight:
                                    continue
                                vol_box = (bw * bh * bl) / 1e9
                                used_vol = (w * h * cut * total_profiles) / 1e9
                                density = used_vol / vol_box if vol_box > 0 else 0
                                if density >= 0.7:
                                    if not best or total_profiles > best['Items/Box']:
                                        best = {
                                            'Profile': name,
                                            'Cut mm': cut,
                                            'Items/Box': total_profiles,
                                            'Box W×H×L mm': f"{ceil(bw)}×{ceil(bh)}×{ceil(bl)}",
                                            'Density': f"{density * 100:.1f}%",
                                            'Density Comment': "🏆 Good density",
                                            'W': ceil(bw),
                                            'H': ceil(bh),
                                            'L': ceil(bl)
                                        }
                if not best:
                    st.warning(f"⚠️ '{name}' cannot fit any box under constraints.")
                    continue

                wf = pallet_width // best['W']
                lf = pallet_length // best['L']
                hf = pallet_max_height // best['H']
                pal_count = wf * lf * hf
                best['Boxes/Pallet'] = pal_count
                best['Pallet Layout'] = f"{wf}×{lf}×{hf}"
                best['Used Pallet Size'] = used_pallet_size

                results.append(best)

            df = pd.DataFrame(results)
            grouped = df.groupby(['W', 'H', 'L'])
            cut_lengths = grouped['Cut mm'].apply(lambda x: ', '.join(str(int(c)) for c in sorted(x.unique()))).reset_index(name='Cut Lengths in Opt Box')
            total_items = grouped['Items/Box'].sum().reset_index(name='Count in Opt Box')
            df = df.merge(cut_lengths, on=['W', 'H', 'L'])
            df = df.merge(total_items, on=['W', 'H', 'L'])
            df['Opt Volume m3'] = (df['W'] * df['H'] * df['L']) / 1e9
            df['Used Volume m3'] = df['Cut mm'] * df['Items/Box'] * editable_data['Profile Width (mm)'].mean() * editable_data['Profile Height (mm)'].mean() / 1e9
            df['Opt Density'] = (df['Used Volume m3'] / df['Opt Volume m3']).clip(upper=1.0)
            df['Opt Density Comment'] = df['Opt Density'].apply(lambda d: "🏆 Good density" if d >= 0.7 else "⚠️ Low density")

            st.success("✅ Optimization Complete")
            st.dataframe(df, use_container_width=True)

            out = BytesIO()
            with pd.ExcelWriter(out, engine='openpyxl') as w:
                df.to_excel(w, index=False, sheet_name='Results')
            st.download_button("📥 Download Results", out.getvalue(), "results.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        st.header("📊 Pallet Layout Visualization")
        idx = st.selectbox("Select profile to visualize:", options=df.index, format_func=lambda i: df.at[i, 'Profile'])
        if st.button("🔍 Show Layout"):
            row = df.loc[idx]
            wf, lf, hf = map(int, row['Pallet Layout'].split('×'))
            bw, bh = map(int, row['Box W×H×L mm'].split('×')[:2])
            fig, ax = plt.subplots()
            ax.add_patch(plt.Rectangle((0, 0), pallet_width, pallet_length, fill=False, edgecolor='black', linewidth=2))
            for i in range(wf):
                for j in range(lf):
                    ax.add_patch(plt.Rectangle((i * bw, j * bh), bw, bh, fill=True, facecolor='skyblue', edgecolor='white'))
            ax.set_xlim(0, pallet_width)
            ax.set_ylim(0, pallet_length)
            ax.set_aspect('equal', 'box')
            ax.set_xlabel('Width mm')
            ax.set_ylabel('Length mm')
            st.pyplot(fig)

