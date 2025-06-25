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

if st.button("🚀 Run Optimization", type="primary"):
    if editable_data.empty:
        st.warning("⚠️ Please upload or enter at least one profile to proceed.")
    else:
        with st.spinner("Optimizing... this may take a moment for large datasets"):
            editable_data["Cut Length (mm)"] = editable_data.apply(
                lambda row: {"mm": row["Cut Length"], "cm": row["Cut Length"]*10, "m": row["Cut Length"]*1000, "inches": row["Cut Length"]*25.4}.get(row["Cut Unit"], row["Cut Length"]),
                axis=1
            )
            editable_data["Weight Per Item"] = editable_data["Unit Weight (kg/m)"] * (editable_data["Cut Length (mm)"] / 1000)

            result_table1 = []
            box_map = {}

            for _, row in editable_data.iterrows():
                pw, ph, cl, uw = row["Profile Width (mm)"], row["Profile Height (mm)"], row["Cut Length (mm)"], row["Unit Weight (kg/m)"]
                wpi = uw * (cl / 1000)
                max_items = int(max_weight // wpi)
                best = None
                for n in range(max_items, 0, -1):
                    for i in range(1, int(n**0.5)+1):
                        if n % i != 0: continue
                        for wc, hc in [(i, n//i), (n//i, i)]:
                            l_count = n // (wc*hc) if wc*hc>0 else 0
                            if wc*hc*l_count != n: continue
                            bw, bh, bl = wc*pw, hc*ph, l_count*cl
                            if bw>max_gaylord_width or bh>max_gaylord_height or bl>max_gaylord_length: continue
                            ratio = max(bw,bh)/min(bw,bh) if min(bw,bh)>0 else 100
                            if ratio > 2: continue
                            best = {"W": ceil(bw), "H": ceil(bh), "L": ceil(bl), "Fit": n}
                            break
                        if best: break
                    if best: break
                if best:
                    result_table1.append({
                        "Profile Name": row["Profile Name"],
                        "Cut Length (mm)": cl,
                        "Items per Box": best["Fit"],
                        "Box W×H×L (mm)": f"{best['W']}×{best['H']}×{best['L']}",
                        "Total Box Weight (kg)": round(best["Fit"] * wpi, 2)
                    })
                    box_map[row["Profile Name"]] = best

            st.success("✅ Optimization Complete")
            df1 = pd.DataFrame(result_table1)
            st.dataframe(df1, use_container_width=True)

            # ---------- SECOND TABLE ----------
            st.subheader("📦 Optimized Shared Box Sizes")
            longest = editable_data.loc[editable_data["Cut Length (mm)"].idxmax()]
            longest_box = box_map.get(longest["Profile Name"], {})
            shared_w, shared_h = longest_box.get("W", 1000), longest_box.get("H", 1000)

            result_table2 = []
            low_weight_profiles = []

            for _, row in editable_data.iterrows():
                cl = row["Cut Length (mm)"]
                pw, ph, uw = row["Profile Width (mm)"], row["Profile Height (mm)"], row["Unit Weight (kg/m)"]
                wpi = uw * (cl / 1000)
                max_items = int(max_weight // wpi)
                best = None
                for n in range(max_items, 0, -1):
                    for i in range(1, int(n**0.5)+1):
                        if n % i != 0: continue
                        for wc, hc in [(i, n//i), (n//i, i)]:
                            if wc*pw > shared_w or hc*ph > shared_h: continue
                            l_count = n // (wc*hc) if wc*hc > 0 else 0
                            if wc*hc*l_count != n: continue
                            bl = l_count * cl
                            if bl > max_gaylord_length: continue
                            best = {"W": shared_w, "H": shared_h, "L": ceil(bl), "Fit": n}
                            break
                        if best: break
                    if best: break
                if best:
                    total_wt = round(best["Fit"] * wpi, 2)
                    if total_wt < 0.5 * max_weight:
                        low_weight_profiles.append((row, total_wt))
                    result_table2.append({
                        "Profile Name": row["Profile Name"],
                        "Cut Length (mm)": cl,
                        "Optimized Box Size": f"{best['W']}×{best['H']}×{best['L']}",
                        "Profiles per Box": best["Fit"],
                        "Total Box Weight (kg)": total_wt
                    })

            if len(editable_data) <= 10 and len(low_weight_profiles) >= 1:
                for row, _ in low_weight_profiles:
                    cl = row["Cut Length (mm)"]
                    pw, ph, uw = row["Profile Width (mm)"], row["Profile Height (mm)"], row["Unit Weight (kg/m)"]
                    wpi = uw * (cl / 1000)
                    max_items = int(max_weight // wpi)
                    for n in range(max_items, 0, -1):
                        for i in range(1, int(n**0.5)+1):
                            if n % i != 0: continue
                            for wc, hc in [(i, n//i), (n//i, i)]:
                                bw, bh = wc*pw, hc*ph
                                l_count = n // (wc*hc) if wc*hc > 0 else 0
                                if wc*hc*l_count != n: continue
                                bl = l_count * cl
                                if bw > max_gaylord_width or bh > max_gaylord_height or bl > max_gaylord_length: continue
                                new_wt = round(n * wpi, 2)
                                if new_wt >= 0.5 * max_weight:
                                    result_table2.append({
                                        "Profile Name": row["Profile Name"],
                                        "Cut Length (mm)": cl,
                                        "Optimized Box Size": f"{ceil(bw)}×{ceil(bh)}×{ceil(bl)}",
                                        "Profiles per Box": n,
                                        "Total Box Weight (kg)": new_wt
                                    })
                                    break
                        else:
                            continue
                        break

            st.dataframe(pd.DataFrame(result_table2), use_container_width=True)
