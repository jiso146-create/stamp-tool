import streamlit as st
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
import io, os, shutil, zipfile

# --- 1. ページ設定と老眼対策CSS ---
st.set_page_config(page_title="LINEスタンプ透過くん", page_icon="🎨")

st.markdown("""
    <style>
    html, body, [class*="css"] { font-size: 24px !important; }
    .stButton>button {
        width: 100%; height: 100px; font-size: 32px !important;
        font-weight: bold; background-color: #00b900; color: white;
        border-radius: 15px; margin-top: 20px;
    }
    .stSlider label, .stSelectbox label, .stRadio label { 
        font-size: 26px !important; font-weight: bold; 
    }
    .preview-box {
        padding: 20px; border-radius: 15px; text-align: center; margin-bottom: 20px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. ロゴとサイト誘導 ---
LOGO_URL = "http://bsdiyai.com/wp-content/uploads/2026/01/cfa8b3e1fa50b36f2dba85e72feba21e.jpg"
st.image(LOGO_URL, width=300)
st.markdown("### [👉 使い方・最新情報は公式サイトへ](http://bsdiyai.com/)")

st.title("🎨 プロ仕様・スタンプ一括透過")

# --- 3. パラメータ設定 ---
with st.expander("⚙️ 設定（背景色に合わせて変えてね）"):
    # 【追加】背景色の選択機能
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
            # 選択したTARGET_RGBとの距離で判定
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
    except Exception as e:
        return None

# --- 4. メイン処理 ---
uploaded_files = st.file_uploader("画像をまとめてアップロード", type=["png", "jpg", "jpeg"], accept_multiple_files=True)

if uploaded_files:
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
                st.markdown(f'<div class="preview-box" style="background-color:{preview_bg};"><p style="font-size:16px; color:#666;">No.{i} プレビュー</p></div>', unsafe_allow_html=True)
                st.image(res, width=200)
            progress_bar.progress(i / len(uploaded_files))

        if processed_imgs:
            processed_imgs[0].resize((240, 240)).save(f"{OUTPUT_DIR}/main.png")
            processed_imgs[0].resize((96, 74)).save(f"{OUTPUT_DIR}/tab.png")
            
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w") as zf:
                for root, _, filenames in os.walk(OUTPUT_DIR):
                    for filename in filenames:
                        zf.write(os.path.join(root, filename), filename)
            
            st.success("✨ すべての処理が完了しました！")
            st.download_button(
                label="🎁 完成ファイルをまとめて保存",
                data=zip_buffer.getvalue(),
                file_name="STAMP_DONE.zip",
                mime="application/zip"
            )
