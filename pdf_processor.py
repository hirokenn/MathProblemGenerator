from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage
import base64
import fitz
import os
import asyncio
import traceback

class PDFProcessor:
    def __init__(self, dir_db: str, embedding_model, llm):
        self.llm = llm
        self.embedding_model = embedding_model
        self.dir_db = dir_db
        
        # ディレクトリが存在するか確認
        os.makedirs(dir_db, exist_ok=True)
        
        # 更新されたChroma初期化方法
        self.db = Chroma(
            embedding_function=self.embedding_model,
            persist_directory=self.dir_db
        )

    def get_collection_size(self):
        """
        ベクトルストアのドキュメント数を取得する
        
        Returns:
            int: ベクトルストアのドキュメント数
        """
        try:
            # Chromaのコレクションサイズを取得
            return self.db._collection.count()
        except Exception as e:
            print(f"コレクションサイズの取得中にエラーが発生しました: {str(e)}")
            return 0

    def process_img(self, image_data):
        """
        画像データを処理する関数
        最新のLangChain APIに合わせて修正
        """
        # メッセージのコンテンツを作成
        message_content = [
            {"type": "text", "text": "このPDFの内容を詳細に説明してください。なお数式はlatex形式で$や$$を用いて記載するようにしてください。"},
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{image_data}"},
            },
        ]
        
        # 最新のLangChain APIでは、BaseMessagesのリストが必要
        messages = [HumanMessage(content=message_content)]
        
        # リストとしてメッセージを渡す
        response = self.llm.invoke(messages)
        return response

    def process_pdf(self, pdf_path: str):
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDFファイルが見つかりません: {pdf_path}")
        
        # PDFを開く
        doc = fitz.open(pdf_path)
        
        for page_num in range(len(doc)):
            # ページを取得
            page = doc[page_num]
            
            # ページを画像として取得
            pix = page.get_pixmap(matrix=fitz.Matrix(300/72, 300/72))
            
            # 画像をJPEGとして保存（一時的に）
            temp_path = f"temp_page_{page_num}.jpg"
            pix.save(temp_path)
            
            # 画像をbase64エンコード
            with open(temp_path, "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
            
            # 一時ファイルを削除
            os.remove(temp_path)
            
            # 画像を処理
            response = self.process_img(encoded_string)
            
            # ベクトルストアに保存
            self.db.add_texts(
                texts=[response.content],
                metadatas=[{"source": pdf_path, "page": page_num + 1}]
            )
        
        # PDFを閉じる
        doc.close()
        
        # ベクトルストアを保存
        self.db.persist()
    
    async def process_pdf_with_progress(self, pdf_path: str, progress_callback=None):
        """
        PDFを処理し、進捗状況をコールバック関数で報告する非同期関数
        
        Args:
            pdf_path (str): 処理するPDFファイルのパス
            progress_callback (function): 進捗状況を報告するコールバック関数
                                         引数: (current_page, total_pages)
        """
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDFファイルが見つかりません: {pdf_path}")
        
        try:
            # PDFを開く
            doc = fitz.open(pdf_path)
            total_pages = len(doc)
            
            # ベクトルストアを定期的に保存するためのカウンター
            page_count = 0
            
            for page_num in range(total_pages):
                page_count += 1
                current_page = page_num + 1
                
                # 進捗状況を報告
                if progress_callback:
                    await progress_callback(current_page, total_pages)
                    await asyncio.sleep(0.1)  # UIの更新を確実にするための短い待機
                
                try:
                    # ページステップの開始を表示
                    if progress_callback:
                        await progress_callback(current_page, total_pages, f"ページ {current_page} の画像変換中...")
                    
                    # ページを取得
                    page = doc[page_num]
                    
                    # ページを画像として取得
                    pix = page.get_pixmap(matrix=fitz.Matrix(300/72, 300/72))
                    
                    # 画像をJPEGとして保存（一時的に）
                    temp_path = f"temp_page_{page_num}.jpg"
                    pix.save(temp_path)
                    
                    # 進捗状況の更新
                    if progress_callback:
                        await progress_callback(current_page, total_pages, f"ページ {current_page} のエンコード中...")
                    
                    # 画像をbase64エンコード
                    with open(temp_path, "rb") as image_file:
                        encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
                    
                    # 一時ファイルを削除
                    os.remove(temp_path)
                    
                    # 進捗状況の更新
                    if progress_callback:
                        await progress_callback(current_page, total_pages, f"ページ {current_page} の解析中...")
                    
                    # 画像を処理（非同期処理を考慮）
                    response = self.process_img(encoded_string)
                    
                    # 進捗状況の更新
                    if progress_callback:
                        await progress_callback(current_page, total_pages, f"ページ {current_page} をベクトルストアに保存中...")
                    
                    # ベクトルストアに保存
                    self.db.add_texts(
                        texts=[response.content],
                        metadatas=[{"source": pdf_path, "page": current_page}]
                    )
                    
                    # 5ページごとにベクトルストアを保存する
                    if page_count % 5 == 0:
                        self.db.persist()
                        if progress_callback:
                            await progress_callback(current_page, total_pages, f"ページ {current_page} まで保存完了。ベクトルストア更新中...")
                            await asyncio.sleep(0.1)
                    
                except Exception as page_error:
                    # ページ処理中のエラーをキャッチ
                    error_msg = f"ページ {current_page} の処理中にエラーが発生しましたが、続行します: {str(page_error)}"
                    print(error_msg)
                    print(traceback.format_exc())
                    
                    if progress_callback:
                        await progress_callback(current_page, total_pages, error_msg)
                        await asyncio.sleep(1)  # エラーメッセージを表示するための待機
                    
                    # エラーが発生したページの情報を記録
                    self.db.add_texts(
                        texts=[f"エラー: このページの処理中に問題が発生しました。{str(page_error)}"],
                        metadatas=[{"source": pdf_path, "page": current_page, "error": True}]
                    )
                
                # 少し待機して、UIの更新を確実にする
                await asyncio.sleep(0.2)
            
            # PDFを閉じる
            doc.close()
            
            # ベクトルストアを保存
            self.db.persist()
            
            return {"status": "success", "total_pages": total_pages}
            
        except Exception as e:
            # 全体的なエラー処理
            error_message = f"PDFの処理中に致命的なエラーが発生しました: {str(e)}"
            print(error_message)
            print(traceback.format_exc())
            raise Exception(error_message)