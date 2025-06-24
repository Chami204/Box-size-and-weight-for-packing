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
default_data = pd.DataFrame({
    "Profile Name": ["Profile A", "Profile A", "Profile A"],
    "Unit Weight (kg/m)": [1.5, 1.5, 1.5],
    "Profile Width (mm)": [50.0, 50.0, 50.0],
    "Profile Height (mm)": [60.0, 60.0, 60.0],
    "Cut Length": [1000, 1500, 2500],
    "Cut Unit": ["mm", "mm", "mm"]
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

def get_box_fit(width, height, box_w, box_h):
    return (box_w // width) * (box_h // height)

# ---------- 4. RUN BUTTON ----------
if st.button("🚀 Run Optimization", type="primary"):
    if editable_data.empty:
        st.warning("⚠️ Please enter at least one profile to proceed.")
    else:
        with st.spinner("Optimizing with intelligent logic..."):
            results = []
            editable_data["Cut Length (mm)"] = editable_data.apply(lambda row: convert_to_mm(row["Cut Length"], row["Cut Unit"]), axis=1)
            profiles = editable_data.to_dict("records")

            for i, p1 in enumerate(profiles):
                profile_name = p1["Profile Name"]
                profile_width = p1["Profile Width (mm)"]
                profile_height = p1["Profile Height (mm)"]

                # Evaluate single cut length option first
                cut_length = p1["Cut Length (mm)"]
                unit_weight = p1["Unit Weight (kg/m)"]
                count_fit = get_box_fit(profile_width, profile_height, max_gaylord_width, max_gaylord_height)
                max_len = max_gaylord_length // cut_length
                profiles_fit = count_fit * max_len
                box_weight = profiles_fit * unit_weight * (cut_length/1000)

                while box_weight > max_weight and profiles_fit > 0:
                    profiles_fit -= 1
                    box_weight = profiles_fit * unit_weight * (cut_length/1000)

                if profiles_fit > 0:
                    vol_box = (profile_width * profile_height * cut_length * profiles_fit) / 1e9
                    total_box_vol = (max_gaylord_width * max_gaylord_height * cut_length * max_len) / 1e9
                    density = vol_box / total_box_vol if total_box_vol > 0 else 0

                    w_fit = pallet_width // max_gaylord_width
                    l_fit = pallet_length // (cut_length * max_len)
                    h_fit = pallet_max_height // max_gaylord_height
                    pallet_count = w_fit * l_fit * h_fit

                    results.append({
                        "Profile Name": profile_name,
                        "Cut Lengths Included": f"{profiles_fit} of {cut_length}mm only",
                        "Box W×H×L (mm)": f"{max_gaylord_width}×{max_gaylord_height}×{cut_length * max_len}",
                        "Profiles in Box": profiles_fit,
                        "Profiles of Same Cut in Box": profiles_fit,
                        "Box Weight (kg)": round(box_weight, 2),
                        "Density (%)": f"{round(density*100,1)}%",
                        "Boxes per Pallet": pallet_count,
                        "Pallet Arrangement": f"{w_fit}×{l_fit}×{h_fit}" if pallet_count > 0 else "❌"
                    })

            if results:
                df = pd.DataFrame(results)
                st.success("✅ Optimization Complete")
                st.dataframe(df, use_container_width=True)
                out = BytesIO()
                with pd.ExcelWriter(out, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False, sheet_name='Results')
                st.download_button("📅 Download Results", out.getvalue(), "results.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            else:
                st.warning("⚠️ No valid box configuration found based on constraints.")
