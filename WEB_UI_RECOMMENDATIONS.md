# 🌐 Web UI Recommendations for SnapAnalyst Chatbot

**Date**: January 13, 2026  
**Goal**: Add full-featured web UI with chat history + data loading interface

---

## 🎯 **Top 3 Recommended Solutions**

### **Option 1: Chainlit ⭐ BEST FOR AI APPS**

**Why This is Perfect for You:**
- ✅ **Built specifically for AI chatbots** (not general purpose)
- ✅ **Chat history built-in** (SQLite/PostgreSQL)
- ✅ **File upload support** (for CSV data loading)
- ✅ **FastAPI compatible** (works with your backend)
- ✅ **Beautiful modern UI** out of the box
- ✅ **Python-based** (matches your stack)
- ✅ **Active development** (2026 updates)

**Features:**
- 💬 Chat interface with streaming
- 📁 File upload widget
- 📊 Data visualization support
- 🔄 Conversation history per user
- 🎨 Customizable UI
- 🔐 Authentication support
- 📱 Mobile responsive

**Installation:**
```bash
pip install chainlit==1.0.0
```

**GitHub**: https://github.com/Chainlit/chainlit  
**Stars**: 6.5k+ ⭐  
**License**: Apache 2.0

---

### **Option 2: Streamlit 🎨 EASIEST TO CUSTOMIZE**

**Why This Could Work:**
- ✅ **Full control** over UI design
- ✅ **Easy to build custom interfaces**
- ✅ **Built-in file uploader**
- ✅ **Session state for history**
- ✅ **Python-only** (no JavaScript needed)
- ✅ **Huge community** (documentation everywhere)
- ✅ **Data-focused** (great for analytics)

**Features:**
- 💬 `st.chat_input()` and `st.chat_message()` (native chat UI)
- 📁 `st.file_uploader()` for CSV uploads
- 📊 Built-in charts and tables
- 🔄 Session state for conversation history
- 🎨 Fully customizable layout
- 🚀 Fast development

**Installation:**
```bash
pip install streamlit==1.30.0
```

**GitHub**: https://github.com/streamlit/streamlit  
**Stars**: 30k+ ⭐  
**License**: Apache 2.0

---

### **Option 3: Libre Chat 🔥 FULL-FEATURED CHATBOT**

**Why This is Powerful:**
- ✅ **Complete chatbot solution** (like ChatGPT UI)
- ✅ **Chat history in database**
- ✅ **Document upload built-in**
- ✅ **Multi-user support**
- ✅ **Modern React UI**
- ✅ **Self-hosted**
- ✅ **API integration ready**

**Features:**
- 💬 Professional chat interface
- 📁 Document upload and processing
- 🔄 Persistent conversation history
- 👥 User authentication
- 🎨 Beautiful UI (React-based)
- 🔌 REST API integration
- 📱 Mobile friendly

**GitHub**: https://github.com/vemonet/libre-chat  
**Stars**: 1k+ ⭐  
**License**: MIT

---

## 📊 **Comparison Matrix**

| Feature | Chainlit | Streamlit | Libre Chat |
|---------|----------|-----------|------------|
| **Setup Time** | ⚡ 10 min | ⚡⚡ 5 min | ⚡⚡⚡ 30 min |
| **Python Integration** | ✅ Native | ✅ Native | 🔌 API calls |
| **Chat History** | ✅ Built-in | 🔧 Manual | ✅ Built-in |
| **File Upload** | ✅ Yes | ✅ Yes | ✅ Yes |
| **Customization** | 🎨 Medium | 🎨🎨🎨 Full | 🎨 Limited |
| **Learning Curve** | 📚 Low | 📚 Very Low | 📚📚 Medium |
| **Production Ready** | ✅ Yes | ✅ Yes | ✅ Yes |
| **Multi-user** | ✅ Yes | 🔧 Manual | ✅ Yes |
| **Authentication** | ✅ Built-in | 🔧 Manual | ✅ Built-in |
| **Mobile Friendly** | ✅ Yes | ✅ Yes | ✅ Yes |

---

## 🏆 **My Recommendation: Chainlit**

**Why Chainlit is the Best Choice:**

1. **Purpose-Built for AI Chatbots**
   - Not a general framework - specifically designed for LLM apps
   - Chat interface is the #1 priority (not an afterthought)

2. **Matches Your Stack**
   - Python-based (works with your FastAPI backend)
   - Can call your existing `/api/v1/chat/query` endpoint
   - Or integrate directly with your LLM service

3. **Complete Feature Set**
   - Chat history out of the box (PostgreSQL or SQLite)
   - File upload widget (for CSV data loading)
   - Streaming responses (real-time feedback)
   - User authentication (multi-user support)

4. **Great Developer Experience**
   - Simple decorator-based API
   - Hot reload during development
   - Excellent documentation
   - Active community

5. **Production Ready**
   - Battle-tested (used by major companies)
   - Scalable (handles multiple users)
   - Deployable anywhere (Docker, cloud, on-prem)

---

## 🚀 **Quick Start with Chainlit**

### **1. Install**
```bash
cd /Users/eric/Devl/Cursor/_private/SnapAnalyst
pip install chainlit==1.0.0
```

### **2. Create UI File**
```python
# chainlit_app.py
import chainlit as cl
import httpx

@cl.on_chat_start
async def start():
    """Initialize chat session"""
    await cl.Message(
        content="👋 Welcome to SnapAnalyst! Ask me anything about SNAP QC data."
    ).send()

@cl.on_message
async def main(message: cl.Message):
    """Handle user messages"""
    # Call your existing API
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/v1/chat/query",
            json={
                "question": message.content,
                "execute": True,
                "explain": True
            }
        )
        data = response.json()
    
    # Show SQL
    await cl.Message(
        content=f"**Generated SQL:**\n```sql\n{data['sql']}\n```"
    ).send()
    
    # Show results
    if data['results']:
        await cl.Message(
            content=f"**Results:**\n{data['results']}"
        ).send()
    else:
        await cl.Message(
            content="✅ Query generated! (Database is empty)"
        ).send()

# File upload handler
@cl.on_file_upload
async def handle_upload(file: cl.File):
    """Handle CSV file upload"""
    # Call your data loading endpoint
    async with httpx.AsyncClient() as client:
        files = {"file": (file.name, file.content, "text/csv")}
        response = await client.post(
            "http://localhost:8000/api/v1/data/load",
            files=files
        )
    
    await cl.Message(
        content=f"✅ Data loaded successfully!"
    ).send()
```

### **3. Run**
```bash
chainlit run chainlit_app.py -w
```

Visit: **http://localhost:8000** (Chainlit default port)

---

## 🎨 **Alternative: Streamlit Implementation**

If you prefer full control, here's a Streamlit version:

```python
# streamlit_app.py
import streamlit as st
import requests
import pandas as pd

st.set_page_config(page_title="SnapAnalyst", page_icon="🏠", layout="wide")

# Sidebar for file upload
with st.sidebar:
    st.header("📁 Data Loading")
    uploaded_file = st.file_uploader("Upload SNAP QC CSV", type=['csv'])
    if uploaded_file and st.button("Load Data"):
        files = {"file": uploaded_file}
        response = requests.post("http://localhost:8000/api/v1/data/load", files=files)
        st.success("Data loaded!")

# Main chat interface
st.title("💬 SnapAnalyst Chatbot")

# Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Chat input
if prompt := st.chat_input("Ask me about SNAP QC data..."):
    # Add user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # Get AI response
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            response = requests.post(
                "http://localhost:8000/api/v1/chat/query",
                json={"question": prompt, "execute": True, "explain": True}
            )
            data = response.json()
            
            # Show SQL
            st.code(data['sql'], language='sql')
            
            # Show results
            if data['results']:
                st.dataframe(pd.DataFrame(data['results']))
            else:
                st.info("Query generated! (Database is empty)")
            
            # Save to history
            st.session_state.messages.append({
                "role": "assistant",
                "content": f"```sql\n{data['sql']}\n```"
            })
```

Run with:
```bash
streamlit run streamlit_app.py
```

---

## 🔧 **Implementation Plan**

### **Phase 1: Quick Win with Chainlit (1 hour)**

1. **Install Chainlit**
   ```bash
   pip install chainlit httpx
   ```

2. **Create `chainlit_app.py`** (as shown above)

3. **Test locally**
   ```bash
   chainlit run chainlit_app.py -w
   ```

4. **Iterate and improve**
   - Add error handling
   - Improve UI messages
   - Add data visualization

### **Phase 2: Add Advanced Features (2-4 hours)**

1. **Chat History**
   ```python
   # .chainlit/config.toml
   [project]
   enable_telemetry = false
   
   [features]
   persist = true
   
   [database]
   type = "postgresql"
   url = "postgresql://user:pass@localhost/snapanalyst_db"
   ```

2. **File Upload UI**
   - Add file upload widget
   - Show upload progress
   - Display loaded records count

3. **Data Visualization**
   - Show query results as tables
   - Add charts for aggregations
   - Export results to CSV

4. **User Authentication** (if needed)
   ```python
   @cl.password_auth_callback
   def auth_callback(username: str, password: str):
       # Your auth logic
       return cl.User(identifier=username)
   ```

---

## 📦 **Deployment Options**

### **Option 1: Docker (Recommended)**
```dockerfile
# Dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8000 8501
CMD ["bash", "-c", "python src/api/main.py & chainlit run chainlit_app.py -h 0.0.0.0 -p 8501"]
```

### **Option 2: Separate Services**
```yaml
# docker-compose.yml
services:
  api:
    build: .
    ports:
      - "8000:8000"
    command: python src/api/main.py
  
  ui:
    build: .
    ports:
      - "8501:8501"
    command: chainlit run chainlit_app.py -h 0.0.0.0 -p 8501
    depends_on:
      - api
```

---

## 💡 **Bonus: Hugging Face Chat UI**

If you want a **ChatGPT-like interface**, consider:

**Hugging Face Chat UI**
- GitHub: https://github.com/huggingface/chat-ui
- Features: MongoDB history, theming, file uploads
- Stack: SvelteKit (requires Node.js)
- Best for: Production-grade, ChatGPT-style interface

**Setup:**
```bash
git clone https://github.com/huggingface/chat-ui
cd chat-ui
npm install
# Configure to call your API endpoint
npm run dev
```

---

## ✅ **My Final Recommendation**

### **Start with Chainlit**

**Why:**
1. ✅ **Fastest to implement** (< 1 hour to working UI)
2. ✅ **Python-native** (matches your stack)
3. ✅ **Chat history built-in** (exactly what you need)
4. ✅ **File upload support** (for data loading)
5. ✅ **Production ready** (scales well)

**Steps:**
1. Install: `pip install chainlit httpx`
2. Create: `chainlit_app.py` (50 lines)
3. Run: `chainlit run chainlit_app.py -w`
4. Visit: http://localhost:8000
5. **Done!** Full chatbot UI with history!

**If you need more customization later:**
- Add Streamlit for custom data dashboards
- Use Libre Chat for multi-tenant deployment
- Build custom React UI for enterprise features

---

## 📚 **Resources**

- **Chainlit Docs**: https://docs.chainlit.io/
- **Streamlit Chat**: https://docs.streamlit.io/library/api-reference/chat
- **Libre Chat**: https://github.com/vemonet/libre-chat
- **Hugging Face Chat UI**: https://github.com/huggingface/chat-ui

---

## 🚀 **Next Steps**

1. **Choose your UI framework** (I recommend Chainlit)
2. **Install dependencies**: `pip install chainlit httpx`
3. **Create UI file**: `chainlit_app.py`
4. **Test locally**: `chainlit run chainlit_app.py -w`
5. **Add features**: File upload, history, visualization
6. **Deploy**: Docker or cloud platform

**Ready to implement?** Let me know which option you prefer and I'll build it! 🎉
