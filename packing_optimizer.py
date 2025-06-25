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
        with st.spinner("Optimizing... this may take a moment for large datasets"):
            results = []
            editable_data["Cut Length (mm)"] = editable_data.apply(lambda row: convert_to_mm(row["Cut Length"], row["Cut Unit"]), axis=1)
            editable_data["Weight Per Item"] = editable_data.apply(lambda row: row["Unit Weight (kg/m)"] * (row["Cut Length (mm)"]/1000), axis=1)

            for _, row in editable_data.iterrows():
                if row["Cut Length (mm)"] <= 0 or row["Unit Weight (kg/m)"] <= 0:
                    continue
                profile_name = row["Profile Name"]
                unit_weight = row["Unit Weight (kg/m)"]
                profile_width = row["Profile Width (mm)"]
                profile_height = row["Profile Height (mm)"]
                cut_mm = row["Cut Length (mm)"]
                weight_item = row["Weight Per Item"]
                max_items = int(max_weight // weight_item)
                if max_items <= 0:
                    max_items = 1

                best_box = None
                best_diff = float('inf')
                best_dev = float('inf')
                best_count = 0
                for count in range(max_items, 0, -1):
                    for w_count, h_count in get_factor_pairs(count):
                        for wc, hc in ((w_count, h_count), (h_count, w_count)):
                            l_count = count // (wc*hc) if wc*hc>0 else 0
                            if wc*hc*l_count != count:
                                continue
                            box_w = wc*profile_width; box_h = hc*profile_height; box_l = l_count*cut_mm
                            if box_w>max_gaylord_width or box_h>max_gaylord_height or box_l>max_gaylord_length:
                                continue
                            wh_diff = abs(box_w-box_h)
                            deviation = max(box_w,box_h,box_l)-min(box_w,box_h,box_l)
                            if wh_diff < best_diff or (wh_diff==best_diff and deviation<best_dev):
                                best_box = {'W':ceil(box_w),'H':ceil(box_h),'L':ceil(box_l),'Fit':count}
                                best_diff, best_dev = wh_diff, deviation
                                best_count = count
                    if best_box is not None:
                        break

                if best_box is None:
                    st.warning(f"⚠️ Could not fit '{profile_name}' into any box under constraints.")
                    continue

                vol_box = (best_box['W']*best_box['H']*best_box['L'])/1e9
                used_vol = best_count * (profile_width*profile_height*cut_mm)/1e9
                density = used_vol/vol_box if vol_box>0 else 0
                density_comment = "🏆 Good density" if density>=0.7 else "⚠️ Low density"

                w_fit = pallet_width//best_box['W'] if best_box['W']>0 else 0
                l_fit = pallet_length//best_box['L'] if best_box['L']>0 else 0
                h_fit = pallet_max_height//best_box['H'] if best_box['H']>0 else 0
                pallet_count = w_fit * l_fit * h_fit

                results.append({
                    "Profile Name": profile_name,
                    "Cut Length (mm)": round(cut_mm,2),
                    "Items per Box": best_box['Fit'],
                    "Box W×H×L (mm)": f"{best_box['W']}×{best_box['H']}×{best_box['L']}",
                    "Density Comment": density_comment,
                    "Boxes per Pallet": pallet_count,
                    "Pallet Arrangement": f"{w_fit}×{l_fit}×{h_fit}" if pallet_count>0 else "❌"
                })

            st.success("✅ Optimization Complete")
            df = pd.DataFrame(results)
            st.dataframe(df, use_container_width=True)

            out = BytesIO()
            with pd.ExcelWriter(out, engine='openpyxl') as writer:
                df.to_excel(writer,index=False,sheet_name='Results')
            st.download_button("📥 Download Results", out.getvalue(),"results.xlsx","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

            # ---------- NEW: MOST OPTIMIZED BOX SIZES TABLE ----------
            st.subheader("📦 Most Optimized Box Sizes Table")
            optimized_results = []
            base_boxes = df.sort_values("Cut Length (mm)", ascending=False)["Box W×H×L (mm)"].unique()
            used_varieties = []

            for box in base_boxes:
                bw, bh, _ = map(int, box.split("×"))
                if (bw, bh) in used_varieties:
                    continue
                temp = []
                for _, row in editable_data.iterrows():
                    p_w = row["Profile Width (mm)"]
                    p_h = row["Profile Height (mm)"]
                    cut_len = row["Cut Length (mm)"]
                    weight_per_item = row["Weight Per Item"]
                    w_fit = bw // p_w
                    h_fit = bh // p_h
                    per_layer = w_fit * h_fit
                    if per_layer == 0:
                        continue
                    max_layers = int(max_weight // (per_layer * weight_per_item))
                    if max_layers == 0:
                        continue
                    items = per_layer * max_layers
                    bl = ceil(cut_len * max_layers)
                    box_weight = round(items * weight_per_item, 2)
                    if bw <= max_gaylord_width and bh <= max_gaylord_height and bl <= max_gaylord_length:
                        temp.append({
                            "Profile Name": row["Profile Name"],
                            "Cut Length (mm)": cut_len,
                            "Optimized Box Size (mm)": f"{bw}×{bh}×{bl}",
                            "Items per Box": items,
                            "Total Box Weight (kg)": box_weight
                        })
                if temp:
                    optimized_results.extend(temp)
                    used_varieties.append((bw,bh))
                if len(used_varieties) >= (2 if len(editable_data)<10 else 3):
                    break

            df2 = pd.DataFrame(optimized_results)
            st.dataframe(df2, use_container_width=True)
            out2 = BytesIO()
            with pd.ExcelWriter(out2, engine='openpyxl') as writer:
                df2.to_excel(writer, index=False, sheet_name='Optimized Box Sizes')
            st.download_button("📥 Download Optimized Box Sizes", out2.getvalue(),"optimized_box_sizes.xlsx","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
