import streamlit as st
import cv2
import os
import pandas as pd
import time
from pathlib import Path
import shutil
import pickle

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
        "last_update_time", "actual_fps" # FPS関連のキーを追加
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
        "labels_config": ["ラベルA", "ラベルB", "ラベルC"],
        "selected_path": None,
        "last_update_time": time.time(), # FPS計算用のタイムスタンプ
        "actual_fps": 0.0,               # 実測FPS
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

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
            subdirectories = [d for d in all_items if os.path.isdir(os.path.join(DATA_ROOT_PATH, d))]
            subdirectories.insert(0, ".")
        except Exception as e:
            st.error(f"データフォルダの読み取りに失敗しました: {e}")
            subdirectories = []

        if not subdirectories:
            st.warning(f"`{DATA_ROOT_PATH}` 内にサブフォルダが見つかりません。")
            st.stop()

        default_index = 0
        if st.session_state.get("selected_path"):
            try:
                saved_folder_name = os.path.basename(st.session_state.selected_path)
                if saved_folder_name == 'data' or saved_folder_name == '':
                    saved_folder_name = "."
                default_index = subdirectories.index(saved_folder_name)
            except ValueError:
                default_index = 0

        selected_folder_name = st.selectbox(
            "ラベリング対象のフォルダを選択してください:",
            options=subdirectories,
            format_func=lambda x: "ルートフォルダ (`/data`)" if x == "." else x,
            index=default_index,
            key="folder_selector"
        )

        selected_path = os.path.normpath(os.path.join(DATA_ROOT_PATH, selected_folder_name))

        if st.button("このフォルダでラベリング開始"):
            st.session_state.selected_path = selected_path
            with st.spinner("画像を読み込んでいます..."):
                if STATE_FILE.exists():
                    STATE_FILE.unlink()

                keys_to_clear = ["image_files", "current_frame_index", "labels_data"]
                for key in keys_to_clear:
                    if key in st.session_state:
                        del st.session_state[key]

                initialize_session_state()

                p_dir = Path(st.session_state.selected_path)
                image_extensions = ["*.png", "*.jpg", "*.jpeg", "*.bmp", "*.tiff"]
                image_paths = []
                for ext in image_extensions:
                    image_paths.extend(p_dir.rglob(ext))

                st.session_state.image_files = sorted([str(p) for p in image_paths])

                if not st.session_state.image_files:
                    st.error(f"フォルダ `{st.session_state.selected_path}` 内に画像ファイルが見つかりませんでした。")
                else:
                    st.success(f"{len(st.session_state.image_files)}枚の画像を読み込みました。")
                    save_state()
                    st.rerun()

        if st.session_state.get("image_files"):
            st.divider()

            st.header("2. ラベル設定")

            label_file = st.file_uploader(
                "ラベル設定ファイルを読み込む (.txt)",
                type=["txt"],
                key="label_uploader"
            )

            if label_file is not None:
                try:
                    labels_from_file = label_file.getvalue().decode("utf-8").splitlines()
                    cleaned_labels = [line.strip() for line in labels_from_file if line.strip()]

                    if cleaned_labels and cleaned_labels != st.session_state.labels_config:
                        st.session_state.labels_config = cleaned_labels
                        st.success(f"{len(cleaned_labels)}個のラベルをファイルから読み込みました。")
                        save_state()
                        st.rerun()

                except Exception as e:
                    st.error(f"ラベルファイルの読み込みに失敗しました: {e}")

            st.info("手動で編集するか、上記のファイルアップロードで設定します。")

            def on_labels_changed():
                st.session_state.labels_config = [line.strip() for line in st.session_state.labels_input.split("\n") if line.strip()]
                save_state()

            st.text_area(
                "ラベルリスト",
                value="\n".join(st.session_state.labels_config),
                height=150,
                key="labels_input",
                on_change=on_labels_changed
            )

            st.divider()
            st.header("3. 結果の出力")

            include_unlabeled = st.checkbox(
                "ラベルが付与されていない画像も出力に含める",
                value=True,
                key="include_unlabeled_checkbox"
            )

            if st.session_state.get("image_files"):
                all_labels = st.session_state.labels_config
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
                    st.download_button(
                        "ラベリング結果をCSVでダウンロード",
                        csv,
                        "labels.csv",
                        "text/csv",
                        key="download_button_csv"
                    )

def main_view():
    """メインの表示エリア（画像、コントロール、ラベリングパネル）を作成します。"""
    # --- FPS Calculation ---
    current_time = time.time()
    delta = current_time - st.session_state.last_update_time
    if delta > 0:
        st.session_state.actual_fps = 1.0 / delta
    st.session_state.last_update_time = current_time
    # --- End of FPS Calculation ---

    if not st.session_state.get("image_files"):
        st.info(
            "ようこそ！\n\n"
            "アプリケーションを起動する際に `DATA_DIR` を指定し、"
            "左のサイドバーに表示されるドロップダウンメニューで目的のフォルダを選択してください。"
        )
        st.code("make run DATA_DIR=/path/to/your/data", language="bash")
        st.stop()

    total_frames = len(st.session_state.image_files)
    current_index = st.session_state.current_frame_index

    if total_frames == 0:
        st.warning("画像リストが空です。サイドバーから再度データを読み込んでください。")
        st.stop()

    if current_index >= total_frames:
        st.warning("現在の画像インデックスが範囲外です。インデックスを0にリセットします。")
        st.session_state.current_frame_index = 0
        current_index = 0
        st.rerun()

    current_image_path = st.session_state.image_files[current_index]

    col_main, col_labels = st.columns([3, 1])

    with col_main:
        # ★★★ 修正点 ★★★ 再生中のみ実測FPSを表示するように修正
        fps_display = f" (実測: {st.session_state.actual_fps:.1f} FPS)" if st.session_state.is_playing else ""
        st.subheader(f"画像表示 ({current_index + 1} / {total_frames}){fps_display}")
        st.image(current_image_path, use_container_width=True)
        st.caption(Path(current_image_path).name)

    with col_labels:
        st.subheader("ラベリング")
        st.caption("ボタンでラベルをON/OFFします。")

        use_fix_mode = st.toggle("ラベル固定モード", help="このスイッチがONの時にラベルボタンを押すと、そのラベルが固定されます。再度押すと解除されます。")
        current_labels = set(st.session_state.labels_data.get(current_image_path, []))

        for label in st.session_state.labels_config:
            is_fixed = label in st.session_state.fixed_labels
            is_active = label in current_labels

            button_type = "primary" if is_active else "secondary"
            button_label = f"📌 {label}" if is_fixed else label

            if st.button(button_label, type=button_type, use_container_width=True, key=f"label_btn_{label}"):
                if use_fix_mode:
                    if is_fixed: st.session_state.fixed_labels.remove(label)
                    else: st.session_state.fixed_labels.add(label)
                else:
                    if is_active: current_labels.remove(label)
                    else: current_labels.add(label)

                st.session_state.labels_data[current_image_path] = list(current_labels)
                save_state()
                st.rerun()

    st.divider()
    st.subheader("コントロール")
    col_progress, col_controls, col_speed = st.columns([3, 2, 1])

    with col_progress:
        st.progress((current_index + 1) / total_frames)
    with col_controls:
        c1, c2, c3 = st.columns(3)
        if c1.button("⏮️ 前へ", use_container_width=True): go_to_frame(current_index - 1)

        play_button_label = "⏸️ 一時停止" if st.session_state.is_playing else "▶️ 再生"
        if c2.button(play_button_label, use_container_width=True):
            # 再生を開始するときにタイマーをリセット
            if not st.session_state.is_playing:
                st.session_state.last_update_time = time.time()
            st.session_state.is_playing = not st.session_state.is_playing
            save_state()
            st.rerun()

        if c3.button("次へ ⏭️", use_container_width=True): go_to_frame(current_index + 1)

    with col_speed:
        def on_slider_change():
            st.session_state.play_speed = st.session_state.play_speed_slider
            save_state()

        st.slider(
            "再生速度 (fps)", 1.0, 120.0,
            value=st.session_state.play_speed,
            key='play_speed_slider',
            on_change=on_slider_change
        )

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

def apply_fixed_labels():
    """現在のフレームに固定ラベルを適用します。"""
    if st.session_state.fixed_labels:
        current_image_path = st.session_state.image_files[st.session_state.current_frame_index]
        current_labels = set(st.session_state.labels_data.get(current_image_path, []))
        current_labels.update(st.session_state.fixed_labels)
        st.session_state.labels_data[current_image_path] = list(current_labels)

def auto_play():
    """再生状態の時に自動でフレームを進めます。"""
    if st.session_state.is_playing:
        current_index = st.session_state.current_frame_index
        total_frames = len(st.session_state.image_files)

        if current_index < total_frames - 1:
            # 目標の待機時間を計算
            target_sleep_time = 1.0 / st.session_state.play_speed

            # 実際の処理時間も考慮に入れる（より正確なFPSに近づけるため）
            # このスクリプトではrerunベースなので、単純なsleepで近似する
            time.sleep(target_sleep_time)

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
        st.session_state.app_initialized = True

    setup_sidebar()
    main_view()
    auto_play()
