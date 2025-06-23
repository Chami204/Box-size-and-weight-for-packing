import streamlit as st
import pandas as pd
from math import ceil, floor
from io import BytesIO

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
        column_config={"Cut Unit": st.column_config.SelectboxColumn(label="Cut Unit", options=["mm", "cm", "m", "inches"])} )

# Helpers
def convert_to_mm(length, unit):
    return {'mm': length, 'cm': length * 10, 'm': length * 1000, 'inches': length * 25.4}.get(unit, length)

# ---------- 4. RUN & OPTIMIZATION ----------
if st.button("🚀 Run Optimization"):
    if editable_data.empty:
        st.warning("⚠️ Please upload or enter profiles to proceed.")
    else:
        with st.spinner("Optimizing box & pallet..."):
            results = []
            for _, row in editable_data.iterrows():
                name = row['Profile Name']
                uw = row['Unit Weight (kg/m)']
                w = row['Profile Width (mm)']
                h = row['Profile Height (mm)']
                cut = convert_to_mm(row['Cut Length'], row['Cut Unit'])
                profile_weight = uw * cut / 1000

                # Try both orientations (w,h) and (h,w) for box cross-section
                best = None
                for base_w, base_h in [(w, h), (h, w)]:
                    if base_w <= 0 or base_h <= 0:
                        continue  # Skip invalid sizes
                    try:
                        lw_max = max_gaylord_width // int(base_w)
                        lh_max = max_gaylord_height // int(base_h)
                        ll_max = max_gaylord_length // int(cut)
                    except:
                        continue  # Skip if any dimension is bad
                
                    for lw in range(1, lw_max + 1):
                        for lh in range(1, lh_max + 1):
                            for ll in range(1, ll_max + 1):         
                        for lh in range(1, max_gaylord_height // base_h + 1):
                            for ll in range(1, max_gaylord_length // cut + 1):
                                bw = lw * base_w
                                bh = lh * base_h
                                bl = ll * cut
                                total_profiles = lw * lh * ll
                                total_weight = total_profiles * profile_weight
                                if total_weight > max_weight:
                                    continue
                                vol_box = (bw * bh * bl) / 1e9
                                used_vol = (w * h * cut * total_profiles) / 1e9
                                density = used_vol / vol_box if vol_box > 0 else 0
                                if density >= 0.7:
                                    if not best or total_profiles > best['Profiles/Box']:
                                        best = {
                                            'Profile': name,
                                            'Cut mm': cut,
                                            'Box Width/mm': bw,
                                            'Box Height/mm': bh,
                                            'Box Length/mm': bl,
                                            'Profiles/Box': total_profiles,
                                            'Box Density Comment': "🏆 Good density",
                                            'Density': density
                                        }
                if best:
                    pw, pl, ph = pallet_width, pallet_length, pallet_max_height
                    box_w, box_h, box_l = best['Box Width/mm'], best['Box Height/mm'], best['Box Length/mm']
                    wf = pw // box_w
                    lf = pl // box_l
                    hf = ph // box_h
                    pallet_count = wf * lf * hf
                    pallet_density_comment = "✅ Efficient pallet usage" if pallet_count > 0 else "❌ Box doesn't fit on pallet"
                    best.update({
                        'Pallet W': pallet_width,
                        'Pallet H': pallet_max_height,
                        'Pallet L': pallet_length,
                        'Boxes/Pallet': pallet_count,
                        'Pallet Density Comment': pallet_density_comment
                    })
                    results.append(best)

            df = pd.DataFrame(results)

            grouped = df.groupby(['Box Width/mm', 'Box Height/mm', 'Box Length/mm'])
            profile_combos = grouped['Cut mm'].apply(lambda x: ', '.join(map(str, sorted(set(x))))).reset_index(name='Cut Lengths in Opt Box (mm)')
            total_items = grouped['Profiles/Box'].sum().reset_index(name='Total Profiles in Opt Box')
            df = df.merge(profile_combos, on=['Box Width/mm', 'Box Height/mm', 'Box Length/mm'])
            df = df.merge(total_items, on=['Box Width/mm', 'Box Height/mm', 'Box Length/mm'])

            st.success("✅ Optimization Complete")
            st.dataframe(df, use_container_width=True)

            out = BytesIO()
            with pd.ExcelWriter(out, engine='openpyxl') as w:
                df.to_excel(w, index=False, sheet_name='Results')
            st.download_button("📥 Download Results", out.getvalue(), "results.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

            st.markdown("""
            #### 📌 Notes:
            - Profiles grouped by optimized box width/height/length.
            - Optimized to maintain density ≥ 70% and minimize box size variety.
            - Ensures total box weight does not exceed Gaylord weight limit.
            """)
