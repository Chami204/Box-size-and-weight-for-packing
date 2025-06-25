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

# ---------- Helpers ----------
def convert_to_mm(length, unit):
    return {"mm": length, "cm": length * 10, "m": length * 1000, "inches": length * 25.4}.get(unit, length)

def get_factor_pairs(n):
    pairs = []
    for i in range(1, int(n ** 0.5) + 1):
        if n % i == 0:
            pairs.append((i, n // i))
    return pairs

# ---------- 4. RUN BUTTON ----------
if st.button("🚀 Run Optimization", type="primary"):
    if editable_data.empty:
        st.warning("⚠️ Please upload or enter at least one profile to proceed.")
    else:
        with st.spinner("Optimizing..."):
            results = []
            editable_data["Cut Length (mm)"] = editable_data.apply(lambda row: convert_to_mm(row["Cut Length"], row["Cut Unit"]), axis=1)
            editable_data["Weight Per Item"] = editable_data.apply(lambda row: row["Unit Weight (kg/m)"] * (row["Cut Length (mm)"] / 1000), axis=1)
            box_map = {}

            # Find longest cut length
            longest_cut = editable_data["Cut Length (mm)"].max()
            longest_profile = editable_data.loc[editable_data["Cut Length (mm)"] == longest_cut].iloc[0]["Profile Name"]
            common_box_size = None

            for _, row in editable_data.iterrows():
                profile_name = row["Profile Name"]
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
                        for wc, hc in [(w_count, h_count), (h_count, w_count)]:
                            l_count = count // (wc * hc)
                            if wc * hc * l_count != count:
                                continue
                            box_w = wc * profile_width
                            box_h = hc * profile_height
                            box_l = l_count * cut_mm
                            if box_w > max_gaylord_width or box_h > max_gaylord_height or box_l > max_gaylord_length:
                                continue
                            wh_ratio = max(box_w, box_h) / min(box_w, box_h)
                            if wh_ratio > 2.5:
                                continue
                            wh_diff = abs(box_w - box_h)
                            deviation = max(box_w, box_h, box_l) - min(box_w, box_h, box_l)
                            if wh_diff < best_diff or (wh_diff == best_diff and deviation < best_dev):
                                best_box = {'W': ceil(box_w), 'H': ceil(box_h), 'L': ceil(box_l), 'Fit': count}
                                best_diff, best_dev = wh_diff, deviation
                                best_count = count
                    if best_box:
                        break

                total_box_weight = best_count * weight_item
                if profile_name == longest_profile:
                    common_box_size = (best_box['W'], best_box['H'])

                box_map[profile_name] = {
                    "box": best_box,
                    "cut_mm": cut_mm,
                    "weight_item": weight_item,
                    "count": best_count,
                    "total_weight": total_box_weight
                }

                results.append({
                    "Profile Name": profile_name,
                    "Cut Length (mm)": round(cut_mm, 2),
                    "Items per Box": best_box['Fit'],
                    "Box W×H×L (mm)": f"{best_box['W']}×{best_box['H']}×{best_box['L']}",
                    "Density Comment": "🏆 Good" if total_box_weight / max_weight >= 0.7 else "⚠️ Low",
                    "Boxes per Pallet": (pallet_width // best_box['W']) * (pallet_length // best_box['L']) * (pallet_max_height // best_box['H']),
                    "Pallet Arrangement": f"{pallet_width // best_box['W']}×{pallet_length // best_box['L']}×{pallet_max_height // best_box['H']}"
                })

            df = pd.DataFrame(results)
            st.success("✅ Optimization Complete")
            st.dataframe(df, use_container_width=True)

            out = BytesIO()
            with pd.ExcelWriter(out, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Results')
            st.download_button("📥 Download Results", out.getvalue(), "results.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

            # ---------- 5. SECOND TABLE: MODIFIED WIDTH & HEIGHT IF <50% ----------
            st.subheader("📦 Adjusted Box Sizes for Low Weight Profiles")
            box_summary = []

            for profile_name, vals in box_map.items():
                cut_mm = vals["cut_mm"]
                weight_item = vals["weight_item"]
                total_weight = vals["total_weight"]
                count = vals["count"]
                box = vals["box"]

                if total_weight < max_weight * 0.5 and profile_name != longest_profile and common_box_size:
                    new_w, new_h = common_box_size
                    area = new_w * new_h
                    item_area = editable_data.loc[editable_data["Profile Name"] == profile_name, "Profile Width (mm)"].values[0] * \
                                editable_data.loc[editable_data["Profile Name"] == profile_name, "Profile Height (mm)"].values[0]
                    items_fit = area // item_area
                    max_l_count = max_weight // (weight_item * items_fit) if weight_item > 0 and items_fit > 0 else 1
                    items_total = int(items_fit * max_l_count)
                    box_summary.append({
                        "Profile Name": profile_name,
                        "Cut Length (mm)": round(cut_mm, 2),
                        "Optimized Box Size": f"{new_w}×{new_h}×{ceil(cut_mm * max_l_count)}",
                        "Profiles per Box": items_total,
                        "Total Box Weight (kg)": round(items_total * weight_item, 2)
                    })
                else:
                    box_summary.append({
                        "Profile Name": profile_name,
                        "Cut Length (mm)": round(cut_mm, 2),
                        "Optimized Box Size": f"{box['W']}×{box['H']}×{box['L']}",
                        "Profiles per Box": count,
                        "Total Box Weight (kg)": round(total_weight, 2)
                    })

            st.dataframe(pd.DataFrame(box_summary), use_container_width=True)
