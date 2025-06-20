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

def all_partitions(seq, max_parts):
    if len(seq) == 0:
        return []
    if max_parts == 1:
        return [[seq]]
    result = []
    for i in range(1, len(seq)):
        first = seq[:i]
        for rest in all_partitions(seq[i:], max_parts - 1):
            result.append([first] + rest)
    result.append([seq])
    return result

# ---------- 3. OPTIMIZATION ----------
if st.button("🚀 Run Optimization"):
    results = []

    grouped = editable_data.groupby("Profile Name")

    for profile_name, group in grouped:
        group = group.reset_index(drop=True)
        valid_rows = group[(group["Cut Length"] > 0) & (group["Unit Weight (kg/m)"] > 0)]
        num_lengths = len(valid_rows)

        if num_lengths == 0:
            continue

        unit_weight = valid_rows.iloc[0]["Unit Weight (kg/m)"]
        profile_width = valid_rows.iloc[0]["Profile Width (mm)"]
        profile_height = valid_rows.iloc[0]["Profile Height (mm)"]

        # Calculate max items across all cut lengths
        items_info = []
        for _, row in valid_rows.iterrows():
            cut_len_mm = convert_to_mm(row["Cut Length"], row["Cut Unit"])
            weight_per_item = unit_weight * (cut_len_mm / 1000)
            if weight_per_item == 0:
                continue
            max_items = int(max_weight // weight_per_item)
            items_info.append((cut_len_mm, weight_per_item, max_items, row["Cut Length"], row["Cut Unit"]))

        if not items_info:
            continue

        # Decide max boxes allowed
        if num_lengths <= 5:
            max_boxes = 1
        elif num_lengths <= 10:
            max_boxes = 2
        elif num_lengths <= 20:
            max_boxes = 3
        else:
            max_boxes = 4

        cut_length_objs = [{"cut_mm": i[0], "wt": i[1], "max_items": i[2], "original": f"{i[3]} {i[4]}"} for i in items_info]
        best_result = []
        best_density = 0

        partitions = all_partitions(cut_length_objs, max_boxes)
        for part in partitions:
            if len(part) > max_boxes:
                continue
            boxes = []
            valid = True
            for box_group in part:
                total_weight = 0
                total_volume = 0
                for item in box_group:
                    l = item["cut_mm"]
                    w = profile_width
                    h = profile_height
                    vol = (l * w * h) / 1e9  # m³
                    total_volume += vol
                    total_weight += item["wt"]
                max_box_vol = (max_gaylord_width * max_gaylord_height * max_gaylord_length) / 1e9
                density = total_volume / max_box_vol if max_box_vol else 0
                if total_weight > max_weight or density > 1:
                    valid = False
                    break
                boxes.append((density, box_group, total_weight))
            if valid:
                avg_density = sum([b[0] for b in boxes]) / len(boxes)
                if avg_density > best_density and avg_density >= 0.7:
                    best_result = boxes
                    best_density = avg_density

        if not best_result:
            st.warning(f"⚠️ Could not pack profile '{profile_name}' within {max_boxes} box(es) at ≥70% density.")
            continue

        # Format result
        for idx, (density, group, weight) in enumerate(best_result, 1):
            cuts = ", ".join([g["original"] for g in group])
            results.append({
                "Profile Name": profile_name,
                "Box #": idx,
                "Cut Lengths": cuts,
                "Items Fit in Box": len(group),
                "Box Density": f"{density*100:.1f}%",
                "Estimated Weight (kg)": round(weight, 2),
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
            file_name="Packing_Results_Grouped.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.warning("⚠️ No valid packing configuration found. Please check your inputs.")
