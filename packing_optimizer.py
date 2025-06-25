import streamlit as st
import pandas as pd
from math import ceil
from io import BytesIO

st.set_page_config(page_title="📦 Profile Packing Optimizer", page_icon="📦")
st.title("📦 Profile Packing Optimizer")

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

def convert_to_mm(length, unit):
    return {"mm": length, "cm": length*10, "m": length*1000, "inches": length*25.4}.get(unit, length)

if st.button("🚀 Run Optimization", type="primary"):
    if editable_data.empty:
        st.warning("⚠️ Please upload or enter at least one profile to proceed.")
    else:
        with st.spinner("Optimizing... this may take a moment for large datasets"):
            editable_data["Cut Length (mm)"] = editable_data.apply(lambda row: convert_to_mm(row["Cut Length"], row["Cut Unit"]), axis=1)
            editable_data["Weight Per Item"] = editable_data.apply(lambda row: row["Unit Weight (kg/m)"] * (row["Cut Length (mm)"]/1000), axis=1)

            editable_data = editable_data.sort_values("Cut Length (mm)", ascending=False).reset_index(drop=True)

            # First profile's box size is taken as reference
            ref = editable_data.loc[0]
            ref_width = ref["Profile Width (mm)"]
            ref_height = ref["Profile Height (mm)"]

            box_varieties = [(ceil(ref_width), ceil(ref_height))]
            optimized_results = []

            for idx, row in editable_data.iterrows():
                name = row["Profile Name"]
                cut_mm = row["Cut Length (mm)"]
                unit_wt = row["Unit Weight (kg/m)"]
                p_w = row["Profile Width (mm)"]
                p_h = row["Profile Height (mm)"]
                weight_per_item = row["Weight Per Item"]

                best_fit = None
                max_items = 0

                for bw, bh in box_varieties:
                    w_fit = bw // p_w
                    h_fit = bh // p_h
                    items_per_layer = w_fit * h_fit
                    if items_per_layer == 0:
                        continue
                    max_layers = int(max_weight // (items_per_layer * weight_per_item))
                    if max_layers <= 0:
                        continue

                    items = items_per_layer * max_layers
                    box_l = ceil(max_layers * cut_mm)

                    if bw <= max_gaylord_width and bh <= max_gaylord_height and box_l <= max_gaylord_length:
                        if items > max_items:
                            max_items = items
                            best_fit = (bw, bh, box_l)

                # If no fit found, try to define another box variety (max 2 for <10 profiles)
                if not best_fit and (len(box_varieties) < 2 if len(editable_data) < 10 else len(box_varieties) < 3):
                    bw, bh = ceil(p_w), ceil(p_h)
                    w_fit = bw // p_w
                    h_fit = bh // p_h
                    items_per_layer = w_fit * h_fit
                    max_layers = int(max_weight // (items_per_layer * weight_per_item))
                    max_layers = max(1, max_layers)
                    box_l = ceil(max_layers * cut_mm)
                    if bw <= max_gaylord_width and bh <= max_gaylord_height and box_l <= max_gaylord_length:
                        best_fit = (bw, bh, box_l)
                        max_items = items_per_layer * max_layers
                        box_varieties.append((bw, bh))

                if best_fit:
                    optimized_results.append({
                        "Profile Name": name,
                        "Cut Length (mm)": cut_mm,
                        "Optimized Box Size (mm)": f"{best_fit[0]}x{best_fit[1]}x{best_fit[2]}",
                        "Items per Box": max_items
                    })
                else:
                    optimized_results.append({
                        "Profile Name": name,
                        "Cut Length (mm)": cut_mm,
                        "Optimized Box Size (mm)": "❌ Cannot fit",
                        "Items per Box": 0
                    })

            st.subheader("📦 Most Optimized Box Sizes Table")
            result_df = pd.DataFrame(optimized_results)
            st.dataframe(result_df, use_container_width=True)

            out = BytesIO()
            with pd.ExcelWriter(out, engine='openpyxl') as writer:
                result_df.to_excel(writer, index=False, sheet_name='Optimized Boxes')
            st.download_button("📅 Download Optimized Sizes", out.getvalue(), "optimized_box_sizes.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
