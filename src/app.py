import os

import chainlit as cl
from dotenv import load_dotenv
from langchain.chat_models import ChatOpenAI
from langchain.embeddings import OpenAIEmbeddings
from langchain.prompts import PromptTemplate
from langchain.schema import HumanMessage
from langchain.text_splitter import CharacterTextSplitter
from langchain.vectorstores import Chroma

from document_loader import excel_loader, pdf_loader, word_loader

load_dotenv("../.env")

ALLOWED_MIME_TYPES = [
    "application/pdf",
    "application/octet-stream",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
]

ALLOWED_EXTENSIONS = [
    ".pdf",
    ".docx",
    ".xlsx",
]

prompt = PromptTemplate(
    template="""
    文章を前提にして質問に答えてください。

    文章 :
    {document}

    質問 : {question}
    """,
    input_variables=["document", "question"],
)


@cl.on_chat_start
async def on_chat_start():
    """初回起動時に呼び出される."""
    files = None

    # awaitメソッドのために、whileを利用する。アップロードされるまで続く。
    while files is None:
        # chainlitの機能に、ファイルをアップロードさせるメソッドがある。
        files = await cl.AskFileMessage(
            # ファイルの最大サイズ
            max_size_mb=20,
            # ファイルをアップロードさせる画面のメッセージ
            content="ファイルを選択してください（.pdf、.docx、.xlsxに対応しています）",
            # PDFファイルを指定する
            accept=ALLOWED_MIME_TYPES,
            # タイムアウトなし
            raise_on_timeout=False,
        ).send()

    file = files[0]
    ext = os.path.splitext(file.name)[1]

    # アップロードされたファイルのパスから中身を読み込む。
    if ext in ALLOWED_EXTENSIONS:
        if ext == ".pdf":
            documents = pdf_loader(file.path)
        elif ext == ".docx":
            documents = word_loader(file.path)
        else:
            documents = excel_loader(file.path)

        text_splitter = CharacterTextSplitter(chunk_size=400)
        splitted_documents = text_splitter.split_documents(documents)

        # テキストをベクトル化するOpenAIのモデル
        embeddings = OpenAIEmbeddings(model="text-embedding-ada-002")

        # Chromaにembedding APIを指定して、初期化する。
        database = Chroma(embedding_function=embeddings)

        # PDFから内容を分割されたドキュメントを保存する。
        database.add_documents(splitted_documents)

        # 今回は、簡易化のためセッションに保存する。
        cl.user_session.set("data", database)
        await cl.Message(content="アップロードが完了しました！").send()


@cl.on_message
async def on_message(input_message: cl.Message):
    """メッセージが送られるたびに呼び出される."""

    # 入力された文字と似たベクトルをPDFの中身から抽出
    # プロンプトを作成して、OpenAIに送信

    # チャット用のOpenAIのモデル。今回は3.5を選定
    open_ai = ChatOpenAI(model="gpt-4-0125-preview")

    # セッションからベクトルストアを取得（この中にPDFの内容がベクトル化されたものが格納されている）
    database = cl.user_session.get("data")

    # 質問された文から似た文字列を、DBより抽出
    documents = database.similarity_search(input_message.content)

    # 抽出したものを結合
    documents_string = ""
    for document in documents:
        documents_string += f"""
        ---------------------------------------------
        {document.page_content}
        """

    # プロンプトに埋め込みながらOpenAIに送信
    result = open_ai(
        [
            HumanMessage(
                content=prompt.format(
                    document=documents_string,
                    query=input_message.content,
                    question=input_message.content,
                )
            )
        ]
    ).content

    # 下記で結果を表示する(content=をOpenAIの結果にする。)
    await cl.Message(content=result).send()