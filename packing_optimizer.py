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

# ---------- 4. OPTIMIZATION ----------
if st.button("🚀 Run Optimization", type="primary"):
    results = []
    pallet_results = []

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

                    # Check max constraints
                    if (box_w > max_gaylord_width or 
                        box_h > max_gaylord_height or 
                        box_l > max_gaylord_length):
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
            })
            continue

        # Calculate pallet fit for this box
        box_dims = [
            best_box["Box Width (mm)"],
            best_box["Box Height (mm)"],
            best_box["Box Length (mm)"]
        ]
        max_boxes = 0
        best_pallet = None
        best_arrangement = ""
        
        # Try all possible box orientations
        for i, j, k in permutations([0, 1, 2]):
            dim1, dim2, dim3 = box_dims[i], box_dims[j], box_dims[k]
            
            # Try both base orientations
            for base_orientation in [(dim1, dim2), (dim2, dim1)]:
                base_w, base_l = base_orientation
                height = dim3
                
                if height > pallet_max_height:
                    continue
                    
                # Calculate how many fit in base area
                w_fit = pallet_width // base_w
                l_fit = pallet_length // base_l
                base_fit = w_fit * l_fit
                
                # Calculate vertical stacking
                height_fit = pallet_max_height // height
                total_fit = base_fit * height_fit
                
                if total_fit > max_boxes:
                    max_boxes = total_fit
                    best_pallet = {
                        "base_width": base_w,
                        "base_length": base_l,
                        "height": height,
                        "w_fit": w_fit,
                        "l_fit": l_fit,
                        "height_fit": height_fit
                    }
                    best_arrangement = f"{w_fit}×{l_fit} (base) × {height_fit} (height)"

        # Add to pallet results
        pallet_results.append({
            "Profile": profile_name,
            "Box Dimensions (mm)": f"{box_dims[0]}×{box_dims[1]}×{box_dims[2]}",
            "Max Boxes/Pallet": max_boxes,
            "Box Arrangement": best_arrangement,
            "Box Orientation": f"{best_pallet['base_width']}×{best_pallet['base_length']} (base)",
            "Box Height": f"{best_pallet['height']} mm",
            "Total Items": max_boxes * best_box["Fit Items"]
        })

        # Add to main results
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
            "W x H x L Arrangement": f"{best_box['W Count']}×{best_box['H Count']}×{best_box['L Count']}",
            "Orientation": best_box["Orientation"],
            "Box Cube Deviation (mm)": int(min_deviation),
        })

    if results:
        # Show main results
        st.success("✅ Gaylord Packing Optimization Complete")
        df = pd.DataFrame(results)
        st.dataframe(df, use_container_width=True)
        
        # Show pallet results
        st.success("📦 Pallet Packing Optimization")
        st.write(f"**Pallet Size:** {pallet_width}×{pallet_length}×{pallet_max_height} mm")
        
        if pallet_results:
            pallet_df = pd.DataFrame(pallet_results)
            st.dataframe(pallet_df, use_container_width=True)
            
            # Add visual feedback
            for result in pallet_results:
                efficiency = ""
                if result["Max Boxes/Pallet"] > 15:
                    efficiency = "🏆 Excellent space utilization"
                elif result["Max Boxes/Pallet"] > 8:
                    efficiency = "👍 Good packing density"
                elif result["Max Boxes/Pallet"] > 0:
                    efficiency = "⚠️ Low packing density"
                else:
                    efficiency = "❌ Does not fit on pallet"
                
                st.info(
                    f"**{result['Profile']}**: {result['Max Boxes/Pallet']} boxes/pallet · "
                    f"{result['Total Items']} total items · {efficiency}"
                )
        else:
            st.warning("No valid pallet configurations found")

        # Download functionality
        from io import BytesIO
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name="Gaylord Packing")
            if pallet_results:
                pd.DataFrame(pallet_results).to_excel(writer, index=False, sheet_name="Pallet Packing")
        st.download_button(
            label="📥 Download Full Report",
            data=output.getvalue(),
            file_name="Packing_Optimization_Report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        st.warning("⚠️ No valid packing configuration found. Please check your inputs.")
