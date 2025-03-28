from langchain_core.prompts import ChatPromptTemplate
from langchain.schema.runnable import RunnablePassthrough
from langchain_openai import ChatOpenAI
from langchain_chroma import Chroma
from operator import itemgetter
import os

from pydantic import BaseModel, Field

class MathProblem(BaseModel):
    """Math problem"""
    question: str = Field(..., description="LaTeX形式の数式を含む数学の問題文。$や$$を使用して数式を記述してください。")
    answer: str = Field(..., description="LaTeX形式の数式を含む解答と解説。$や$$を使用して数式を記述してください。")


class MathProblemGenerator:
    def __init__(self, llm, embedding_model, dir_db="./chroma_db", k=3):
        self.model = llm
        self.structured_model = self.model.with_structured_output(MathProblem)

        # ディレクトリが存在するか確認
        os.makedirs(dir_db, exist_ok=True)
        
        # 更新されたChroma初期化方法
        self.db = Chroma(
            persist_directory=dir_db,
            embedding_function=embedding_model
        )
        self.retriever = self.db.as_retriever(k=k)
        
        self.generate_prompt = ChatPromptTemplate.from_messages([
            ("system", """
            あなたは数学の問題を生成するプロフェッショナルです。
            以下の要件に従って、参考文書の内容に基づいて関連する数学の問題とその解答を生成してください。
            数学の問題は十分な複雑さと教育的かつ実践的な内容に基づいて作成してください。
            また、解答と解説は十分に丁寧かつ詳細に記述し、問いの内容に過不足なく適切な解答をするようにしてください。
            数学に関する表現は統一し、正確な数学用語を使用してください。
            
            
            # 問題の要件
            {topic}に関する問題を生成してください。
            問題は{difficulty}の難易度で作成してください。
            
            # 難易度の基準
            - 初級: 大学学部レベルの問題。基本的な概念の理解と応用が必要。
            - 中級: 大学院初級レベルの問題。より深い理解と複数の概念の組み合わせが必要。
            - 上級: 大学院上級レベルの問題。高度な理解、創造的な解法、複雑な数学的思考が必要。
            
            # 参考文書
            {source}
            
            # 生成する問題の形式
            問題や解答、解説はLaTeX形式で記述してください。"$"や"$$"を使用して数式を記述してください。
            例:
            $x^2 + y^2 = 1$
            $$x^2 + y^2 = 1$$  
            """),
        ])

        self.explain_prompt = ChatPromptTemplate.from_messages([
            ("system", """
            以下の参考文書に基づいて、質問に対して解説を行なってください。
            
            # 参考文書
            {source}
            
            # 質問
            {question}
            
            # 解説
            解説はLaTeX形式で記述してください。"$"や"$$"を使用して数式を記述してください。
            """),
        ])
        
        self.generate_chain = (
            RunnablePassthrough.assign(
                source=lambda x: self.retriever.invoke(x["topic"])
            )
            | self.generate_prompt
            | self.structured_model
        )

        self.explain_chain = (
            RunnablePassthrough.assign(
                source=lambda x: self.retriever.invoke(x["question"])
            )
            | self.explain_prompt
            | self.structured_model
        )

    def generate_problem(self, topic: str, difficulty: str) -> MathProblem:
        return self.generate_chain.invoke({"topic": topic, "difficulty": difficulty})
    
    def explain_problem(self, question: str) -> MathProblem:
        return self.explain_chain.invoke({"question": question})