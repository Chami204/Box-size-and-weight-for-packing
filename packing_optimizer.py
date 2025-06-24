import streamlit as st
import pandas as pd
from math import ceil
from io import BytesIO
from sklearn.cluster import KMeans
import numpy as np

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
    "Profile Name": ["Profile A", "Profile B", "Profile C", "Profile D", "Profile E"],
    "Unit Weight (kg/m)": [1.5, 2.0, 1.8, 1.6, 1.4],
    "Profile Width (mm)": [50.0, 60.0, 52.0, 48.0, 55.0],
    "Profile Height (mm)": [60.0, 70.0, 62.0, 58.0, 65.0],
    "Cut Length": [2500, 3000, 2700, 2800, 2600],
    "Cut Unit": ["mm", "mm", "mm", "mm", "mm"],
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

def euclidean_distance(p1, p2):
    return np.sqrt((p1[0]-p2[0])**2 + (p1[1]-p2[1])**2)

def assign_to_clusters(profiles, centers):
    assignments = []
    for w,h in profiles:
        # find nearest center by Euclidean distance
        dists = [euclidean_distance((w,h), c) for c in centers]
        assignments.append(np.argmin(dists))
    return assignments

def calc_box_length(max_weight, unit_weight, profile_length, items_per_box):
    # total weight = unit_weight * total length of profiles in box
    # total length = profile_length * items_per_box
    # max items limited by max weight, so
    # box length needed to fit max items within weight limit:
    max_total_length = max_weight / unit_weight
    length_needed = profile_length * items_per_box
    if length_needed <= max_total_length:
        return length_needed
    else:
        # reduce items so length_needed fits max_total_length
        # return max allowed length (rounded up)
        return max_total_length

def get_factor_pairs(n):
    pairs = []
    for i in range(1, int(n**0.5)+1):
        if n % i == 0:
            pairs.append((i, n//i))
    return pairs

# ---------- 4. RUN OPTIMIZATION ----------
if st.button("🚀 Run Optimization", type="primary"):
    if editable_data.empty:
        st.warning("⚠️ Please enter at least one profile.")
    else:
        with st.spinner("Optimizing..."):
            # Convert all lengths to mm
            editable_data["Cut Length (mm)"] = editable_data.apply(lambda row: convert_to_mm(row["Cut Length"], row["Cut Unit"]), axis=1)
            
            profiles = editable_data[["Profile Width (mm)", "Profile Height (mm)"]].values
            
            n_profiles = len(profiles)
            
            # Determine number of clusters (box varieties)
            if n_profiles < 10:
                n_clusters = 2
            elif n_profiles < 20:
                n_clusters = 3
            else:
                n_clusters = 4
            
            # Run KMeans clustering on width & height
            if n_profiles < n_clusters:
                n_clusters = n_profiles
            
            kmeans = KMeans(n_clusters=n_clusters, random_state=42)
            kmeans.fit(profiles)
            centers = kmeans.cluster_centers_
            
            assignments = assign_to_clusters(profiles, centers)
            
            results = []
            
            for i, row in editable_data.iterrows():
                profile_name = row["Profile Name"]
                unit_weight = row["Unit Weight (kg/m)"]
                profile_width = row["Profile Width (mm)"]
                profile_height = row["Profile Height (mm)"]
                cut_mm = row["Cut Length (mm)"]
                
                max_items_by_weight = int(max_weight // (unit_weight * (cut_mm/1000)))
                if max_items_by_weight <= 0:
                    max_items_by_weight = 1
                
                cluster_idx = assignments[i]
                box_w, box_h = centers[cluster_idx]
                box_w = ceil(box_w)
                box_h = ceil(box_h)
                
                # Calculate how many items fit in one layer (width x height)
                items_per_layer = (box_w // profile_width) * (box_h // profile_height)
                if items_per_layer == 0:
                    items_per_layer = 1  # fallback to 1
                
                # Max layers allowed by max_items_by_weight
                max_layers = max_items_by_weight // items_per_layer
                if max_layers == 0:
                    max_layers = 1
                
                # Calculate box length to hold these layers
                box_l = max_layers * cut_mm
                
                # Check if box respects max Gaylord constraints, if not, reduce layers
                while (box_w > max_gaylord_width or box_h > max_gaylord_height or box_l > max_gaylord_length) and max_layers > 0:
                    max_layers -= 1
                    box_l = max_layers * cut_mm
                
                if max_layers == 0:
                    max_layers = 1
                    box_l = max_layers * cut_mm
                    # If still invalid, this means profile cannot fit under constraints
                    # but we proceed anyway (you can add warning if needed)
                
                items_in_box = items_per_layer * max_layers
                
                # Calculate density (used volume / box volume)
                vol_box = (box_w * box_h * box_l) / 1e9  # m3
                used_vol = items_in_box * (profile_width * profile_height * cut_mm) / 1e9
                density = used_vol / vol_box if vol_box > 0 else 0
                density_comment = "🏆 Good density" if density >= 0.7 else "⚠️ Low density"
                
                # Pallet fitting
                w_fit = pallet_width // box_w if box_w > 0 else 0
                l_fit = pallet_length // box_l if box_l > 0 else 0
                h_fit = pallet_max_height // box_h if box_h > 0 else 0
                pallet_count = w_fit * l_fit * h_fit
                
                results.append({
                    "Profile Name": profile_name,
                    "Cluster (Box Type)": f"Box Type {cluster_idx+1}",
                    "Assigned Box W×H (mm)": f"{box_w}×{box_h}",
                    "Box Length (mm)": ceil(box_l),
                    "Items per Box": items_in_box,
                    "Density Comment": density_comment,
                    "Boxes per Pallet": pallet_count,
                    "Pallet Arrangement": f"{w_fit}×{l_fit}×{h_fit}" if pallet_count > 0 else "❌"
                })
            
            df = pd.DataFrame(results)
            st.success("✅ Optimization Complete")
            st.dataframe(df, use_container_width=True)
            
            # Export to Excel
            out = BytesIO()
            with pd.ExcelWriter(out, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Results')
            st.download_button("📥 Download Results", out.getvalue(), "results.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
