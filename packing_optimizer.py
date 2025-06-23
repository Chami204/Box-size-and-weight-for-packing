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

# ---------- 3. PROFILE + CUT LENGTH INPUT ----------
st.header("3️⃣ Profile + Cut Lengths Input Table")
uploaded_file = st.file_uploader("Upload Profile Data (.csv or .xlsx)", type=["csv","xlsx"])
if uploaded_file:
    if uploaded_file.name.endswith('.csv'):
        editable_data = pd.read_csv(uploaded_file)
    else:
        editable_data = pd.read_excel(uploaded_file)
else:
    default_data = pd.DataFrame({
        "Profile Name":["Profile A","Profile B"],
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

def get_factor_pairs(n):
    pairs = []
    for i in range(1, int(n ** 0.5) + 1):
        if n % i == 0:
            pairs.append((i, n // i))
    return pairs

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
                max_count = int(max_weight // weight_item)
                best = None
                for c in range(max_count, 0, -1):
                    for fw, fh in get_factor_pairs(c):
                        for wc, hc in ((fw, fh), (fh, fw)):
                            lc = c // (wc * hc) if wc * hc > 0 else 0
                            if wc * hc * lc != c:
                                continue
                            bw = wc * w
                            bh = hc * h
                            bl = lc * cut
                            if bw > max_gaylord_width or bh > max_gaylord_height or bl > max_gaylord_length:
                                continue
                            vol_box = (bw * bh * bl) / 1e9
                            used_vol = (w * h * cut * c) / 1e9
                            density = used_vol / vol_box if vol_box > 0 else 0
                            if best is None or density > best.get('Density', 0):
                                best = {
                                    'Profile': name,
                                    'Cut mm': cut,
                                    'Box Width/mm': ceil(bw),
                                    'Box Height/mm': ceil(bh),
                                    'Box Length/mm': ceil(bl),
                                    'Number of profiles/box': c,
                                    'Box Density Comment': "🏆 Good density" if density >= 0.7 else "⚠️ Low density",
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
                        'Number of Boxes/pallet': pallet_count,
                        'Pallet Density Comment': pallet_density_comment
                    })
                    results.append(best)

            df = pd.DataFrame(results)

            # KMeans clustering to reduce box variants
            try:
                from sklearn.cluster import KMeans
                coords = df[['Box Width/mm', 'Box Height/mm']]
                max_clusters = 3 if len(df) <= 10 else 5
                kmeans = KMeans(n_clusters=min(max_clusters, len(df)), random_state=42).fit(coords)
                centers = kmeans.cluster_centers_
                df['Box Width/mm'] = [int(ceil(centers[i][0])) for i in kmeans.labels_]
                df['Box Height/mm'] = [int(ceil(centers[i][1])) for i in kmeans.labels_]
            except:
                pass

            st.success("✅ Optimization Complete")
            st.dataframe(df, use_container_width=True)

            # download
            out = BytesIO()
            with pd.ExcelWriter(out, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Optimized Packing')
            st.download_button("📥 Download Results", out.getvalue(), "optimized_packing.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

            st.markdown("""
            #### 📌 Box & Pallet Packing Notes:
            - Boxes are stacked based on width × height consistency while allowing length variations.
            - Profiles with similar cross-sectional dimensions are grouped to reduce box variety and cost.
            - Pallet layout considers full utilization of available volume based on constraint dimensions.
            - Comments on density indicate space efficiency: high density = optimal packaging.
            """)
