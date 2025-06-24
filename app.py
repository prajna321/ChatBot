import streamlit as st

# ✅ FIRST Streamlit call
st.set_page_config("GitLab GenAI Chatbot", page_icon="🤖", layout="wide")

# Then all other imports and logic
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_core.documents import Document
from langchain.memory import ConversationSummaryBufferMemory
from langchain.chains import ConversationalRetrievalChain
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import PromptTemplate
import os

# ------------------------------
# 🔐 API KEY SETUP
# ------------------------------
if "GOOGLE_API_KEY" in st.secrets:
    os.environ["GOOGLE_API_KEY"] = st.secrets["GOOGLE_API_KEY"]
else:
    st.error("Google API Key not found. Please add it to Streamlit secrets.")
    st.stop()

# ------------------------------
# 🧠 Load FAISS Vector DB & Embeddings
# ------------------------------
@st.cache_resource(show_spinner="Loading vector DB...")
def load_vector_store():
    embedding = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    vectordb = FAISS.load_local(
        "data/faiss_index",
        embedding,
        allow_dangerous_deserialization=True
    )

    retriever = vectordb.as_retriever(
        search_type="mmr",
        search_kwargs={"k": 8, "fetch_k": 18}
    )
    return retriever

retriever = load_vector_store()

# ------------------------------
# 🤖 Gemini 2.5 Flash Setup via LangChain
# ------------------------------
gemini_llm = ChatGoogleGenerativeAI(
    model="gemini-1.5-flash",
    temperature=0.3,
    convert_system_message_to_human=True,
)

# ------------------------------
# 🧠 Chat Memory (Context Retention)
# ------------------------------
memory = ConversationSummaryBufferMemory(
    llm=gemini_llm,
    memory_key="chat_history",
    return_messages=True,
    output_key="answer"  # ✅ Fixes multi-output ambiguity
)

# ------------------------------
# 📜 Custom Prompt Template (Updated Correctly)
# ------------------------------
prompt = PromptTemplate(
    input_variables=["context", "question"],
    template="""
You are an expert assistant trained on GitLab's official Handbook and Direction documents.

Please:
- Answer with as much useful detail as possible.
- Use bullet points or formatting if appropriate.
- Cite the source section when available.
- Only answer from GitLab materials. Politely decline anything off-topic.

Context:
{context}

Question:
{question}
"""
)

# ✅ Final chain with explicit output_key
qa_chain = ConversationalRetrievalChain.from_llm(
    llm=gemini_llm,
    retriever=retriever,
    memory=memory,
    return_source_documents=True,
    combine_docs_chain_kwargs={"prompt": prompt},
    output_key="answer",  # ✅ Also required here
    verbose=False
)

# ------------------------------
# 🖼️ Streamlit UI Setup
# ------------------------------
st.title("🤖 GitLab Handbook & Direction AI Chatbot")
st.markdown("""
Welcome! This GenAI assistant helps GitLab team members and future employees learn about:
- 📘 GitLab's Handbook (culture, engineering, async, etc.)
- 🧭 GitLab's Product Direction (strategy, themes, FY25+)

Just ask your question below and the chatbot will find answers from official GitLab docs.
""")

# Chat session state
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

user_query = st.chat_input("Ask me anything about GitLab... ✨")

# Display past messages
for user_msg, bot_msg in st.session_state.chat_history:
    with st.chat_message("user", avatar="🧑"):
        st.markdown(user_msg)
    with st.chat_message("assistant", avatar="🤖"):
        st.markdown(bot_msg)

# New query
if user_query:
    with st.chat_message("user", avatar="🧑"):
        st.markdown(user_query)

    try:
        with st.spinner("🤖 Thinking... generating response..."):
            result = qa_chain({"question": user_query})
            response = result["answer"]

        with st.chat_message("assistant", avatar="🤖"):
            st.markdown(response)

        # Sources shown in expander
        with st.expander("📚 Sources & Reasoning", expanded=False):
            for doc in result.get("source_documents", []):
                meta = doc.metadata
                st.markdown(f"**{meta.get('source', 'Unknown')} →** `{meta.get('section', 'N/A')}`")
                st.code(doc.page_content.strip()[:700] + "...", language="markdown")

        st.session_state.chat_history.append((user_query, response))

    except Exception as e:
        st.error("⚠️ Something went wrong while generating the answer.")
        st.exception(e)
