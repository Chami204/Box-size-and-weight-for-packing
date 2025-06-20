import streamlit as st
import pandas as pd
from math import ceil
from itertools import permutations

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

# Additional packing logic for cut length consolidation
st.header("4️⃣ Box Consolidation (Optional)")
if st.toggle("Enable Consolidated Packing by Profile", value=False):
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
                    vol = (l * w * h) / 1e9
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

        for idx, (density, group, weight) in enumerate(best_result, 1):
            cuts = ", ".join([g["original"] for g in group])
            st.info(
                f"**{profile_name}** - Box #{idx}: \n"
                f"Cut Lengths: {cuts}\n"
                f"Estimated Weight: {round(weight, 2)} kg\n"
                f"Box Density: {density*100:.1f}%"
            )
