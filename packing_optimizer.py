import streamlit as st
import pandas as pd
from math import ceil
from itertools import permutations
from io import BytesIO
try:
    import matplotlib.pyplot as plt
except ImportError:
    plt = None
    st.warning("matplotlib is not installed. Pallet visualization is disabled.")

st.set_page_config(page_title="📦 Profile Packing Optimizer", page_icon="📦")
st.title("📦 Profile Packing Optimizer - Maximize Fit by Weight & Pallet Layout")

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
used_pallet_size = f"{pallet_width}×{pallet_length}×{pallet_max_height} mm"

# ---------- 3. PROFILE + CUT LENGTH INPUT ----------
st.header("3️⃣ Profile + Cut Lengths Input Table")
uploaded_file = st.file_uploader("Upload Profile Data (.csv or .xlsx)", type=["csv","xlsx"])
if uploaded_file:
    if uploaded_file.name.endswith('.csv'):
        editable_data = pd.read_csv(uploaded_file)
    else:
        editable_data = pd.read_excel(uploaded_file)
else:
    default_data = pd.DataFrame({
        "Profile Name":["Profile A","Profile B"],
        "Unit Weight (kg/m)":[1.5,2.0],
        "Profile Width (mm)":[50.0,60.0],
        "Profile Height (mm)":[60.0,70.0],
        "Cut Length":[2500,3000],
        "Cut Unit":["mm","mm"],
    })
    editable_data = st.data_editor(default_data, num_rows='dynamic', use_container_width=True,
        column_config={"Cut Unit":st.column_config.SelectboxColumn(label="Cut Unit",options=["mm","cm","m","inches"])})

# Helpers
def convert_to_mm(length, unit): return {'mm':length,'cm':length*10,'m':length*1000,'inches':length*25.4}.get(unit,length)

def get_factor_pairs(n):
    pairs=[]
    for i in range(1,int(n**0.5)+1):
        if n % i ==0: pairs.append((i,n//i))
    return pairs

# ---------- 4. RUN & OPTIMIZATION ----------
if st.button("🚀 Run Optimization"):
    if editable_data.empty:
        st.warning("⚠️ Please upload or enter profiles to proceed.")
    else:
        with st.spinner("Optimizing box & pallet...\nThis may take a moment."):
            results=[]
            for _,row in editable_data.iterrows():
                if row['Cut Length']<=0 or row['Unit Weight (kg/m)']<=0: continue
                name=row['Profile Name']; uw=row['Unit Weight (kg/m)']
                w=row['Profile Width (mm)']; h=row['Profile Height (mm)']
                cut=convert_to_mm(row['Cut Length'],row['Cut Unit'])
                weight_item=uw*(cut/1000)
                count=int(max_weight//weight_item) or 1
                best=None; bd=float('inf'); dd=float('inf'); bc=0
                for c in range(count,0,-1):
                    for fw,fh in get_factor_pairs(c):
                        for wc,hc in ((fw,fh),(fh,fw)):
                            lc=c//(wc*hc) if wc*hc>0 else 0
                            if wc*hc*lc!=c: continue
                            bw=wc*w; bh=hc*h; bl=lc*cut
                            if bw>max_gaylord_width or bh>max_gaylord_height or bl>max_gaylord_length: continue
                            diff=abs(bw-bh); dev=max(bw,bh,bl)-min(bw,bh,bl)
                            if diff<bd or (diff==bd and dev<dd): best={'W':ceil(bw),'H':ceil(bh),'L':ceil(bl),'Fit':c}; bd,dd=diff,dev; bc=c
                    if best: break
                if not best:
                    st.warning(f"⚠️ '{name}' cannot fit any box under constraints.")
                    continue
                vol_box=(best['W']*best['H']*best['L'])/1e9
                used_vol=bc*(w*h*cut)/1e9
                density=used_vol/vol_box if vol_box>0 else 0
                dcom="🏆 Good density" if density>=0.7 else "⚠️ Low density"
                wf=pallet_width//best['W']; lf=pallet_length//best['L']; hf=pallet_max_height//best['H']
                pal_count=wf*lf*hf
                results.append({
                    'Profile':name,
                    'Cut mm':cut,
                    'Items/Box':best['Fit'],
                    'Box W×H×L mm':f"{best['W']}×{best['H']}×{best['L']}",
                    'Density':f"{density*100:.1f}%",
                    'Density Comment':dcom,
                    'Boxes/Pallet':pal_count,
                    'Pallet Layout':f"{wf}×{lf}×{hf}",
                    'Used Pallet Size':used_pallet_size
                })
            df=pd.DataFrame(results)
            # ----- Heuristic: dynamically limit box size variants -----
            # Extract numeric dims
            whl = df['Box W×H×L mm'].str.split('×', expand=True).astype(int)
            whl.columns = ['W','H','L']
            # Determine max groups based on number of unique lengths
            unique_L = sorted(whl['L'].unique())
            m = len(unique_L)
            if m <= 5:
                max_groups = 1
            elif m <= 10:
                max_groups = 2
            elif m <= 20:
                max_groups = 3
            else:
                max_groups = min(5, m)
            # Assign each row to a group by quantile of L
            df['group'] = pd.qcut(whl['L'], q=max_groups, labels=False, duplicates='drop')
            # For each group, compute max W,H
            opt_wh = df.groupby('group').apply(lambda g: pd.Series({
                'optW': whl.loc[g.index,'W'].max(),
                'optH': whl.loc[g.index,'H'].max()
            })).reset_index()
            # Map optimized dims back
            df = df.merge(opt_wh, on='group')
            # Build optimized box dims keeping L
            df['Opt Box W×H×L mm'] = df.apply(lambda r: f"{r['optW']}×{r['optH']}×{whl.at[r.name,'L']}", axis=1)
            # Recalculate pallet fit for optimized boxes
            df['Opt W'] = df['optW']; df['Opt H'] = df['optH']; df['Opt L'] = whl['L']
            df['Opt Boxes/Pallet'] = (pallet_width // df['Opt W']) * (pallet_length // df['Opt L']) * (pallet_max_height // df['Opt H'])
            df['Opt Pallet Layout'] = df.apply(lambda r: f"{pallet_width//r['Opt W']}×{pallet_length//r['Opt L']}×{pallet_max_height//r['Opt H']}", axis=1)
            df.drop(columns=['group','optW','optH'], inplace=True)

            st.success("✅ Optimization Complete")("✅ Optimization Complete")
            st.dataframe(df,use_container_width=True)

            # download
            out=BytesIO()
            with pd.ExcelWriter(out,engine='openpyxl') as w: df.to_excel(w,index=False,sheet_name='Results')
            st.download_button("📥 Download Results",out.getvalue(),"results.xlsx","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        # ---------- 5. PALLET VISUALIZATION ----------
        st.header("📊 Pallet Layout Visualization")
        idx=st.selectbox("Select profile to visualize:",options=df.index,format_func=lambda i:df.at[i,'Profile'])
        if st.button("🔍 Show Layout"):
            row=df.loc[idx]
            wf,lf,hf = map(int,row['Pallet Layout'].split('×'))
            bw,bh=row['Box W×H×L mm'].split('×')[:2]
            bw,bh=int(bw),int(bh)
            fig,ax=plt.subplots()
            # draw pallet border
            ax.add_patch(plt.Rectangle((0,0),(pallet_width),(pallet_length),fill=False,edgecolor='black',linewidth=2))
            # draw boxes on base layer
            for i in range(wf):
                for j in range(lf):
                    ax.add_patch(plt.Rectangle((i*bw,j*bh),bw,bh,fill=True,facecolor='skyblue',edgecolor='white'))
            ax.set_xlim(0,pallet_width); ax.set_ylim(0,pallet_length)
            ax.set_aspect('equal', 'box')
            ax.set_xlabel('Width mm'); ax.set_ylabel('Length mm')
            st.pyplot(fig)
