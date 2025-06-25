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

            # Get box info from table 1 in a dict by profile name for quick lookup
            box_dict = {row["Profile Name"]: row["Box W×H×L (mm)"] for _, row in df.iterrows()}

            # Find longest cut length row to fix that box as is
            longest_cut_idx = editable_data["Cut Length (mm)"].idxmax()
            longest_profile = editable_data.loc[longest_cut_idx]
            longest_box_size = box_dict.get(longest_profile["Profile Name"])
            if not longest_box_size:
                st.warning("⚠️ Could not find box size for the longest profile.")
                longest_box_size = f"{max_gaylord_width}×{max_gaylord_height}×{max_gaylord_length}"

            longest_W, longest_H, longest_L = map(int, longest_box_size.split("×"))

            for idx, row in editable_data.iterrows():
                profile_name = row["Profile Name"]
                cut_mm = row["Cut Length (mm)"]
                unit_weight = row["Unit Weight (kg/m)"]
                weight_item = unit_weight * cut_mm / 1000
                profile_width = row["Profile Width (mm)"]
                profile_height = row["Profile Height (mm)"]

                # For longest profile: use its box as is (width,height,length)
                if idx == longest_cut_idx:
                    fit = df.loc[df["Profile Name"] == profile_name, "Items per Box"].values[0]
                    box_w, box_h, box_l = longest_W, longest_H, longest_L
                    total_weight = fit * weight_item
                    box_summary.append({
                        "Profile Name": profile_name,
                        "Cut Length (mm)": cut_mm,
                        "Optimized Box Size": f"{box_w}×{box_h}×{box_l}",
                        "Profiles per Box": fit,
                        "Total Box Weight (kg)": round(total_weight, 2)
                    })
                    continue

                # For others: try packing into longest_W x longest_H box, length varies, calc how many fit similarly to table 1

                max_items = int(max_weight // weight_item)
                if max_items <= 0:
                    max_items = 1

                best_box = None
                best_diff = float('inf')
                best_dev = float('inf')

                # Try counts from max_items down to 1
                for count in range(max_items, 0, -1):
                    for w_count, h_count in get_factor_pairs(count):
                        for wc, hc in ((w_count, h_count), (h_count, w_count)):
                            # Use longest_W and longest_H as fixed width and height box sides,
                            # so total width = wc * profile_width must <= longest_W
                            # and total height = hc * profile_height must <= longest_H
                            total_w = wc * profile_width
                            total_h = hc * profile_height
                            if total_w > longest_W or total_h > longest_H:
                                continue
                            # Length count
                            l_count = count // (wc * hc) if (wc * hc) > 0 else 0
                            if wc * hc * l_count != count:
                                continue
                            total_l = l_count * cut_mm
                            if total_l > max_gaylord_length:
                                continue

                            wh_diff = abs(total_w - total_h)
                            deviation = max(total_w, total_h, total_l) - min(total_w, total_h, total_l)
                            if wh_diff < best_diff or (wh_diff == best_diff and deviation < best_dev):
                                best_box = {'W': ceil(total_w), 'H': ceil(total_h), 'L': ceil(total_l), 'Fit': count}
                                best_diff, best_dev = wh_diff, deviation
                    if best_box is not None:
                        break

                if best_box is None:
                    # fallback to original box from table 1
                    box_size_orig = box_dict.get(profile_name)
                    if box_size_orig:
                        W, H, L = map(int, box_size_orig.split("×"))
                        fit = df.loc[df["Profile Name"] == profile_name, "Items per Box"].values[0]
                        total_weight = fit * weight_item
                        box_summary.append({
                            "Profile Name": profile_name,
                            "Cut Length (mm)": cut_mm,
                            "Optimized Box Size": f"{W}×{H}×{L}",
                            "Profiles per Box": fit,
                            "Total Box Weight (kg)": round(total_weight, 2)
                        })
                    else:
                        st.warning(f"⚠️ Could not fit '{profile_name}' into any optimized box.")
                    continue

                total_weight = best_box['Fit'] * weight_item

                # If total weight less than 50% max weight, try to find better box by adjusting width & height
                if total_weight < 0.5 * max_weight:
                    # Find a better box with width/height adjustable but length fixed as best_box['L']
                    alternative_box = find_best_box(
                        profile_width, profile_height, best_box['L'], unit_weight,
                        max_weight, max_gaylord_width, max_gaylord_height, max_gaylord_length
                    )
                    if alternative_box:
                        total_weight_alt = alternative_box['Fit'] * weight_item
                        if total_weight_alt > total_weight:
                            best_box = alternative_box
                            total_weight = total_weight_alt

                box_summary.append({
                    "Profile Name": profile_name,
                    "Cut Length (mm)": cut_mm,
                    "Optimized Box Size": f"{best_box['W']}×{best_box['H']}×{best_box['L']}",
                    "Profiles per Box": best_box['Fit'],
                    "Total Box Weight (kg)": round(total_weight, 2)
                })

            if box_summary:
                st.dataframe(pd.DataFrame(box_summary), use_container_width=True)
            else:
                st.warning("❌ No profiles could be packed using selected optimized box sizes.")
