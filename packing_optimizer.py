import streamlit as st
import pandas as pd
from math import ceil
from itertools import permutations

st.set_page_config(page_title="📦 Profile Packing Optimizer", page_icon="📦")
st.title("📦 Profile Packing Optimizer - Maximize Fit by Weight")

# ---------- 1. GAYLORD CONSTRAINTS ----------
st.header("1️⃣ Gaylord Constraints")

max_weight = st.number_input("Maximum Gaylord Weight (kg)", min_value=0.1, format="%.2f")
max_gaylord_width = st.number_input("Maximum Gaylord Width (mm)", min_value=1)
max_gaylord_height = st.number_input("Maximum Gaylord Height (mm)", min_value=1)
max_gaylord_length = st.number_input("Maximum Gaylord Length (mm)", min_value=1)

# ---------- 2. PROFILE + CUT LENGTH INPUT ----------
st.header("2️⃣ Profile + Cut Lengths Input Table")

default_data = pd.DataFrame({
    "Profile Name": [""],
    "Unit Weight (kg/m)": [0.0],
    "Profile Width (mm)": [0.0],
    "Profile Height (mm)": [0.0],
    "Cut Length": [0.0],
    "Cut Unit": ["mm"],
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
    return {
        "mm": length,
        "cm": length * 10,
        "m": length * 1000,
        "inches": length * 25.4
    }.get(unit, length)

# ---------- 3. OPTIMIZATION ----------
if st.button("🚀 Run Optimization"):
    results = []

    for _, row in editable_data.iterrows():
        if row["Cut Length"] <= 0 or row["Unit Weight (kg/m)"] <= 0:
            continue

        profile_name = row["Profile Name"]
        unit_weight = row["Unit Weight (kg/m)"]
        profile_width = row["Profile Width (mm)"]
        profile_height = row["Profile Height (mm)"]
        cut_len_mm = convert_to_mm(row["Cut Length"], row["Cut Unit"])
        original = f"{row['Cut Length']} {row['Cut Unit']}"

        weight_per_item = unit_weight * (cut_len_mm / 1000)
        if weight_per_item == 0:
            continue

        max_items = int(max_weight // weight_per_item)
        if max_items == 0:
            # Cannot fit even one item due to weight
            results.append({
                "Profile Name": profile_name,
                "Cut Length": original,
                "Cut Length (mm)": round(cut_len_mm, 2),
                "Weight per Item (kg)": round(weight_per_item, 3),
                "Max Items per Gaylord": max_items,
                "Box Width (mm)": "❌",
                "Box Height (mm)": "❌",
                "Box Length (mm)": "❌",
                "Items Fit in Box": 0,
                "W x H x L Arrangement": "-",
                "Orientation": "-",
                "Box Cube Deviation (mm)": "-",
                "Fits Pallet (≤1100x700)": "❌"
            })
            continue

        best_box = None
        min_wh_diff = float('inf')   # minimum width-height difference
        min_deviation = float('inf') # minimum cube deviation

        for w_count in range(1, max_items + 1):
            for h_count in range(1, max_items + 1):
                if max_items % (w_count * h_count) != 0:
                    continue
                l_count = max_items // (w_count * h_count)

                dims = {
                    'W': w_count * profile_width,
                    'H': h_count * profile_height,
                    'L': l_count * cut_len_mm
                }

                for orientation in permutations(['W', 'H', 'L']):
                    box_w = dims[orientation[0]]
                    box_h = dims[orientation[1]]
                    box_l = dims[orientation[2]]

                    # Check max width, height, and length constraints
                    if box_w > max_gaylord_width or box_h > max_gaylord_height or box_l > max_gaylord_length:
                        continue

                    wh_diff = abs(box_w - box_h)
                    deviation = max(box_w, box_h, box_l) - min(box_w, box_h, box_l)

                    # Priority 1: minimize width-height difference
                    # Priority 2: minimize overall cube deviation
                    if wh_diff < min_wh_diff or (wh_diff == min_wh_diff and deviation < min_deviation):
                        min_wh_diff = wh_diff
                        min_deviation = deviation
                        best_box = {
                            "Box Width (mm)": int(ceil(box_w)),
                            "Box Height (mm)": int(ceil(box_h)),
                            "Box Length (mm)": int(ceil(box_l)),
                            "Fit Items": max_items,
                            "W Count": w_count,
                            "H Count": h_count,
                            "L Count": l_count,
                            "Orientation": f"{orientation[0]} x {orientation[1]} x {orientation[2]}"
                        }

        if best_box is None:
            results.append({
                "Profile Name": profile_name,
                "Cut Length": original,
                "Cut Length (mm)": round(cut_len_mm, 2),
                "Weight per Item (kg)": round(weight_per_item, 3),
                "Max Items per Gaylord": max_items,
                "Box Width (mm)": "❌",
                "Box Height (mm)": "❌",
                "Box Length (mm)": "❌",
                "Items Fit in Box": 0,
                "W x H x L Arrangement": "-",
                "Orientation": "-",
                "Box Cube Deviation (mm)": "-",
                "Fits Pallet (≤1100x700)": "❌"
            })
            continue

        fits_pallet = best_box["Box Width (mm)"] <= 1100 and best_box["Box Height (mm)"] <= 700

        results.append({
            "Profile Name": profile_name,
            "Cut Length": original,
            "Cut Length (mm)": round(cut_len_mm, 3),
            "Weight per Item (kg)": round(weight_per_item, 3),
            "Max Items per Gaylord": max_items,
            "Box Width (mm)": best_box["Box Width (mm)"],
            "Box Height (mm)": best_box["Box Height (mm)"],
            "Box Length (mm)": best_box["Box Length (mm)"],
            "Items Fit in Box": best_box["Fit Items"],
            "W x H x L Arrangement": f"{best_box['W Count']} x {best_box['H Count']} x {best_box['L Count']}",
            "Orientation": best_box["Orientation"],
            "Box Cube Deviation (mm)": int(min_deviation),
            "Fits Pallet (≤1100x700)": "✅" if fits_pallet else "❌"
        })

    if results:
        df = pd.DataFrame(results)
        st.success("✅ Optimization Complete")
        st.dataframe(df, use_container_width=True)

        from io import BytesIO
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name="Packing Plan")
        st.download_button(
            label="📥 Download Excel",
            data=output.getvalue(),
            file_name=f"Packing_Results.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.warning("⚠️ No valid packing configuration found. Please check your inputs.")
