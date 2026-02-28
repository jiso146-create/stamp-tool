import streamlit as st
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
import io, os, shutil, zipfile
import base64

# --- 1. ページ構成（アイコンとタイトルを設定） ---
# page_iconに画像のURLを指定することで、タブのアイコンが変わります
st.set_page_config(
    page_title="LINEスタンプ透過くん", 
    page_icon="http://bsdiyai.com/wp-content/uploads/2026/01/cfa8b3e1fa50b36f2dba85e72feba21e.jpg",
    layout="centered"
)

# --- 2. 徹底的にStreamlit要素を消去するCSS ---
st.markdown("""
    <style>
    /* 1. 標準メニュー・ヘッダー・フッターを物理的に削除 */
    header, footer, #MainMenu {visibility: hidden !important; display: none !important;}
    
    /* 2. 右下の王冠・デプロイボタンなどを強制非表示 */
    .stAppDeployButton, .stDeployButton, #viewer-badge, .stActionButton, [data-testid="stStatusWidget"] {
        display: none !important;
        visibility: hidden !important;
    }
    
    /* 3. 余白調整 */
    [data-testid="stHeader"] {display: none !important;}
    .block-container {padding-top: 1rem !important; padding-bottom: 1rem !important;}

    /* 4. デザイン最適化 */
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
    /* 宣伝用テキストのスタイル */
    .credit {
        font-size: 14px !important;
        color: #999;
        text-align: center;
        margin-top: 50px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 3. 補助関数 ---
def st_image_to_base64(img):
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode()

# --- 4. メインコンテンツ ---
LOGO_URL = "http://bsdiyai.com/wp-content/uploads/2026/01/cfa8b3e1fa50b36f2dba85e72feba21e.jpg"
st.image(LOGO_URL, width=300)
st.markdown("### [👉 使い方・最新情報は公式サイトへ](https://ai.bsdiyai.com/wp-admin/post.php?post=691&action=edit)")

st.title("🎨 スタンプ一括透過")

st.markdown("""
    <div class="guide-box">
        <b>📱 スマホで複数選ぶコツ</b><br>
        1. 「Browse files」を押し、1枚目を<b>長押し</b>します。<br>
        2. 残りを選び、画面右上の<b>「選択」または「完了」</b>を押してください。<br>
        ※一枚づつ追加してもOKです。
    </div>
    """, unsafe_allow_html=True)

# --- 5. パラメータ設定 ---
with st.expander("⚙️ 設定（背景色に合わせて変えてね）"):
    color_name = st.selectbox(
        "AIで作った背景色は何色？", 
        ["マゼンタ (桃)", "ライム (緑)", "シアン (水色)", "イエロー (黄)"]
    )
    color_dict = {
        "マゼンタ (桃)": (255, 0, 255),
        "ライム (緑)": (0, 255, 0),
        "シアン (水色)": (0, 255, 255),
        "イエロー (黄)": (255, 255, 0)
    }
    TARGET_RGB = color_dict[color_name]

    MODE = st.selectbox("背景の消し方", ["AllPixels", "FloodFill"], index=0)
    THRESHOLD = st.slider("透過の強さ", 0, 255, 150)
    ERODE = st.slider("縁を削る量", 0, 3, 1)
    SMOOTH = st.slider("なめらかさ", 0, 3, 1)

# 確認用の背景色
bg_choice = st.radio("仕上がり確認用の背景色", ["透過", "チャット画面風", "黒"], horizontal=True)
bg_map = {"透過": "#ffffff", "チャット画面風": "#7494C0", "黒": "#333333"}
preview_bg = bg_map[bg_choice]

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
            mask = np.sqrt(np.sum((data[:,:,:3] - TARGET_RGB)**2, axis=2)) < THRESHOLD
            data[mask] = [0,0,0,0]
            img = Image.fromarray(data)

        r, g, b, a = img.split()
        a = a.point(lambda p: 255 if p > 128 else 0)
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

# --- 6. メイン処理 ---
uploaded_files = st.file_uploader(
    "画像をアップロード", 
    type=["png", "jpg", "jpeg", "webp"], 
    accept_multiple_files=True
)

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

# --- 7. フッター（宣伝） ---
st.markdown("""
    <div class="credit">
        武術創造 DIY・AI研究所
    </div>
    """, unsafe_allow_html=True)
