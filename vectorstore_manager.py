import os
import json
from pathlib import Path

class VectorStoreManager:
    """ベクトルストアの管理を行うクラス"""
    
    CONFIG_FILE = "vectorstore_config.json"
    
    def __init__(self, base_dir="./vector_stores"):
        """
        ベクトルストアマネージャーを初期化
        
        Args:
            base_dir (str): ベクトルストアの基本ディレクトリ
        """
        self.base_dir = Path(base_dir)
        self.config_path = self.base_dir / self.CONFIG_FILE
        self.current_store = None
        
        # 基本ディレクトリが存在しない場合は作成
        os.makedirs(self.base_dir, exist_ok=True)
        
        # 設定ファイルの読み込み
        self.config = self._load_config()
        
        # デフォルトのストアをセット
        self._set_default_if_needed()
    
    def _load_config(self):
        """設定ファイルを読み込む"""
        if not os.path.exists(self.config_path):
            # デフォルト設定を作成
            default_config = {
                "stores": [
                    {
                        "name": "デフォルトストア",
                        "path": "default_store",
                        "description": "デフォルトのベクトルストア"
                    }
                ],
                "current_store": "デフォルトストア"
            }
            
            # 設定を保存
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(default_config, f, ensure_ascii=False, indent=2)
            
            return default_config
        
        # 既存の設定を読み込む
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"設定ファイルの読み込み中にエラーが発生しました: {str(e)}")
            # デフォルト設定を返す
            return {
                "stores": [
                    {
                        "name": "デフォルトストア",
                        "path": "default_store",
                        "description": "デフォルトのベクトルストア"
                    }
                ],
                "current_store": "デフォルトストア"
            }
    
    def _save_config(self):
        """設定ファイルを保存する"""
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(self.config, f, ensure_ascii=False, indent=2)
    
    def _set_default_if_needed(self):
        """デフォルトストアが未設定の場合はセット"""
        if not self.config.get("current_store") or not self.get_store_by_name(self.config["current_store"]):
            if len(self.config["stores"]) > 0:
                self.config["current_store"] = self.config["stores"][0]["name"]
            else:
                # ストアがない場合はデフォルトを追加
                self.config["stores"].append({
                    "name": "デフォルトストア",
                    "path": "default_store",
                    "description": "デフォルトのベクトルストア"
                })
                self.config["current_store"] = "デフォルトストア"
            
            self._save_config()
    
    def get_current_store_path(self):
        """現在のストアのパスを取得"""
        store = self.get_store_by_name(self.config["current_store"])
        if store:
            return str(self.base_dir / store["path"])
        return None
    
    def get_store_by_name(self, name):
        """名前からストア情報を取得"""
        for store in self.config["stores"]:
            if store["name"] == name:
                return store
        return None
    
    def get_all_stores(self):
        """全てのストア情報を取得"""
        return self.config["stores"]
    
    def get_current_store_name(self):
        """現在のストア名を取得"""
        return self.config["current_store"]
    
    def add_store(self, name, description=""):
        """新しいストアを追加"""
        # 名前の重複チェック
        if self.get_store_by_name(name):
            raise ValueError(f"'{name}'という名前のストアは既に存在します")
        
        # パス名の生成（名前をスネークケースに変換）
        path = name.lower().replace(" ", "_").replace("-", "_")
        
        # 新しいストアの情報
        new_store = {
            "name": name,
            "path": path,
            "description": description
        }
        
        # ストアの追加
        self.config["stores"].append(new_store)
        
        # ディレクトリ作成
        os.makedirs(self.base_dir / path, exist_ok=True)
        
        # 設定を保存
        self._save_config()
        
        return new_store
    
    def set_current_store(self, name):
        """現在のストアを設定"""
        store = self.get_store_by_name(name)
        if not store:
            raise ValueError(f"'{name}'という名前のストアは存在しません")
        
        # 現在のストアを更新
        self.config["current_store"] = name
        
        # 設定を保存
        self._save_config()
        
        return store
    
    def delete_store(self, name):
        """ストアを削除"""
        if name == "デフォルトストア":
            raise ValueError("デフォルトストアは削除できません")
        
        store = self.get_store_by_name(name)
        if not store:
            raise ValueError(f"'{name}'という名前のストアは存在しません")
        
        # 現在のストアが削除対象の場合はデフォルトに戻す
        if self.config["current_store"] == name:
            self._set_default_if_needed()
        
        # ストアの削除
        self.config["stores"] = [s for s in self.config["stores"] if s["name"] != name]
        
        # 設定を保存
        self._save_config()
        
        return True 