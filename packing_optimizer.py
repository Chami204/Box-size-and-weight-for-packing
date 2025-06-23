import streamlit as st
import pandas as pd
from math import ceil
from io import BytesIO

st.set_page_config(page_title="📦 Profile Packing Optimizer", page_icon="📦")
st.title("📦 Profile Packing Optimizer - Optimize Box & Pallet")

# 1️⃣ Gaylord Constraints
st.header("1️⃣ Gaylord Constraints")
col1, col2, col3 = st.columns(3)
with col1:
    max_weight = st.number_input("Maximum Gaylord Weight (kg)", min_value=0.1, value=1000.0, format="%.2f")
with col2:
    max_gaylord_width = st.number_input("Maximum Gaylord Width (mm)", min_value=1, value=1200)
with col3:
    max_gaylord_height = st.number_input("Maximum Gaylord Height (mm)", min_value=1, value=1200)
max_gaylord_length = st.number_input("Maximum Gaylord Length (mm)", min_value=1, value=1200)

# 2️⃣ Pallet Constraints
st.header("2️⃣ Pallet Constraints")
col1, col2, col3 = st.columns(3)
with col1:
    pallet_width = st.number_input("Pallet Width (mm)", min_value=1, value=1100)
with col2:
    pallet_length = st.number_input("Pallet Length (mm)", min_value=1, value=1100)
with col3:
    pallet_max_height = st.number_input("Pallet Max Height (mm)", min_value=1, value=2000)

# 3️⃣ Input Table
def convert_to_mm(length, unit): return {'mm': length, 'cm': length*10, 'm': length*1000, 'inches': length*25.4}.get(unit, length)

def get_factor_pairs(n):
    pairs=[]
    for i in range(1, int(n**0.5)+1):
        if n%i==0: pairs.append((i, n//i))
    return pairs

st.header("3️⃣ Profile + Cut Lengths Input Table")
uploaded = st.file_uploader("Upload .csv or .xlsx", type=["csv","xlsx"])
if uploaded:
    if uploaded.name.endswith('.csv'):
        df_input = pd.read_csv(uploaded)
    else:
        df_input = pd.read_excel(uploaded)
else:
    df_input = pd.DataFrame({
        'Profile Name':['A','B'],
        'Unit Weight (kg/m)':[1.5,2.0],
        'Profile Width (mm)':[50,60],
        'Profile Height (mm)':[60,70],
        'Cut Length':[2500,3000],
        'Cut Unit':['mm','mm']
    })
    df_input = st.data_editor(df_input, num_rows='dynamic', use_container_width=True,
        column_config={'Cut Unit': st.column_config.SelectboxColumn(label='Unit', options=['mm','cm','m','inches'])})

# 4️⃣ Run Optimization
if st.button("🚀 Run Optimization"):
    if df_input.empty:
        st.warning("Enter data to proceed")
    else:
        # compute initial best per profile
        rows=[]
        for _,r in df_input.iterrows():
            if r['Cut Length']<=0 or r['Unit Weight (kg/m)']<=0: continue
            cut_mm = convert_to_mm(r['Cut Length'], r['Cut Unit'])
            uw=r['Unit Weight (kg/m)']; pw=r['Profile Width (mm)']; ph=r['Profile Height (mm)']
            max_profiles = []
            # find best W,H per profile by density
            for w_count,h_count in get_factor_pairs(1): pass
            # we just collect current best box dims
            # find max counts for this profile unconstrained by common dims
            # simply record original best W,H
            # compute floor boxes per box by dims/length and weight
            total_by_dims = (max_gaylord_width//pw)*(max_gaylord_height//ph)*(max_gaylord_length//cut_mm)
            total_by_weight = int(max_weight//(uw*(cut_mm/1000)))
            count = min(total_by_dims, total_by_weight)
            if count<=0: continue
            # choose w_box=pw_count*pw etc
            wbox = pw * (max_gaylord_width//pw)
            hbox = ph * (max_gaylord_height//ph)
            lbox = cut_mm * (max_gaylord_length//cut_mm)
            # ensure dims within
            wbox=min(wbox,max_gaylord_width); hbox=min(hbox,max_gaylord_height); lbox=min(lbox,max_gaylord_length)
            density = (r['Profile Width (mm)']*r['Profile Height (mm)']*cut_mm*count)/((wbox*hbox*lbox))
            rows.append({'Profile':r['Profile Name'],'Cut length/mm':cut_mm,'Box W':wbox,'Box H':hbox,'Box L':lbox,'Count':count,'Density':density})
        df_best=pd.DataFrame(rows)
        # determine common dims by frequency
        wh = df_best[['Box W','Box H']].astype(str).agg('×'.join,axis=1)
        common = wh.value_counts().index[:2]
        common_dims=[tuple(map(int,s.split('×'))) for s in common]
        # final output
        final=[]
        for _,r in df_input.iterrows():
            cut_mm = convert_to_mm(r['Cut Length'], r['Cut Unit'])
            uw=r['Unit Weight (kg/m)']; pw=r['Profile Width (mm)']; ph=r['Profile Height (mm)']
            best=None
            for w_box,h_box in common_dims:
                # profiles per box
                by_dims = (max_gaylord_width//w_box)*(max_gaylord_height//h_box)*(max_gaylord_length//cut_mm)
                by_wt = int(max_weight//(uw*(cut_mm/1000)))
                total=min(by_dims,by_wt)
                if total<=0: continue
                density=(pw*ph*cut_mm*total)/(w_box*h_box*cut_mm*1e-3)
                if best is None or density>best['density']:
                    best={'Profile':r['Profile Name'],'Cut length/mm':cut_mm,'Box Width/mm':w_box,'Box Height/mm':h_box,'Box Length/mm':cut_mm,'Number of profiles/box':total,'Box density comment':"Good" if density>=0.7 else "Low", 'density':density}
            if best:
                # pallet
                wf=pallet_width//best['Box Width/mm']; lf=pallet_length//best['Box Length/mm']; hf=pallet_max_height//best['Box Height/mm']
                bc=wf*lf*hf
                best.update({'Pallet W (mm)':pallet_width,'Pallet H (mm)':pallet_max_height,'Pallet L (mm)':pallet_length,'Number of Boxes/pallet':bc,'pallet density comment':"OK" if bc>0 else "No fit"})
                final.append(best)
        out=pd.DataFrame(final)[['Profile','Cut length/mm','Box Width/mm','Box Height/mm','Box Length/mm','Number of profiles/box','Box density comment','Pallet W (mm)','Pallet H (mm)','Pallet L (mm)','Number of Boxes/pallet','pallet density comment']]
        st.dataframe(out,use_container_width=True)
        outbuf=BytesIO()
        out.to_excel(outbuf,index=False)
        st.download_button("Download",outbuf.getvalue(),"packing.xlsx","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
