import streamlit as st
import pandas as pd
from math import ceil
from io import BytesIO
from collections import Counter

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

default_data = pd.DataFrame({
    "Profile Name": ["Profile A", "Profile B", "Profile C"],
    "Unit Weight (kg/m)": [1.5, 2.0, 1.8],
    "Profile Width (mm)": [50.0, 60.0, 52.0],
    "Profile Height (mm)": [60.0, 70.0, 62.0],
    "Cut Length": [2500, 3000, 2700],
    "Cut Unit": ["mm", "mm", "mm"],
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

# ---------- HELPERS ----------
def convert_to_mm(length, unit):
    return {"mm": length, "cm": length*10, "m": length*1000, "inches": length*25.4}.get(unit, length)

def get_factor_pairs(n):
    pairs = []
    for i in range(1, int(n**0.5)+1):
        if n % i == 0:
            pairs.append((i, n//i))
    return pairs

def get_common_box_sizes(df, limit=3):
    rounded_sizes = [(round(w / 10) * 10, round(h / 10) * 10) for w, h in zip(df["Profile Width (mm)"], df["Profile Height (mm)"])]
    most_common = Counter(rounded_sizes).most_common(limit)
    return [size for size, _ in most_common]

# ---------- 4. RUN OPTIMIZATION ----------
if st.button("🚀 Run Optimization", type="primary"):
    if editable_data.empty:
        st.warning("⚠️ Please enter at least one profile.")
    else:
        with st.spinner("Optimizing..."):
            results = []
            editable_data["Cut Length (mm)"] = editable_data.apply(lambda row: convert_to_mm(row["Cut Length"], row["Cut Unit"]), axis=1)
            common_box_sizes = get_common_box_sizes(editable_data, limit=3)

            for _, row in editable_data.iterrows():
                profile_name = row["Profile Name"]
                unit_weight = row["Unit Weight (kg/m)"]
                profile_width = row["Profile Width (mm)"]
                profile_height = row["Profile Height (mm)"]
                cut_mm = row["Cut Length (mm)"]

                weight_item = unit_weight * (cut_mm / 1000)
                max_items = int(max_weight // weight_item)
                if max_items <= 0:
                    max_items = 1

                best_box = None
                best_density = 0
                best_count = 0
                shared_used = False

                # First Try Shared Box Sizes
                for box_w, box_h in common_box_sizes:
                    items_per_layer = (box_w // profile_width) * (box_h // profile_height)
                    if items_per_layer == 0:
                        continue
                    l_count = max_items // items_per_layer
                    count = items_per_layer * l_count
                    box_l = l_count * cut_mm

                    if box_w > max_gaylord_width or box_h > max_gaylord_height or box_l > max_gaylord_length or count == 0:
                        continue

                    box_vol = (box_w * box_h * box_l) / 1e9
                    used_vol = count * (profile_width * profile_height * cut_mm) / 1e9
                    density = used_vol / box_vol if box_vol > 0 else 0

                    if density > best_density:
                        best_density = density
                        best_box = {'W': box_w, 'H': box_h, 'L': ceil(box_l)}
                        best_count = count
                        shared_used = True

                # Fallback: Try Custom Dimensions
                if not best_box:
                    for count in range(max_items, 0, -1):
                        for w_count, h_count in get_factor_pairs(count):
                            for wc, hc in ((w_count, h_count), (h_count, wc)):
                                l_count = count // (wc * hc) if wc * hc > 0 else 0
                                if wc * hc * l_count != count:
                                    continue
                                box_w = wc * profile_width
                                box_h = hc * profile_height
                                box_l = l_count * cut_mm
                                if box_w > max_gaylord_width or box_h > max_gaylord_height or box_l > max_gaylord_length:
                                    continue
                                box_vol = (box_w * box_h * box_l) / 1e9
                                used_vol = count * (profile_width * profile_height * cut_mm) / 1e9
                                density = used_vol / box_vol if box_vol > 0 else 0
                                if density > best_density:
                                    best_box = {'W': ceil(box_w), 'H': ceil(box_h), 'L': ceil(box_l)}
                                    best_density = density
                                    best_count = count
                        if best_box:
                            break

                density_comment = "🏆 Good density" if best_density >= 0.7 else "⚠️ Low density"
                box_type = "✅ Shared Box" if shared_used else "🛠️ Custom Box"

                # Pallet fitting
                w_fit = pallet_width // best_box['W']
                l_fit = pallet_length // best_box['L']
                h_fit = pallet_max_height // best_box['H']
                pallet_count = w_fit * l_fit * h_fit

                results.append({
                    "Profile Name": profile_name,
                    "Cut Length (mm)": round(cut_mm, 2),
                    "Items per Box": best_count,
                    "Box W×H×L (mm)": f"{best_box['W']}×{best_box['H']}×{best_box['L']}",
                    "Box Type": box_type,
                    "Density Comment": density_comment,
                    "Boxes per Pallet": pallet_count,
                    "Pallet Arrangement": f"{w_fit}×{l_fit}×{h_fit}" if pallet_count > 0 else "❌"
                })

            st.success("✅ Optimization Complete")
            df = pd.DataFrame(results)
            st.dataframe(df, use_container_width=True)

            # Export to Excel
            out = BytesIO()
            with pd.ExcelWriter(out, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Results')
            st.download_button("📥 Download Results", out.getvalue(), "results.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
