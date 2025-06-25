# 1. ベースイメージとして公式のPython 3.9 slim版を選択
FROM python:3.9-slim

# 2. コンテナ内の作業ディレクトリを作成・設定
WORKDIR /app

# 3. 最初に依存関係ファイルだけをコピー
COPY requirements.txt .

# 4. 依存ライブラリをインストール（キャッシュを効かせるため先に実行）
RUN pip install --no-cache-dir -r requirements.txt

# 5. アプリケーションのソースコードをコピー
COPY . .

# 6. Streamlitが使用するポートを外部に公開
EXPOSE 8501

# 7. コンテナ起動時に実行するコマンド
#    0.0.0.0 を指定してコンテナ外部からのアクセスを許可する
CMD ["streamlit", "run", "labeling_app.py", "--server.port", "8501", "--server.address", "0.0.0.0"]
