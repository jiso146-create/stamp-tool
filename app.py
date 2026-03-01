import streamlit as st
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
import io, os, shutil, zipfile
import base64

# --- 1. ページ構成 ---
st.set_page_config(
    page_title="LINEスタンプ透過くん", 
    page_icon="http://bsdiyai.com/wp-content/uploads/2026/01/cfa8b3e1fa50b36f2dba85e72feba21e.jpg",
    layout="centered"
)

# --- 2. CSS設定（徹底消去） ---
st.markdown("""
    <style>
    header, footer, #MainMenu {visibility: hidden !important; display: none !important;}
    .stAppDeployButton, .stDeployButton, #viewer-badge, .stActionButton, [data-testid="stStatusWidget"] {
        display: none !important; visibility: hidden !important;
    }
    [data-testid="stHeader"] {display: none !important;}
    .block-container {padding-top: 1rem !important; padding-bottom: 1rem !important;}
    html, body, [class*="css"] { font-size: 24px !important; }
    .stButton>button {
        width: 100%; height: 100px; font-size: 32px !important;
        font-weight: bold; background-color: #00b900 !important; color: white !important;
        border-radius: 15px; margin-top: 20px;
    }
    .stSlider label, .stSelectbox label, .stRadio label { 
        font-size: 26px !important; font-weight: bold; 
    }
    .guide-box {
        background-color: #e3f2fd; color: #0d47a1; padding: 15px;
        border-radius: 10px; border: 1px solid #bbdefb;
        font-size: 18px !important; margin-bottom: 20px;
    }
    .credit {
        font-size: 14px !important; color: #999; text-align: center; margin-top: 50px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 3. 補助関数 ---
def st_image_to_base64(img):
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode()

# --- 4. メインヘッダー ---
LOGO_URL = "http://bsdiyai.com/wp-content/uploads/2026/01/cfa8b3e1fa50b36f2dba85e72feba21e.jpg"
st.image(LOGO_URL, width=300)
st.markdown("### [👉 使い方・最新情報は公式サイトへ](https://ai.bsdiyai.com/)")
st.title("🎨 スタンプ一括透過")

# --- 5. 【NEW!】画像アップロード（最優先） ---
uploaded_files = st.file_uploader(
    "画像をアップロード（複数選べます）", 
    type=["png", "jpg", "jpeg", "webp"], 
    accept_multiple_files=True
)

# --- 6. 【NEW!】仕上がり確認用の背景選択 ---
st.write("### 📺 仕上がりのチェック")
bg_choice = st.radio("背景を切り替えて確認：", ["チャット画面風", "透過", "黒"], horizontal=True)
bg_map = {"透過": "#ffffff", "チャット画面風": "#7494C0", "黒": "#333333"}
preview_bg = bg_map[bg_choice]

# --- 7. 設定（エクスパンダーで畳む） ---
with st.expander("⚙️ こだわり設定（マゼンタが残る時はこちら）"):
    color_name = st.selectbox(
        "AIで作った背景色は何色？", 
        ["マゼンタ (桃)", "ライム (緑)", "シアン (水色)", "イエロー (黄)"]
    )
    color_dict = {
        "マゼンタ (桃)": (255, 0, 255), "ライム (緑)": (0, 255, 0),
        "シアン (水色)": (0, 255, 255), "イエロー (黄)": (255, 255, 0)
    }
    TARGET_RGB = color_dict[color_name]
    MODE = st.selectbox("背景の消し方", ["AllPixels", "FloodFill"], index=0)
    THRESHOLD = st.slider("透過の強さ", 0, 255, 150)
    
    st.write("---")
    USE_MATTING = st.checkbox("境界を自動で馴染ませる", value=True)
    ERODE = st.slider("縁を削り取る (Erode)", 0, 5, 1)
    SMOOTH = st.slider("なめらかさ", 0, 3, 1)

# 固定設定
STAMP_SIZE = (370, 320)
MARGIN = 10
OUTPUT_DIR = "stamps"

def process_ultimate(content, i):
    try:
        img = Image.open(content).convert("RGBA")
        if MODE == "FloodFill":
            for p in [(0,0), (img.width-1,0), (0,img.height-1), (img.width-1,img.height-1)]:
                ImageDraw.floodfill(img, p, (0,0,0,0), thresh=THRESHOLD)
        else:
            data = np.array(img)
            diff = np.sqrt(np.sum((data[:,:,:3] - TARGET_RGB)**2, axis=2))
            mask = diff < THRESHOLD
            data[mask] = [0,0,0,0]
            img = Image.fromarray(data)
        r, g, b, a = img.split()
        if USE_MATTING: a = a.filter(ImageFilter.SMOOTH_MORE)
        if ERODE > 0: a = a.filter(ImageFilter.MinFilter(ERODE * 2 + 1))
        if SMOOTH > 0: a = a.filter(ImageFilter.GaussianBlur(SMOOTH * 0.5))
        img = Image.merge("RGBA", (r, g, b, a))
        bbox = img.getbbox()
        if not bbox: return None
        cropped = img.crop(bbox)
        max_w, max_h = STAMP_SIZE[0] - (MARGIN * 2), STAMP_SIZE[1] - (MARGIN * 2)
        cropped.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)
        canvas = Image.new("RGBA", STAMP_SIZE, (0,0,0,0))
        offset = ((STAMP_SIZE[0] - cropped.width) // 2, (STAMP_SIZE[1] - cropped.height) // 2)
        canvas.paste(cropped, offset)
        return canvas
    except:
        return None

# --- 8. メイン処理 ---
if uploaded_files:
    st.success(f"✅ {len(uploaded_files)}枚受け取りました")
    if st.button("🚀 一括変換＆ダウンロード準備"):
        if os.path.exists(OUTPUT_DIR): shutil.rmtree(OUTPUT_DIR)
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        processed_imgs = []
        progress_bar = st.progress(0)
        
        for i, file in enumerate(uploaded_files, 1):
            res = process_ultimate(file, i)
            if res:
                res.save(f"{OUTPUT_DIR}/stamp_{i:02d}.png", "PNG", optimize=True)
                processed_imgs.append(res)
                st.markdown(f"""
                    <div style="background-color: {preview_bg}; padding: 20px; border-radius: 10px; display: inline-block; line-height: 0;">
                        <img src="data:image/png;base64,{st_image_to_base64(res)}" width="200">
                    </div>
                    """, unsafe_allow_html=True)
            progress_bar.progress(i / len(uploaded_files))

        if processed_imgs:
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w") as zf:
                for root, _, filenames in os.walk(OUTPUT_DIR):
                    for filename in filenames:
                        zf.write(os.path.join(root, filename), filename)
            st.download_button(
                label="🎁 完成ファイルを保存",
                data=zip_buffer.getvalue(),
                file_name="STAMP_DONE.zip",
                mime="application/zip"
            )

st.markdown('<div class="credit">武術創造 DIY・AI研究所</div>', unsafe_allow_html=True)
