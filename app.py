import streamlit as st
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
import io, os, shutil, zipfile
import base64

# --- 画像をプレビュー用に変換する魔法の関数 ---
def st_image_to_base64(img):
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode()

# --- 1. ページ設定とデザイン（老眼＆スマホ最適化） ---
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
    /* ガイドメッセージのスタイル */
    .guide-box {
        background-color: #e3f2fd; color: #0d47a1; padding: 15px;
        border-radius: 10px; border: 1px solid #bbdefb;
        font-size: 18px !important; margin-bottom: 20px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. ロゴとサイト誘導 ---
LOGO_URL = "http://bsdiyai.com/wp-content/uploads/2026/01/cfa8b3e1fa50b36f2dba85e72feba21e.jpg"
st.image(LOGO_URL, width=300)
st.markdown("### [👉 使い方・最新情報は公式サイトへ](https://ai.bsdiyai.com/wp-admin/post.php?post=691&action=edit)")

st.title("🎨 スタンプ一括透過")

# --- 3. スマホ操作のガイド（最重要） ---
st.markdown("""
    <div class="guide-box">
        <b>📱 スマホで複数選ぶコツ</b><br>
        1. 「Browse files」を押し、1枚目を<b>長押し</b>します。<br>
        2. 残りを選び、画面右上の<b>「選択」「完了」または「開く」</b>を押すと、下にボタンが出ます。<br>
        ※Genspark等の特殊なフォルダで選べない場合は、一度「画像」フォルダから選んでみてください。<br>
        だめなら一枚づつ追加して
    </div>
    """, unsafe_allow_html=True)

# --- 4. パラメータ設定 ---
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
    except Exception as e:
        return None

# --- 5. メイン処理 ---
# 【重要】Androidでも複数選択を促す文言に修正
uploaded_files = st.file_uploader(
    "画像をまとめてアップロード（1枚目を長押し！）", 
    type=["png", "jpg", "jpeg", "webp"], 
    accept_multiple_files=True
)

if uploaded_files is not None and len(uploaded_files) > 0:
    st.success(f"✅ {len(uploaded_files)}枚の画像を受け取りました！")
    
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
                
                # 背景色を画像に直接適用するプレビュー
                st.markdown(
                    f"""
                    <div style="background-color: {preview_bg}; padding: 20px; border-radius: 10px; display: inline-block; line-height: 0;">
                        <img src="data:image/png;base64,{st_image_to_base64(res)}" width="200">
                    </div>
                    <p style="font-size:16px; color:#666;">No.{i} プレビュー</p>
                    """,
                    unsafe_allow_html=True
                )
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
