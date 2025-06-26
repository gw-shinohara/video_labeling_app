import streamlit as st
import cv2
import os
import pandas as pd
import time
from pathlib import Path
import shutil
import pickle
import re

# --- 定数 ---
# セッション状態を保存するファイル
STATE_FILE = Path("./.session_state.pkl")
# Dockerコンテナ内のデータマウントポイント
DATA_ROOT_PATH = "/data"

# --- 状態の保存・復元 ---
def save_state():
    """現在のセッション状態をファイルに保存します。"""
    # 保存するべきキーをリスト化
    keys_to_save = [
        "image_files", "current_frame_index", "labels_data",
        "labels_config", "fixed_labels", "play_speed", "selected_path",
        "last_update_time", "actual_fps", "use_fix_mode"
    ]
    state_to_save = {key: st.session_state.get(key) for key in keys_to_save}

    with open(STATE_FILE, "wb") as f:
        pickle.dump(state_to_save, f)

def load_state():
    """ファイルからセッション状態を復元します。"""
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, "rb") as f:
                loaded_state = pickle.load(f)
                # 読み込んだ値でsession_stateを一括更新
                st.session_state.update(loaded_state)
            st.toast("前回の作業状態を復元しました。")
        except Exception as e:
            st.error(f"状態ファイルの読み込みに失敗しました: {e}")
            STATE_FILE.unlink()

def reset_state():
    """セッション状態と保存ファイルをリセットします。"""
    if STATE_FILE.exists():
        STATE_FILE.unlink()
    keys_to_clear = list(st.session_state.keys())
    for key in keys_to_clear:
        del st.session_state[key]
    st.success("作業状態をリセットしました。ページを再読み込みします。")
    time.sleep(2)
    st.rerun()

# --- 状態管理の初期化 ---
def initialize_session_state():
    """セッション内で使用する変数を初期化します。"""
    defaults = {
        "image_files": [],
        "current_frame_index": 0,
        "labels_data": {},
        "is_playing": False,
        "fixed_labels": set(),
        "play_speed": 10.0,
        "labels_config": ["歩行者", "自転車", "## 天気", "晴れ", "曇り"],
        "selected_path": None,
        "last_update_time": time.time(),
        "actual_fps": 0.0,
        "checkbox_labels": [],
        "radio_groups": {},
        "use_fix_mode": False, # ★★★ 追加: ラベル固定モードの状態
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

# --- ラベル設定の解析機能 ---
def parse_label_config():
    """ラベル設定を解析して、チェックボックスとラジオボタンのグループに振り分けます。"""
    checkbox_labels = []
    radio_groups = {}
    current_group_name = None
    
    config_lines = st.session_state.get('labels_config', [])

    for line in config_lines:
        line = line.strip()
        if not line:
            continue # 空行は無視

        if line.startswith('##'):
            current_group_name = line.lstrip('# ').strip()
            if current_group_name:
                radio_groups[current_group_name] = []
        elif current_group_name is not None:
            radio_groups[current_group_name].append(line)
        else:
            checkbox_labels.append(line)

    st.session_state.checkbox_labels = checkbox_labels
    st.session_state.radio_groups = radio_groups

# --- ラベル読み込み機能 ---
def load_labels_from_csv(uploaded_file):
    """アップロードされたCSVからラベル結果を読み込み、ラベル設定も自動更新します。"""
    try:
        image_path_map = {Path(p).name: p for p in st.session_state.image_files}
        df = pd.read_csv(uploaded_file)

        if 'filename' not in df.columns:
            st.error("CSVファイルに 'filename' カラムが見つかりません。")
            return

        label_columns = [col for col in df.columns if col != 'filename']
        st.session_state.labels_config = label_columns # CSVのヘッダをそのままラベル設定とする
        st.success(f"ラベル設定をCSVから読み込んだ{len(label_columns)}個のラベルに更新しました。")
        parse_label_config() # 更新された設定を解析

        loaded_count = 0
        for _, row in df.iterrows():
            filename = row['filename']
            image_path = image_path_map.get(filename)
            if image_path:
                applied_labels = [label for label in label_columns if label in row and row[label] == 1]
                st.session_state.labels_data[image_path] = applied_labels
                loaded_count += 1
        
        if loaded_count > 0:
            st.success(f"{loaded_count}件の画像に対するラベリングデータをCSVから読み込みました。")
        else:
            st.warning("CSV内のファイル名と一致する画像が現在のフォルダに見つかりませんでした。")
        save_state()

    except Exception as e:
        st.error(f"ラベルCSVの読み込み中にエラーが発生しました: {e}")

def on_csv_upload():
    """Callback function to handle CSV file upload."""
    uploaded_file = st.session_state.labels_csv_uploader
    if uploaded_file:
        with st.spinner("ラベルデータを読み込んでいます..."):
            load_labels_from_csv(uploaded_file)

# --- UIコンポーネント ---
def setup_sidebar():
    """サイドバーのUI要素を設定します。"""
    with st.sidebar:
        st.header("作業管理")
        if st.button("現在の作業状態をリセット", type="secondary"):
            reset_state()
        st.divider()

        st.header("1. データ読み込み")

        if not os.path.isdir(DATA_ROOT_PATH) or not os.listdir(DATA_ROOT_PATH):
            st.error("データフォルダが見つかりません。")
            st.warning("`make run DATA_DIR=/path/to/your/pictures` のように、画像フォルダのパスを正しく指定しましたか？")
            st.info("詳細はプロジェクトの `Makefile` を参照してください。")
            st.stop()

        try:
            all_items = sorted(os.listdir(DATA_ROOT_PATH))
            subdirectories = [d for d in all_items if os.path.isdir(os.path.join(DATA_ROOT_PATH, d)) and not d.startswith('.')]
            subdirectories.insert(0, ".")
        except Exception as e:
            st.error(f"データフォルダの読み取りに失敗しました: {e}")
            subdirectories = []

        default_index = 0
        if st.session_state.get("selected_path"):
            try:
                saved_folder_name = os.path.basename(st.session_state.selected_path)
                if saved_folder_name == 'data' or saved_folder_name == '': saved_folder_name = "."
                default_index = subdirectories.index(saved_folder_name)
            except ValueError: default_index = 0

        selected_folder_name = st.selectbox("ラベリング対象のフォルダを選択してください:", options=subdirectories, format_func=lambda x: "ルートフォルダ (`/data`)" if x == "." else x, index=default_index, key="folder_selector")
        selected_path = os.path.normpath(os.path.join(DATA_ROOT_PATH, selected_folder_name))

        if st.button("このフォルダでラベリング開始"):
            st.session_state.selected_path = selected_path
            with st.spinner("画像を読み込んでいます..."):
                if STATE_FILE.exists(): STATE_FILE.unlink()
                keys_to_clear = ["image_files", "current_frame_index", "labels_data"]
                for key in keys_to_clear:
                    if key in st.session_state: del st.session_state[key]
                initialize_session_state()
                parse_label_config() # 初期化後にも解析を実行

                image_paths = []
                image_extensions_set = {".png", ".jpg", ".jpeg", ".bmp", ".tiff"}
                search_path = st.session_state.selected_path
                for root, dirs, files in os.walk(search_path):
                    dirs[:] = [d for d in dirs if not d.startswith('.')]
                    for file in files:
                        if not file.startswith('.') and Path(file).suffix.lower() in image_extensions_set:
                            image_paths.append(os.path.join(root, file))
                st.session_state.image_files = sorted(image_paths)

                if not st.session_state.image_files:
                    st.error(f"フォルダ `{st.session_state.selected_path}` 内に画像ファイルが見つかりませんでした。")
                else:
                    st.success(f"{len(st.session_state.image_files)}枚の画像を読み込みました。")
                    save_state()
                    st.rerun()

        if st.session_state.get("image_files"):
            st.divider()
            st.header("2. ラベル読み込み (任意)")
            st.file_uploader("ラベリング結果CSVを読み込む", type=["csv"], key="labels_csv_uploader", on_change=on_csv_upload, help="以前出力した `labels.csv` をアップロードすると、ラベル設定と作業内容の両方を復元できます。")
            
            st.header("3. ラベル設定")
            label_file = st.file_uploader("ラベル設定ファイルを読み込む (.txt)", type=["txt"], key="label_uploader")
            if label_file is not None:
                try:
                    labels_from_file = label_file.getvalue().decode("utf-8").splitlines()
                    cleaned_labels = [line.strip() for line in labels_from_file if line.strip()]
                    if cleaned_labels and cleaned_labels != st.session_state.labels_config:
                        st.session_state.labels_config = cleaned_labels
                        parse_label_config() # 更新された設定を解析
                        st.success(f"{len(cleaned_labels)}個のラベルをファイルから読み込みました。")
                        save_state()
                        st.rerun()
                except Exception as e:
                    st.error(f"ラベルファイルの読み込みに失敗しました: {e}")

            st.info("`## グループ名` で単一選択ラジオボタンを定義できます。")
            
            def on_labels_changed():
                st.session_state.labels_config = [line.strip() for line in st.session_state.labels_input.split("\n")]
                parse_label_config() # 更新された設定を解析
                save_state()

            st.text_area("ラベルリスト", value="\n".join(st.session_state.labels_config), height=200, key="labels_input", on_change=on_labels_changed)
            
            st.divider()
            st.header("4. 結果の出力")
            include_unlabeled = st.checkbox("ラベルが付与されていない画像も出力に含める", value=True, key="include_unlabeled_checkbox")
            if st.session_state.get("image_files"):
                all_labels = [l.strip() for l in st.session_state.labels_config if l.strip() and not l.strip().startswith('##')]
                header = ['filename'] + all_labels
                rows = []
                for image_path in sorted(st.session_state.image_files):
                    applied_labels = st.session_state.labels_data.get(image_path, [])
                    applied_labels_set = set(applied_labels)
                    if include_unlabeled or applied_labels:
                        row_data = {'filename': Path(image_path).name}
                        for label in all_labels:
                            row_data[label] = 1 if label in applied_labels_set else 0
                        rows.append(row_data)
                if rows:
                    df = pd.DataFrame(rows, columns=header)
                    csv = df.to_csv(index=False).encode('utf-8')
                    st.download_button("ラベリング結果をCSVでダウンロード", csv, "labels.csv", "text/csv", key="download_button_csv")

def main_view():
    """メインの表示エリア（画像、コントロール、ラベリングパネル）を作成します。"""
    if not st.session_state.get("image_files"):
        st.info("ようこそ！左のサイドバーから作業を開始してください。")
        st.code("make run DATA_DIR=/path/to/your/data", language="bash")
        st.stop()

    total_frames = len(st.session_state.image_files)
    current_index = st.session_state.current_frame_index
    if current_index >= total_frames:
        st.warning("インデックスが範囲外です。リセットします。"); st.session_state.current_frame_index = 0; current_index = 0; st.rerun()
    current_image_path = st.session_state.image_files[current_index]

    col_main, col_labels = st.columns([3, 1])
    with col_main:
        fps_display = f" (実測: {st.session_state.actual_fps:.1f} FPS)" if st.session_state.is_playing else ""
        st.subheader(f"画像表示 ({current_index + 1} / {total_frames}){fps_display}")
        st.image(current_image_path, use_container_width=True)
        st.caption(Path(current_image_path).name)

    with col_labels:
        st.subheader("ラベリング")
        # ★★★ 修正点: ラベル固定モードのトグルをパネル上部に移動 ★★★
        st.toggle("ラベル固定モード", key="use_fix_mode", help="このスイッチがONの時にラベルを選択すると、そのラベルが固定されます。")
        
        current_labels = set(st.session_state.labels_data.get(current_image_path, []))
        
        # 1. 複数選択ボタンの表示
        if st.session_state.checkbox_labels:
            st.markdown("---")
            st.caption("複数選択")
            for label in st.session_state.checkbox_labels:
                is_fixed = label in st.session_state.fixed_labels
                is_active = label in current_labels
                button_type = "primary" if is_active else "secondary"
                button_label = f"📌 {label}" if is_fixed else label
                if st.button(button_label, type=button_type, use_container_width=True, key=f"label_btn_{label}"):
                    if st.session_state.use_fix_mode:
                        if is_fixed: st.session_state.fixed_labels.remove(label)
                        else: st.session_state.fixed_labels.add(label)
                    else:
                        if is_active: current_labels.remove(label)
                        else: current_labels.add(label)
                    st.session_state.labels_data[current_image_path] = list(current_labels)
                    save_state()
                    st.rerun()
        
        # 2. 単一選択ラジオボタンの表示
        for group, options in st.session_state.radio_groups.items():
            st.markdown("---")
            st.caption(f"単一選択: {group}")
            
            current_selection_in_group = next((opt for opt in options if opt in current_labels), None)

            # ★★★ 修正点: ラジオボタンのon_changeロジックを更新 ★★★
            def on_radio_change(group_name, group_options):
                selected_label = st.session_state[f"radio_{group_name}"]
                img_path = st.session_state.image_files[st.session_state.current_frame_index]
                
                # 通常のラベル付け処理
                temp_labels = set(st.session_state.labels_data.get(img_path, []))
                temp_labels.difference_update(group_options)
                if selected_label != "（未選択）":
                    temp_labels.add(selected_label)
                st.session_state.labels_data[img_path] = list(temp_labels)

                # 固定モードが有効な場合、固定ラベルセットも更新
                if st.session_state.use_fix_mode:
                    st.session_state.fixed_labels.difference_update(group_options)
                    if selected_label != "（未選択）":
                        st.session_state.fixed_labels.add(selected_label)
                
                save_state()

            radio_display_options = ["（未選択）"] + options
            index = radio_display_options.index(current_selection_in_group) if current_selection_in_group else 0
            
            # ★★★ 修正点: format_funcでピンアイコンを表示 ★★★
            def format_label_with_pin(option):
                return f"📌 {option}" if option in st.session_state.fixed_labels else option

            st.radio(
                f"Radio group for {group}", options=radio_display_options, index=index,
                key=f"radio_{group}", on_change=on_radio_change, args=(group, options), 
                label_visibility="collapsed", format_func=format_label_with_pin
            )

    st.divider()
    st.subheader("コントロール")
    col_progress, col_controls, col_speed = st.columns([3, 2, 1])
    with col_progress:
        st.progress((current_index + 1) / total_frames)
    with col_controls:
        c1, c2, c3 = st.columns(3)
        if c1.button("⏮️ 前へ", use_container_width=True): go_to_frame(current_index - 1)
        play_label = "⏸️ 一時停止" if st.session_state.is_playing else "▶️ 再生"
        if c2.button(play_label, use_container_width=True):
            if not st.session_state.is_playing: st.session_state.last_update_time = time.time()
            st.session_state.is_playing = not st.session_state.is_playing
            save_state(); st.rerun()
        if c3.button("次へ ⏭️", use_container_width=True): go_to_frame(current_index + 1)
    with col_speed:
        def on_slider_change():
            st.session_state.play_speed = st.session_state.play_speed_slider
            save_state()
        st.slider("再生速度 (fps)", 1.0, 120.0, st.session_state.play_speed, key='play_speed_slider', on_change=on_slider_change)

def go_to_frame(index):
    """指定されたインデックスのフレームに移動します。"""
    total_frames = len(st.session_state.image_files)
    if total_frames == 0: return
    new_index = max(0, min(index, total_frames - 1))
    if st.session_state.current_frame_index != new_index:
        st.session_state.current_frame_index = new_index
        apply_fixed_labels()
    st.session_state.is_playing = False
    save_state()
    st.rerun()

# ★★★ 修正点: apply_fixed_labelsのロジックを更新 ★★★
def apply_fixed_labels():
    """現在のフレームに固定ラベルを適用します（ボタンおよびラジオ）。"""
    if not st.session_state.fixed_labels:
        return

    img_path = st.session_state.image_files[st.session_state.current_frame_index]
    current_labels = set(st.session_state.labels_data.get(img_path, []))

    # 1. チェックボックスタイプの固定ラベルを適用
    fixed_checkboxes = st.session_state.fixed_labels.intersection(st.session_state.checkbox_labels)
    current_labels.update(fixed_checkboxes)

    # 2. ラジオボタンタイプの固定ラベルを適用
    for group, options in st.session_state.radio_groups.items():
        # このグループに属する固定ラベルがあるか確認
        fixed_selection_in_group = st.session_state.fixed_labels.intersection(options)
        
        if fixed_selection_in_group:
            # 既存の同グループのラベルを削除
            current_labels.difference_update(options)
            # 固定ラベルを1つ追加（セットなのでpopでOK）
            current_labels.add(fixed_selection_in_group.pop())

    st.session_state.labels_data[img_path] = list(current_labels)


def auto_play():
    """再生状態の時に自動でフレームを進めます。"""
    if st.session_state.is_playing:
        if st.session_state.current_frame_index < len(st.session_state.image_files) - 1:
            time.sleep(1.0 / st.session_state.play_speed)
            st.session_state.current_frame_index += 1
            apply_fixed_labels()
            save_state()
            st.rerun()
        else:
            st.session_state.is_playing = False
            save_state()
            st.rerun()

if __name__ == "__main__":
    st.set_page_config(layout="wide", page_title="動画ラベリングツール")
    st.title("動画・連番画像ラベリングツール")

    if "app_initialized" not in st.session_state:
        initialize_session_state()
        load_state()
        parse_label_config() # 初期ロード時に解析
        st.session_state.app_initialized = True

    setup_sidebar()
    main_view()

    # FPS計算と自動再生はメインビューの後に配置
    current_time = time.time()
    if 'last_update_time' in st.session_state:
        delta = current_time - st.session_state.last_update_time
        if delta > 0: st.session_state.actual_fps = 1.0 / delta
    st.session_state.last_update_time = current_time
    
    auto_play()
