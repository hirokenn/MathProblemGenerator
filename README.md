# 問題生成ツール

PDF資料をアップロードし、そのコンテンツに基づいて問題を生成するWebアプリケーションです。異なる難易度の問題を生成し、解答と解説を提供します。

## 特徴

- PDFのアップロードと自動処理
- 難易度別（初級、中級、上級）の問題生成
- 詳細な解答と解説
- 複数のベクトルストア管理によるデータセット分離
- PDFに基づく質問応答機能
- 日本語UIに完全対応

## 使用技術

- [Chainlit](https://github.com/Chainlit/chainlit) - インタラクティブなUI
- [LangChain](https://github.com/langchain-ai/langchain) - LLMの処理フレームワーク
- [OpenAI API](https://openai.com/api/) - 問題生成と解説生成
- [ChromaDB](https://github.com/chroma-core/chroma) - ベクターストア
- [PyMuPDF](https://github.com/pymupdf/PyMuPDF) - PDF処理

## 開始方法

### 前提条件

- Python 3.8以上
- OpenAI APIキー

### インストール

1. リポジトリをクローンする
```bash
git clone https://github.com/yourusername/math-exercise-generator.git
cd math-exercise-generator
```

2. 必要なパッケージをインストールする
```bash
pip install -r requirements.txt
```

3. `.env`ファイルを作成してOpenAI APIキーを設定する
```bash
echo "OPENAI_API_KEY=your_api_key_here" > .env
```

### 使用方法

1. アプリケーションを起動する
```bash
chainlit run app.py
```

2. ブラウザで `http://localhost:8000` にアクセスする

3. 利用可能なコマンド:
   - `/upload`: PDFをアップロードしてベクトルストアに保存
   - `/generate [出題範囲] [難易度]`: 指定した難易度と範囲で問題を生成
   - `/answer`: 最後に生成された問題の解答を表示
   - `/explain [質問]`: PDFの内容に基づいて特定の質問に回答
   - `/help`: ヘルプメッセージを表示

## ベクトルストア管理

- `/store list`: 使用可能なベクトルストアの一覧を表示
- `/store select [名前]`: 使用するベクトルストアを選択
- `/store add [名前] [説明]`: 新しいベクトルストアを追加
- `/store delete [名前]`: ベクトルストアを削除

## 難易度の基準

- **初級**: 大学学部レベル
- **中級**: 大学院初級レベル
- **上級**: 大学院上級レベル

## プロジェクト構造

- `app.py`: メインアプリケーション
- `pdf_processor.py`: PDFのアップロードと処理
- `problem_generator.py`: 数学問題生成
- `vectorstore_manager.py`: ベクトルストア管理
- `vector_stores/`: ベクトルストアのデータ
- `.chainlit/`: Chainlit設定

## ライセンス

[MITライセンス](LICENSE) 