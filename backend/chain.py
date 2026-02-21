"""
RAG pipeline with Groq LLM, retrieval and dialog context.
"""

import logging
from typing import AsyncIterator

from langchain_groq import ChatGroq
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from backend.config import GROQ_API_KEY, LLM_MODEL, LLM_TEMPERATURE, MAX_HISTORY_MESSAGES
from backend.retriever import format_sources, search_documents

logger = logging.getLogger("rag-chatbot")

SYSTEM_PROMPT = """Ты корпоративный AI-ассистент.
Отвечай естественно, понятно и по делу, без канцелярита.

Правила:
1. Используй только факты из блока «Контекст из документов».
2. Учитывай историю диалога: если пользователь пишет «это/он/там/они», связывай с предыдущими репликами.
3. Если вопрос неоднозначный, задай один короткий уточняющий вопрос.
4. Отвечай на языке пользователя.
5. После ключевых утверждений указывай источник в формате: [файл, стр. N].
6. Если ответа нет в контексте, честно скажи об этом и предложи, как переформулировать запрос.

Контекст из документов:
{context}
"""


def get_llm() -> ChatGroq:
    """Initialize Groq chat model."""
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY is not set. Please configure it in .env.")

    return ChatGroq(
        api_key=GROQ_API_KEY,
        model_name=LLM_MODEL,
        temperature=LLM_TEMPERATURE,
        streaming=True,
    )


def format_chat_history(chat_history: list[dict]) -> list:
    """Convert chat history into LangChain messages with a rolling window."""
    messages = []
    recent = chat_history[-MAX_HISTORY_MESSAGES:] if chat_history else []

    for msg in recent:
        role = msg.get("role", "")
        content = (msg.get("content", "") or "").strip()
        if not content:
            continue

        if role == "user":
            messages.append(HumanMessage(content=content))
        elif role == "assistant":
            messages.append(AIMessage(content=content))

    return messages


def build_retrieval_query(question: str, chat_history: list[dict]) -> str:
    """
    Build retrieval query with short conversational context.
    This improves follow-up questions like "а что там по срокам?".
    """
    user_turns = [
        (m.get("content", "") or "").strip()
        for m in chat_history
        if m.get("role") == "user" and (m.get("content", "") or "").strip()
    ]

    # Keep only the latest few user turns to avoid noisy retrieval query.
    tail = user_turns[-3:]
    if not tail:
        return question

    return "\n".join([*tail, question])


def format_docs(docs) -> str:
    """Format retrieved documents into context block for prompt."""
    if not docs:
        return "Документы не найдены."

    formatted = []
    for doc in docs:
        source = doc.metadata.get("source", "unknown")
        page = doc.metadata.get("page", "?")
        formatted.append(f"[Источник: {source}, стр. {page}]\n{doc.page_content}")

    return "\n\n---\n\n".join(formatted)


def build_rag_chain():
    """Build LCEL chain: prompt -> LLM -> text parser."""
    llm = get_llm()
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", SYSTEM_PROMPT),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{question}"),
        ]
    )
    return prompt | llm | StrOutputParser()


def get_answer(question: str, chat_history: list[dict]) -> dict:
    """Synchronous answer generation."""
    try:
        retrieval_query = build_retrieval_query(question, chat_history)
        docs = search_documents(retrieval_query)
        context = format_docs(docs)
        sources = format_sources(docs)
        history = format_chat_history(chat_history)

        chain = build_rag_chain()
        answer = chain.invoke(
            {
                "context": context,
                "chat_history": history,
                "question": question,
            }
        )

        logger.info(
            "Answer generated (%s chars, %s sources).",
            len(answer),
            len(sources),
        )
        return {"answer": answer, "sources": sources}

    except Exception as e:
        logger.error("Answer generation failed: %s", e)
        return {
            "answer": f"Произошла ошибка при генерации ответа: {str(e)}",
            "sources": [],
        }


async def get_answer_stream(question: str, chat_history: list[dict]) -> tuple[AsyncIterator[str], list[dict]]:
    """Streaming answer generation."""
    try:
        retrieval_query = build_retrieval_query(question, chat_history)
        docs = search_documents(retrieval_query)
        context = format_docs(docs)
        sources = format_sources(docs)
        history = format_chat_history(chat_history)

        chain = build_rag_chain()

        async def token_stream():
            try:
                async for chunk in chain.astream(
                    {
                        "context": context,
                        "chat_history": history,
                        "question": question,
                    }
                ):
                    yield chunk
            except Exception as e:
                logger.error("Streaming failed: %s", e)
                yield f"\n\nОшибка при генерации ответа: {str(e)}"

        logger.info("Streaming started for question: '%s...'", question[:80])
        return token_stream(), sources

    except Exception as e:
        logger.error("Streaming preparation failed: %s", e)

        async def error_stream():
            yield f"Произошла ошибка: {str(e)}"

        return error_stream(), []
