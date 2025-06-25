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

def find_best_box(profile_width, profile_height, cut_mm, unit_weight, max_weight, max_w, max_h, max_l):
    weight_item = unit_weight * (cut_mm/1000)
    max_items = max(1, int(max_weight // weight_item))
    best_box = None
    best_diff = float('inf')
    best_dev = float('inf')
    for count in range(max_items, 0, -1):
        for w_count, h_count in get_factor_pairs(count):
            for wc, hc in ((w_count, h_count), (h_count, w_count)):
                l_count = count // (wc*hc) if wc*hc > 0 else 0
                if wc*hc*l_count != count:
                    continue
                box_w = wc*profile_width
                box_h = hc*profile_height
                box_l = l_count*cut_mm
                if box_w > max_w or box_h > max_h or box_l > max_l:
                    continue
                wh_ratio = max(box_w, box_h) / min(box_w, box_h) if min(box_w, box_h) > 0 else 10
                if wh_ratio > 2:  # Avoid very flat or tall boxes
                    continue
                wh_diff = abs(box_w - box_h)
                deviation = max(box_w, box_h, box_l) - min(box_w, box_h, box_l)
                if wh_diff < best_diff or (wh_diff == best_diff and deviation < best_dev):
                    best_box = {'W': ceil(box_w), 'H': ceil(box_h), 'L': ceil(box_l), 'Fit': count}
                    best_diff, best_dev = wh_diff, deviation
        if best_box is not None:
            break
    return best_box

# ---------- 4. RUN BUTTON ----------
if st.button("🚀 Run Optimization", type="primary"):
    if editable_data.empty:
        st.warning("⚠️ Please upload or enter at least one profile to proceed.")
    else:
        with st.spinner("Optimizing... this may take a moment for large datasets"):
            results = []
            editable_data["Cut Length (mm)"] = editable_data.apply(lambda row: convert_to_mm(row["Cut Length"], row["Cut Unit"]), axis=1)
            editable_data["Weight Per Item"] = editable_data.apply(lambda row: row["Unit Weight (kg/m)"] * (row["Cut Length (mm)"]/1000), axis=1)

            # Table 1: Calculate box sizes per profile
            for _, row in editable_data.iterrows():
                if row["Cut Length (mm)"] <= 0 or row["Unit Weight (kg/m)"] <= 0:
                    continue
                profile_name = row["Profile Name"]
                unit_weight = row["Unit Weight (kg/m)"]
                profile_width = row["Profile Width (mm)"]
                profile_height = row["Profile Height (mm)"]
                cut_mm = row["Cut Length (mm)"]
                weight_item = row["Weight Per Item"]

                best_box = find_best_box(profile_width, profile_height, cut_mm, unit_weight,
                                         max_weight, max_gaylord_width, max_gaylord_height, max_gaylord_length)

                if best_box is None:
                    st.warning(f"⚠️ Could not fit '{profile_name}' into any box under constraints.")
                    continue

                vol_box = (best_box['W']*best_box['H']*best_box['L'])/1e9
                used_vol = best_box['Fit'] * (profile_width*profile_height*cut_mm)/1e9
                density = used_vol/vol_box if vol_box > 0 else 0
                density_comment = "🏆 Good density" if density >= 0.7 else "⚠️ Low density"

                w_fit = pallet_width//best_box['W'] if best_box['W'] > 0 else 0
                l_fit = pallet_length//best_box['L'] if best_box['L'] > 0 else 0
                h_fit = pallet_max_height//best_box['H'] if best_box['H'] > 0 else 0
                pallet_count = w_fit * l_fit * h_fit

                results.append({
                    "Profile Name": profile_name,
                    "Cut Length (mm)": round(cut_mm, 2),
                    "Items per Box": best_box['Fit'],
                    "Box W×H×L (mm)": f"{best_box['W']}×{best_box['H']}×{best_box['L']}",
                    "Density Comment": density_comment,
                    "Boxes per Pallet": pallet_count,
                    "Pallet Arrangement": f"{w_fit}×{l_fit}×{h_fit}" if pallet_count > 0 else "❌"
                })

            st.success("✅ Optimization Complete")
            df = pd.DataFrame(results)
            st.dataframe(df, use_container_width=True)

            out = BytesIO()
            with pd.ExcelWriter(out, engine='openpyxl') as writer:
                df.to_excel(writer,index=False,sheet_name='Results')
            st.download_button("📥 Download Results", out.getvalue(),
                               "results.xlsx",
                               "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

            # ---------- 5. SECOND TABLE: MOST OPTIMIZED BOX SIZES ----------
            st.subheader("📦 Most Optimized Box Sizes Table")

            # Prepare for second table
            box_summary = []

            # Find all profiles with weight < 50% max_weight
            light_profiles = editable_data[editable_data["Weight Per Item"] * editable_data["Cut Length (mm)"] / 1000 < 0.5 * max_weight]
            
            if not light_profiles.empty:
                # Find the most common profile dimensions among light profiles
                common_width = light_profiles["Profile Width (mm)"].mode()[0]
                common_height = light_profiles["Profile Height (mm)"].mode()[0]
                
                # Find best box dimensions for these common dimensions
                common_box = find_best_box(
                    common_width,
                    common_height,
                    max_gaylord_length,  # Using max length to find maximum possible fit
                    light_profiles["Unit Weight (kg/m)"].mean(),  # Average weight
                    max_weight,
                    max_gaylord_width,
                    max_gaylord_height,
                    max_gaylord_length
                )
                
                if common_box:
                    light_box_W = common_box['W']
                    light_box_H = common_box['H']
                else:
                    # Fallback to max dimensions if no box found
                    light_box_W = max_gaylord_width
                    light_box_H = max_gaylord_height
            else:
                # If no light profiles, use max dimensions
                light_box_W = max_gaylord_width
                light_box_H = max_gaylord_height

            for _, row in editable_data.iterrows():
                profile_name = row["Profile Name"]
                cut_mm = row["Cut Length (mm)"]
                unit_weight = row["Unit Weight (kg/m)"]
                weight_item = unit_weight * cut_mm / 1000
                profile_width = row["Profile Width (mm)"]
                profile_height = row["Profile Height (mm)"]
                
                # Check if this is a light profile
                is_light = weight_item * cut_mm / 1000 < 0.5 * max_weight
                
                if is_light:
                    # For light profiles: use common box width and height, length = cut length
                    box_w = light_box_W
                    box_h = light_box_H
                    box_l = cut_mm
                    
                    # Calculate how many fit in width and height
                    w_fit = box_w // profile_width if profile_width > 0 else 0
                    h_fit = box_h // profile_height if profile_height > 0 else 0
                    
                    if w_fit == 0 or h_fit == 0:
                        box_summary.append({
                            "Profile Name": profile_name,
                            "Cut Length (mm)": cut_mm,
                            "Optimized Box Size": "N/A",
                            "Profiles per Box": 0,
                            "Total Box Weight (kg)": 0,
                            "Boxes per Pallet": 0,
                            "Pallet Arrangement": "❌"
                        })
                        continue
                    
                    # Only 1 layer in length since box length = cut length
                    total_fit = w_fit * h_fit
                    
                    # Ensure we don't exceed weight limit
                    max_by_weight = int(max_weight // weight_item) if weight_item > 0 else 0
                    actual_fit = min(total_fit, max_by_weight) if max_by_weight > 0 else total_fit
                else:
                    # For heavy profiles: use original optimization
                    best_box = find_best_box(
                        profile_width, profile_height, cut_mm, unit_weight,
                        max_weight, max_gaylord_width, max_gaylord_height, max_gaylord_length
                    )
                    
                    if not best_box:
                        box_summary.append({
                            "Profile Name": profile_name,
                            "Cut Length (mm)": cut_mm,
                            "Optimized Box Size": "N/A",
                            "Profiles per Box": 0,
                            "Total Box Weight (kg)": 0,
                            "Boxes per Pallet": 0,
                            "Pallet Arrangement": "❌"
                        })
                        continue
                    
                    box_w = best_box['W']
                    box_h = best_box['H']
                    box_l = best_box['L']
                    actual_fit = best_box['Fit']
                
                # Calculate pallet information (same logic as first table)
                w_fit_pallet = pallet_width // box_w if box_w > 0 else 0
                l_fit_pallet = pallet_length // box_l if box_l > 0 else 0
                h_fit_pallet = pallet_max_height // box_h if box_h > 0 else 0
                pallet_count = w_fit_pallet * l_fit_pallet * h_fit_pallet
                
                box_summary.append({
                    "Profile Name": profile_name,
                    "Cut Length (mm)": cut_mm,
                    "Optimized Box Size": f"{box_w}×{box_h}×{box_l}",
                    "Profiles per Box": actual_fit,
                    "Total Box Weight (kg)": round(actual_fit * weight_item, 2),
                    "Boxes per Pallet": pallet_count,
                    "Pallet Arrangement": f"{w_fit_pallet}×{l_fit_pallet}×{h_fit_pallet}" if pallet_count > 0 else "❌"
                })

            if box_summary:
                st.dataframe(pd.DataFrame(box_summary), use_container_width=True)
            else:
                st.warning("❌ No profiles could be packed using selected optimized box sizes.")
