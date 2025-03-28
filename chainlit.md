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