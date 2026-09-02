LangChain + LangGraph



&#x20;                        AI APPLICATION

&#x20;                             │

&#x20;                             ▼

&#x20;                   ┌───────────────────┐

&#x20;                   │    LangChain      │

&#x20;                   │                   │

&#x20;                   │ Models             │

&#x20;                   │ Prompts            │

&#x20;                   │ Tools              │

&#x20;                   │ Structured Output  │

&#x20;                   │ Retrieval / RAG    │

&#x20;                   │ Agents             │

&#x20;                   └─────────┬─────────┘

&#x20;                             │

&#x20;                             ▼

&#x20;                   ┌───────────────────┐

&#x20;                   │     LangGraph     │

&#x20;                   │                   │

&#x20;                   │ State             │

&#x20;                   │ Nodes             │

&#x20;                   │ Edges             │

&#x20;                   │ Loops             │

&#x20;                   │ Persistence       │

&#x20;                   │ Interrupts        │

&#x20;                   │ HITL              │

&#x20;                   │ Durable execution  │

&#x20;                   └─────────┬─────────┘

&#x20;                             │

&#x20;                             ▼

&#x20;                   ┌───────────────────┐

&#x20;                   │    LangSmith      │

&#x20;                   │                   │

&#x20;                   │ Tracing           │

&#x20;                   │ Debugging         │

&#x20;                   │ Evaluation        │

&#x20;                   │ Monitoring        │

&#x20;                   └───────────────────┘



## **PART 1**

**LangChain is a framework for connecting LLMs with prompts, tools, data, memory, and application logic**



## PART 2 — The core LangChain components

###### **1. Models -** model.invoke()

###### **2. Messages -** ChatPromptTemplate

###### **3. Prompts -** chain = prompt | model | parser, **LCEL** = LangChain Expression Language.

###### &#x09;**Runnables .invoke() One input, .batch() Multiple inputs:, .stream() Stream execution/output:**



###### **4. Tools (**A function an LLM can decide to call.**)**

###### **5. Tool calling**

###### **6. Structured output** (User ↓ LLM ↓ Tool call ↓ Tool ↓ Tool result ↓ LLM ↓ Answer)downstream applications need reliable 	machine-readable data.

###### **7. Embeddings** (Embedding converts text into vectors.)

###### **8. Document loaders** 

###### **9. Text splitters** Document ↓ Chunks

###### **10. Vector stores** (FAISSChromaPineconeQdrantWeaviateMilvuspgvector)

###### **11. Retrievers**

###### **12. RAG** (2-step RAG, Agentic RAG, and Hybrid RAG)

###### **13. Agents**

###### **14. Middleware**

###### **15. Memory**

###### **16. LangGraph**

###### **17. LangSmith**





