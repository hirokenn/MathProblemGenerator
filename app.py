import os
import chainlit as cl
from chainlit.input_widget import Select, Slider, TextInput
from pdf_processor import PDFProcessor
from problem_generator import MathProblemGenerator
from vectorstore_manager import VectorStoreManager
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
import fitz  # PyMuPDF
import traceback

# ベクトルストアマネージャーの初期化
vectorstore_manager = VectorStoreManager("./vector_stores")

# 環境設定
DB_DIR = vectorstore_manager.get_current_store_path()
os.makedirs(DB_DIR, exist_ok=True)

# モデルの初期化
embedding_model = OpenAIEmbeddings()
llm = ChatOpenAI(model="gpt-4o", temperature=0.2)  # 数学問題生成のため温度を下げる

# プロセッサとジェネレーターの初期化
pdf_processor = PDFProcessor(DB_DIR, embedding_model, llm)
problem_generator = MathProblemGenerator(llm, embedding_model, DB_DIR)

# 現在の問題を保存する変数
current_problem = None

# ウェルカムメッセージを保存するグローバル変数
welcome_message = None

@cl.on_chat_start
async def start():
    """チャットの開始時に実行される関数"""
    global welcome_message
    
    current_store_name = vectorstore_manager.get_current_store_name()
    
    # ウェルカムメッセージの内容を作成（装飾を追加）
    welcome_content = (
        "# 📚 数学問題生成ツール\n\n"
        "---\n\n"
        "## 🔍 利用可能なコマンド\n\n"
        "- `/upload`: PDFをアップロードしてベクトルストアに保存\n"
        "- `/generate [出題範囲] [難易度]`: 指定した難易度と範囲で問題を生成\n"
        "  例: `/generate 微分積分 中級`\n"
        "- `/answer`: 最後に生成された問題の解答を表示\n"
        "- `/explain [質問]`: PDFの内容に基づいて特定の質問に回答\n"
        "  例: `/explain 微分方程式とは何ですか？`\n"
        "- `/help`: このヘルプメッセージを表示\n\n"
        "## 📂 ベクトルストア管理\n\n"
        "- `/store list`: 使用可能なベクトルストアの一覧を表示\n"
        "- `/store select [名前]`: 使用するベクトルストアを選択\n"
        "- `/store add [名前] [説明]`: 新しいベクトルストアを追加\n"
        "- `/store delete [名前]`: ベクトルストアを削除\n"
        f"- 現在のベクトルストア: **{current_store_name}**\n\n"
        "## 🎓 難易度の基準\n\n"
        "- **初級**: 大学学部レベル\n"
        "- **中級**: 大学院初級レベル\n"
        "- **上級**: 大学院上級レベル\n\n"
        "## 💬 通常チャットモード\n\n"
        "スラッシュコマンド以外の入力は、AIとの数学に関する通常の会話として扱われます。\n"
        "質問や相談がある場合は、自由に入力してください。\n\n"
        "---\n"
        "_いつでも `/help` と入力すると、このメッセージを再表示できます。_"
    )
    
    # ウェルカムメッセージを作成
    welcome_message = cl.Message(content=welcome_content)
    await welcome_message.send()
    
    # チャット履歴の初期化
    cl.user_session.set("chat_history", [])
    
    # ウェルカムメッセージをセッションに保存
    cl.user_session.set("welcome_message_id", welcome_message.id)
    cl.user_session.set("welcome_content", welcome_content)

# ウェルカムメッセージが表示されているか確認し、必要に応じて再表示する関数
async def ensure_welcome_message():
    global welcome_message
    
    # ウェルカムメッセージIDとコンテンツをセッションから取得
    welcome_message_id = cl.user_session.get("welcome_message_id")
    welcome_content = cl.user_session.get("welcome_content")
    
    # ウェルカムメッセージが消えている場合は再表示
    if not welcome_message or not welcome_message_id:
        if welcome_content:
            # 保存された内容で新しいメッセージを作成
            welcome_message = cl.Message(content=welcome_content)
            await welcome_message.send()
            
            # 新しいIDを保存
            cl.user_session.set("welcome_message_id", welcome_message.id)

@cl.on_message
async def main(message: cl.Message):
    """メッセージを受信したときに実行される関数"""
    global current_problem, pdf_processor, problem_generator, DB_DIR
    
    # ウェルカムメッセージを確認
    await ensure_welcome_message()
    
    if message.content.startswith("/upload"):
        await handle_upload()
    
    elif message.content.startswith("/generate"):
        # /generateコマンドの引数を解析
        args = message.content.split()
        
        # コマンドだけの場合は設定画面を表示
        if len(args) == 1:
            await handle_generate_with_form()
        # 引数が与えられた場合は直接問題を生成
        elif len(args) >= 3:
            topic = args[1]
            difficulty = args[2]
            
            # 難易度の検証
            valid_difficulties = ["初級", "中級", "上級"]
            if difficulty not in valid_difficulties:
                await cl.Message(content=f"無効な難易度です。有効な難易度: {', '.join(valid_difficulties)}").send()
                return
                
            await generate_problem(difficulty, topic)
        # 引数が足りない場合はエラーメッセージを表示
        else:
            await cl.Message(
                content="引数が足りません。正しい使い方: `/generate [出題範囲] [難易度]`\n"
                       "例: `/generate 微分積分 中級`"
            ).send()
    
    elif message.content.startswith("/answer"):
        await explain_problem()
    
    elif message.content.startswith("/explain"):
        # 説明コマンドの処理
        command_text = message.content.strip()
        if len(command_text) <= 9:  # "/explain " の長さは9
            await cl.Message(content="❌ 質問が指定されていません。使い方: `/explain [質問]`").send()
            return
        
        question = command_text[9:].strip()  # "/explain " の後の質問部分を取得
        await handle_explain(question)
    
    elif message.content.startswith("/store"):
        # ベクトルストア管理コマンドの処理
        await handle_store_command(message.content)
    
    elif message.content.startswith("/help"):
        # ヘルプコマンドでウェルカムメッセージを再表示
        await show_help()
    
    else:
        # スラッシュコマンドでなければ、通常のチャットモードとして扱う
        await handle_normal_chat(message.content)

async def show_help():
    """ヘルプメッセージを表示する関数"""
    global welcome_message
    
    current_store_name = vectorstore_manager.get_current_store_name()
    
    # ヘルプメッセージの内容を作成（装飾を追加）
    help_content = (
        "# 📚 数学問題生成ツール\n\n"
        "---\n\n"
        "## 🔍 利用可能なコマンド\n\n"
        "- `/upload`: PDFをアップロードしてベクトルストアに保存\n"
        "- `/generate [出題範囲] [難易度]`: 指定した難易度と範囲で問題を生成\n"
        "  例: `/generate 微分積分 中級`\n"
        "- `/answer`: 最後に生成された問題の解答を表示\n"
        "- `/explain [質問]`: PDFの内容に基づいて特定の質問に回答\n"
        "  例: `/explain 微分方程式とは何ですか？`\n"
        "- `/help`: このヘルプメッセージを表示\n\n"
        "## 📂 ベクトルストア管理\n\n"
        "- `/store list`: 使用可能なベクトルストアの一覧を表示\n"
        "- `/store select [名前]`: 使用するベクトルストアを選択\n"
        "- `/store add [名前] [説明]`: 新しいベクトルストアを追加\n"
        "- `/store delete [名前]`: ベクトルストアを削除\n"
        f"- 現在のベクトルストア: **{current_store_name}**\n\n"
        "## 🎓 難易度の基準\n\n"
        "- **初級**: 大学学部レベル\n"
        "- **中級**: 大学院初級レベル\n"
        "- **上級**: 大学院上級レベル\n\n"
        "## 💬 通常チャットモード\n\n"
        "スラッシュコマンド以外の入力は、AIとの数学に関する通常の会話として扱われます。\n"
        "質問や相談がある場合は、自由に入力してください。\n\n"
        "---\n"
        "_いつでも `/help` と入力すると、このメッセージを再表示できます。_"
    )
    
    # 新しいヘルプメッセージを作成
    help_message = cl.Message(content=help_content)
    await help_message.send()
    
    # ウェルカムメッセージとして保存
    welcome_message = help_message
    cl.user_session.set("welcome_message_id", welcome_message.id)
    cl.user_session.set("welcome_content", help_content)

async def handle_store_command(command: str):
    """ベクトルストア管理コマンドを処理する関数"""
    global pdf_processor, problem_generator, DB_DIR
    
    # ウェルカムメッセージを確認
    await ensure_welcome_message()
    
    parts = command.split()
    
    if len(parts) < 2:
        await cl.Message(content="❌ ベクトルストアコマンドの形式が正しくありません。使用方法を確認してください。").send()
        return
    
    sub_command = parts[1]
    
    # 使用可能なベクトルストアの一覧表示
    if sub_command == "list":
        stores = vectorstore_manager.get_all_stores()
        current_store = vectorstore_manager.get_current_store_name()
        
        # ストア一覧の構築
        store_list = "\n".join([
            f"- **{store['name']}**{' 📌 (現在使用中)' if store['name'] == current_store else ''}: {store['description']}"
            for store in stores
        ])
        
        await cl.Message(content=f"# 📂 使用可能なベクトルストア\n\n{store_list}").send()
    
    # ベクトルストアの選択
    elif sub_command == "select":
        if len(parts) < 3:
            # 選択肢を表示
            stores = vectorstore_manager.get_all_stores()
            store_names = [store["name"] for store in stores]

            # 新しいChainlit APIに合わせて修正
            await cl.Message(content=f"## 📋 ベクトルストア選択\n\n使用するベクトルストアを選択してください\n\n選択肢: {', '.join(store_names)}").send()
            response = await cl.AskUserMessage(
                content="ベクトルストア名を入力してください",
                timeout=180
            ).send()
            
            if not response:
                return
            
            # ユーザー入力からストア名を取得
            selected_store = response["output"].strip()
            
            # 存在確認
            if selected_store not in store_names:
                await cl.Message(content=f"❌ '{selected_store}'は有効なベクトルストア名ではありません。").send()
                return
        else:
            # コマンドからストア名を取得
            selected_store = " ".join(parts[2:])
        
        try:
            # ストアの選択
            vectorstore_manager.set_current_store(selected_store)
            
            # ベクトルストアのパスを更新
            DB_DIR = vectorstore_manager.get_current_store_path()
            
            # プロセッサとジェネレーターを再初期化
            pdf_processor = PDFProcessor(DB_DIR, embedding_model, llm)
            problem_generator = MathProblemGenerator(llm, embedding_model, DB_DIR)
            
            await cl.Message(content=f"✅ ベクトルストア「{selected_store}」を選択しました。").send()
        except ValueError as e:
            await cl.Message(content=f"❌ エラー: {str(e)}").send()
    
    # 新しいベクトルストアの追加
    elif sub_command == "add":
        if len(parts) < 3:
            # 新しいChainlit APIに合わせて修正
            await cl.Message(content="## 📥 新しいベクトルストア追加\n\n新しいベクトルストアの情報を入力してください。\n\n「ストア名 説明」の形式で入力してください。").send()
            
            # ユーザーの入力を待機
            response = await cl.AskUserMessage(
                content="例: 線形代数資料 線形代数に関する資料を保存するベクトルストア",
                timeout=180
            ).send()
            
            if not response:
                return
            
            # 入力を解析
            input_parts = response["output"].strip().split(" ", 1)
            if len(input_parts) >= 1:
                store_name = input_parts[0]
                store_description = input_parts[1] if len(input_parts) > 1 else ""
            else:
                await cl.Message(content="❌ 入力形式が正しくありません。").send()
                return
        else:
            # コマンドからパラメータを取得
            store_name = parts[2]
            store_description = " ".join(parts[3:]) if len(parts) > 3 else ""
        
        try:
            # 新しいストアの追加
            new_store = vectorstore_manager.add_store(store_name, store_description)
            
            await cl.Message(content=f"✅ 新しいベクトルストア「{new_store['name']}」を追加しました。").send()
            
            # 自動的に新しいストアを選択するか尋ねる
            await cl.Message(content=f"## 🔄 ストア選択\n\n新しく追加したベクトルストア「{new_store['name']}」を使用しますか？").send()
            response = await cl.AskUserMessage(
                content="「はい」または「いいえ」で回答してください",
                timeout=180
            ).send()
            
            if response and response["output"].strip().lower() in ["はい", "yes", "y"]:
                # 新しいストアを選択
                vectorstore_manager.set_current_store(new_store["name"])
                
                # ベクトルストアのパスを更新
                DB_DIR = vectorstore_manager.get_current_store_path()
                
                # プロセッサとジェネレーターを再初期化
                pdf_processor = PDFProcessor(DB_DIR, embedding_model, llm)
                problem_generator = MathProblemGenerator(llm, embedding_model, DB_DIR)
                
                await cl.Message(content=f"✅ ベクトルストア「{new_store['name']}」を選択しました。").send()
        
        except ValueError as e:
            await cl.Message(content=f"❌ エラー: {str(e)}").send()
    
    # ベクトルストアの削除
    elif sub_command == "delete":
        if len(parts) < 3:
            # 選択肢を表示
            stores = vectorstore_manager.get_all_stores()
            store_names = [store["name"] for store in stores if store["name"] != "デフォルトストア"]
            
            if not store_names:
                await cl.Message(content="❌ 削除可能なベクトルストアがありません。デフォルトストアは削除できません。").send()
                return
            
            # 新しいChainlit APIに合わせて修正
            await cl.Message(content=f"## 🗑️ ベクトルストア削除\n\n削除するベクトルストアを選択してください\n\n選択肢: {', '.join(store_names)}").send()
            response = await cl.AskUserMessage(
                content="削除するベクトルストア名を入力してください",
                timeout=180
            ).send()
            
            if not response:
                return
            
            selected_store = response["output"].strip()
            
            # 存在確認と削除可能チェック
            if selected_store not in store_names:
                await cl.Message(content=f"❌ '{selected_store}'は有効なベクトルストア名ではないか、削除できません。").send()
                return
        else:
            # コマンドからストア名を取得
            selected_store = " ".join(parts[2:])
        
        # 削除の確認
        await cl.Message(content=f"⚠️ 警告: ベクトルストア「{selected_store}」を削除してもよろしいですか？この操作は元に戻せません。").send()
        confirm_response = await cl.AskUserMessage(
            content="「はい、削除します」または「いいえ、キャンセルします」と入力してください",
            timeout=180
        ).send()
        
        if not confirm_response or confirm_response["output"].strip() != "はい、削除します":
            await cl.Message(content="✅ 削除をキャンセルしました。").send()
            return
        
        try:
            # ストアの削除
            vectorstore_manager.delete_store(selected_store)
            
            # 現在のストア名を取得
            current_store_name = vectorstore_manager.get_current_store_name()
            
            # ベクトルストアのパスを更新（削除後は自動的にデフォルトか別のストアに切り替わる）
            DB_DIR = vectorstore_manager.get_current_store_path()
            
            # プロセッサとジェネレーターを再初期化
            pdf_processor = PDFProcessor(DB_DIR, embedding_model, llm)
            problem_generator = MathProblemGenerator(llm, embedding_model, DB_DIR)
            
            await cl.Message(content=f"✅ ベクトルストア「{selected_store}」を削除しました。現在のストア: {current_store_name}").send()
        except ValueError as e:
            await cl.Message(content=f"❌ エラー: {str(e)}").send()
    
    else:
        await cl.Message(content="❌ 無効なベクトルストアコマンドです。使用可能なコマンド: list, select, add, delete").send()

async def handle_upload():
    """PDFのアップロード処理を行う関数"""
    # ウェルカムメッセージを確認
    await ensure_welcome_message()
    
    files = await cl.AskFileMessage(
        content="## 📤 PDFアップロード\n\nPDFファイルをアップロードしてください",
        accept=["application/pdf"],
        max_size_mb=20,
        timeout=180,
    ).send()
    
    if not files:
        await cl.Message(content="❌ アップロードがキャンセルされました").send()
        return
    
    file = files[0]
    
    # 処理中のメッセージ
    msg = cl.Message(content=f"🔄 `{file.name}`を処理中です...")
    await msg.send()
    
    # デバッグメッセージの表示
    debug_msg = cl.Message(content="🔍 デバッグ情報を表示します")
    await debug_msg.send()
    
    try:
        # PDFのページ数を取得
        doc = fitz.open(file.path)
        total_pages = len(doc)
        doc.close()
        
        # 新しいUpdateメソッドの使用方法
        msg.content = f"📄 `{file.name}`（全{total_pages}ページ）の処理を開始します。"
        await msg.update()
        
        # 進捗状況を表示するための関数を定義
        async def progress_callback(current_page, total_pages, status_text=None):
            progress = int((current_page / total_pages) * 100)
            
            # ステータステキストがある場合は表示
            if status_text:
                message = f"🔄 `{file.name}`の処理中...\n\nページ {current_page}/{total_pages} ({progress}%)\n\n**状態**: {status_text}"
                debug_msg.content = f"🔍 最新の状態: {status_text}"
                await debug_msg.update()
            else:
                message = f"🔄 `{file.name}`の処理中...\n\nページ {current_page}/{total_pages} ({progress}%)"
            
            msg.content = message
            await msg.update()
        
        # 新しい進捗コールバック付きでPDFを処理
        result = await pdf_processor.process_pdf_with_progress(file.path, progress_callback)
        
        # 処理完了メッセージ
        msg.content = f"✅ `{file.name}`の処理が完了しました。\n\n全{total_pages}ページがベクトルストアに保存されました。"
        await msg.update()
        
        debug_msg.content = f"🔍 処理結果: {result}"
        await debug_msg.update()
    
    except Exception as e:
        error_traceback = traceback.format_exc()
        msg.content = f"❌ エラーが発生しました: {str(e)}"
        await msg.update()
        
        debug_msg.content = f"🐞 エラー詳細:\n```\n{error_traceback}\n```"
        await debug_msg.update()

async def handle_generate_with_form():
    """問題生成のフォーム入力画面を表示する関数"""
    # ウェルカムメッセージを確認
    await ensure_welcome_message()
    
    # 問題生成の説明メッセージ
    instruction_msg = cl.Message(
        content="## 🔢 問題生成の設定\n\n"
               "「[出題範囲] [難易度]」の形式で入力してください。\n"
               "例: `微分積分 中級`\n\n"
               "**有効な難易度**: 初級, 中級, 上級"
    )
    await instruction_msg.send()
    
    # AskUserMessageを使用して入力を取得
    response = await cl.AskUserMessage(
        content="出題範囲と難易度を入力してください",
        timeout=180,
    ).send()
    
    if not response:
        return
    
    # ユーザーが入力したテキストを解析
    user_input = response["output"].strip()
    parts = user_input.split()
    
    if len(parts) >= 2:
        topic = parts[0]
        difficulty = parts[1]
        
        # 難易度の検証
        valid_difficulties = ["初級", "中級", "上級"]
        if difficulty not in valid_difficulties:
            await cl.Message(content=f"❌ 無効な難易度です。有効な難易度: {', '.join(valid_difficulties)}").send()
            return
            
        await generate_problem(difficulty, topic)
    else:
        await cl.Message(
            content="❌ 入力形式が正しくありません。「[出題範囲] [難易度]」の形式で入力してください。\n"
                   "例: `微分積分 中級`"
        ).send()

async def generate_problem(difficulty, topic):
    """問題を生成する関数"""
    global current_problem
    
    # ウェルカムメッセージを確認
    await ensure_welcome_message()
    
    # 処理中のメッセージ
    msg = cl.Message(content=f"🔄 難易度「{difficulty}」、範囲「{topic}」の問題を生成中...")
    await msg.send()
    
    try:
        # 問題を生成
        current_problem = problem_generator.generate_problem(topic, difficulty)
        
        # current_problemが辞書型かどうか確認し、それに応じて値を取得
        if isinstance(current_problem, dict):
            question = current_problem.get("question", "問題の生成に失敗しました。")
        else:
            # オブジェクトの場合はアトリビュートとしてアクセス
            question = current_problem.question if hasattr(current_problem, "question") else "問題の生成に失敗しました。"
        
        # LaTeX形式の問題を表示
        msg.content = f"## 📝 問題\n\n{question}"
        await msg.update()
        
        # チャット履歴に問題を追加
        chat_history = cl.user_session.get("chat_history", [])
        chat_history.append({"role": "user", "content": f"/generate {topic} {difficulty}"})
        chat_history.append({"role": "assistant", "content": f"## 📝 問題\n\n{question}"})
        cl.user_session.set("chat_history", chat_history)
        
    except Exception as e:
        error_traceback = traceback.format_exc()
        msg.content = f"❌ 問題の生成中にエラーが発生しました: {str(e)}"
        await msg.update()
        
        # デバッグ情報
        debug_msg = cl.Message(content=f"🐞 エラー詳細:\n```\n{error_traceback}\n```")
        await debug_msg.send()

async def explain_problem():
    """問題の解答を表示する関数"""
    global current_problem
    
    # ウェルカムメッセージを確認
    await ensure_welcome_message()
    
    if current_problem is None:
        await cl.Message(content="❌ まだ問題が生成されていません。先に `/generate` コマンドで問題を生成してください。").send()
        return
    
    # current_problemが辞書型かどうか確認し、それに応じて値を取得
    if isinstance(current_problem, dict):
        answer = current_problem.get("answer", "解答がありません。")
    else:
        # オブジェクトの場合はアトリビュートとしてアクセス
        answer = current_problem.answer if hasattr(current_problem, "answer") else "解答がありません。"
    
    # 解答を表示
    answer_message = cl.Message(content=f"## 📝 解答\n\n{answer}")
    await answer_message.send()
    
    # チャット履歴に解答を追加
    chat_history = cl.user_session.get("chat_history", [])
    chat_history.append({"role": "user", "content": "/answer"})
    chat_history.append({"role": "assistant", "content": f"## 📝 解答\n\n{answer}"})
    cl.user_session.set("chat_history", chat_history)

async def handle_explain(question: str):
    """
    問題や質問に対する説明を提供する関数
    
    Args:
        question (str): 説明が必要な質問または問題
    """
    # ウェルカムメッセージを確認
    await ensure_welcome_message()
    
    # 処理中メッセージを表示
    msg = cl.Message(content=f"🔄 質問「{question}」について考えています...")
    await msg.send()
    
    try:
        # 問題に対する説明を生成
        result = problem_generator.explain_problem(question)
        
        # 結果の取得
        if isinstance(result, dict):
            explanation = result.get("answer", "説明を生成できませんでした。")
        else:
            explanation = result.answer if hasattr(result, "answer") else "説明を生成できませんでした。"
        
        # 説明を表示
        msg.content = f"## 📘 説明: {question}\n\n{explanation}"
        await msg.update()
        
        # チャット履歴に説明を追加
        chat_history = cl.user_session.get("chat_history", [])
        chat_history.append({"role": "user", "content": f"/explain {question}"})
        chat_history.append({"role": "assistant", "content": f"## 📘 説明: {question}\n\n{explanation}"})
        cl.user_session.set("chat_history", chat_history)
        
    except Exception as e:
        error_traceback = traceback.format_exc()
        msg.content = f"❌ 説明の生成中にエラーが発生しました: {str(e)}"
        await msg.update()
        
        # デバッグ情報
        debug_msg = cl.Message(content=f"🐞 エラー詳細:\n```\n{error_traceback}\n```")
        await debug_msg.send()

async def handle_normal_chat(message_content: str):
    """通常のチャットメッセージを処理する関数"""
    # ウェルカムメッセージを確認
    await ensure_welcome_message()
    
    try:
        # 処理中表示
        thinking_msg = cl.Message(content="考え中...")
        await thinking_msg.send()
        
        # チャット履歴の取得
        chat_history = cl.user_session.get("chat_history", [])
        
        # 新しいメッセージを追加
        chat_history.append({"role": "user", "content": message_content})
        
        # システムメッセージを含む会話のコンテキストを構築
        system_message = {"role": "system", "content": """あなたは数学の専門家です。数学の問題解決、概念の説明、学習方法のアドバイスを提供します。
        回答には適切に数式を使用し、LaTeX形式で記述してください。$や$$を使用して数式を記述してください。
        説明は論理的で正確な数学用語を使い、丁寧に行ってください。
        ユーザーの質問が曖昧な場合は、より詳細な情報を求めてください。
        また、数学に関する質問でない場合でも、教育的で役立つ回答を心がけてください。"""}
        
        messages = [system_message]
        messages.extend([{"role": msg["role"], "content": msg["content"]} for msg in chat_history])
        
        # 数学専門の知識を持つLLMとして応答を生成
        response = llm.invoke(messages)
        
        # 応答を履歴に追加
        chat_history.append({"role": "assistant", "content": response.content})
        
        # 履歴を保存（最大10往復まで保存）
        if len(chat_history) > 20:  # 10往復 = 20メッセージ
            chat_history = chat_history[-20:]
        cl.user_session.set("chat_history", chat_history)
        
        # 応答を表示
        thinking_msg.content = response.content
        await thinking_msg.update()
        
    except Exception as e:
        error_traceback = traceback.format_exc()
        await cl.Message(content=f"エラーが発生しました: {str(e)}").send()
        
        # デバッグ情報
        debug_msg = cl.Message(content=f"エラー詳細:\n```\n{error_traceback}\n```")
        await debug_msg.send()

if __name__ == "__main__":
    # Chainlitアプリの実行
    cl.run() 