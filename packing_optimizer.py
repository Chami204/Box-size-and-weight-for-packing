import streamlit as st
import pandas as pd
from math import ceil
from io import BytesIO

st.set_page_config(page_title="📦 Profile Packing Optimizer", page_icon="📦")
st.title("📦 Profile Packing Optimizer - Maximize Fit by Weight")

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
uploaded_file = st.file_uploader("Upload Profile Data (.csv or .xlsx)", type=["csv", "xlsx"])
if uploaded_file:
    if uploaded_file.name.endswith(".csv"):
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
    editable_data = st.data_editor(
        default_data,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "Cut Unit": st.column_config.SelectboxColumn(
                label="Cut Unit",
                options=["mm", "cm", "m", "inches"]
            )
        }
    )

# Helpers

def convert_to_mm(length, unit):
    return {"mm": length, "cm": length*10, "m": length*1000, "inches": length*25.4}.get(unit, length)

def get_factor_pairs(n):
    pairs = []
    for i in range(1, int(n**0.5)+1):
        if n % i == 0:
            pairs.append((i, n//i))
    return pairs

# ---------- 4. RUN BUTTON ----------
if st.button("🚀 Run Optimization", type="primary"):
    if editable_data.empty:
        st.warning("⚠️ Please upload or enter at least one profile to proceed.")
    else:
        with st.spinner("Optimizing... this may take a moment for large datasets"):  # feedback
            results = []
            pallet_results = []

            for _, row in editable_data.iterrows():
                if row["Cut Length"] <= 0 or row["Unit Weight (kg/m)"] <= 0:
                    continue
                profile_name = row["Profile Name"]
                unit_weight = row["Unit Weight (kg/m)"]
                profile_width = row["Profile Width (mm)"]
                profile_height = row["Profile Height (mm)"]
                cut_mm = convert_to_mm(row["Cut Length"], row["Cut Unit"])
                weight_item = unit_weight * (cut_mm/1000)
                if weight_item == 0: continue
                max_items = int(max_weight // weight_item)
                if max_items == 0:
                    results.append({"Profile Name":profile_name, "Error":"Too heavy"})
                    continue

                # faster: use factor pairs for w and h
                best_box, best_diff, best_dev = None, float('inf'), float('inf')
                for w_count, h_count in get_factor_pairs(max_items):
                    for (wc, hc) in [(w_count, h_count), (h_count, w_count)]:
                        l_count = max_items//(wc*hc)
                        if wc*hc*l_count != max_items: continue
                        box_w = wc*profile_width; box_h = hc*profile_height; box_l = l_count*cut_mm
                        if box_w>max_gaylord_width or box_h>max_gaylord_height or box_l>max_gaylord_length: continue
                        wh_diff = abs(box_w-box_h); deviation=max(box_w,box_h,box_l)-min(box_w,box_h,box_l)
                        if wh_diff < best_diff or (wh_diff==best_diff and deviation<best_dev):
                            best_box={'W':ceil(box_w),'H':ceil(box_h),'L':ceil(box_l),'Fit':max_items}
                            best_diff, best_dev = wh_diff, deviation
                if not best_box:
                    results.append({"Profile Name":profile_name, "Error":"No fit"}); continue

                # pallet fit simple calculation
                w_fit = pallet_width//best_box['W']; l_fit=pallet_length//best_box['L']
                h_fit = pallet_max_height//best_box['H']
                pallet_count = w_fit*l_fit*h_fit
                results.append({"Profile":profile_name, "W":best_box['W'],"H":best_box['H'],"L":best_box['L'],"FitItems":best_box['Fit'],"PalletBoxes":pallet_count})

            st.success("✅ Optimization Complete")
            df = pd.DataFrame(results)
            st.dataframe(df, use_container_width=True)

            # download
            out = BytesIO()
            with pd.ExcelWriter(out, engine='openpyxl') as writer:
                df.to_excel(writer,index=False)
            st.download_button("📥 Download Results", out.getvalue(),"results.xlsx","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
