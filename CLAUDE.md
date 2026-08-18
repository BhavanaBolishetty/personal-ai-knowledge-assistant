# Personal AI Knowledge Assistant

## Project Goal

Build a production-quality Personal AI Knowledge Assistant.

The application should help a user continuously collect knowledge from different sources and retrieve, organize, connect, and synthesize that knowledge later.

The system should not be treated as a simple "chat with PDF" application.

The core idea is:

The user adds knowledge over time from documents, web resources, notes, and other supported sources. The system processes and stores that knowledge. Later, the user can ask questions and receive grounded answers based on the relevant information stored in their personal knowledge base.

The application must provide source attribution so the user can understand where an answer came from.

## Important Product Principle

This is a personal knowledge system, not a generic chatbot.

The application should focus on:

- Persistent knowledge
- Multi-source retrieval
- Knowledge synthesis
- Source attribution
- Search
- Learning history
- Future extensibility
- Reliable AI behavior

Do not turn this into an unnecessary multi-agent system.

Do not add AI agents simply because they are popular.

Use the simplest architecture that solves the problem well.

## Initial Supported Sources

The initial version should support:

1. PDF documents
2. Plain text
3. Markdown
4. User-created notes

The architecture should allow future support for:

- Web pages
- GitHub repositories
- YouTube transcripts
- Other document formats

Do not implement all future sources immediately.

Build the architecture so they can be added later without rewriting the core system.

## Core User Flow

The initial application should support this flow:

1. User opens the application.
2. User uploads a supported document.
3. The system extracts the content.
4. The system splits the content into meaningful chunks.
5. The system creates embeddings for the chunks.
6. The embeddings and metadata are stored in the vector database.
7. The user asks a question.
8. The system converts the question into an embedding.
9. The system retrieves relevant knowledge.
10. The system generates a grounded answer using the retrieved context.
11. The application displays the answer.
12. The application displays the sources used for the answer.

## Multi-Source Synthesis

The system must be designed to retrieve information from multiple stored sources when appropriate.

For example, the knowledge base may contain:

- DSA notes
- System Design PDFs
- Machine Learning notes
- AI articles
- Personal notes

If a question requires information from multiple sources, the system should retrieve relevant information from those sources and synthesize it into one coherent answer.

The system must not assume that only one document is relevant.

However, do not force multiple sources into every answer.

Use multiple sources when they genuinely improve the answer.

## Source Attribution

Every retrieved piece of knowledge must preserve metadata about its source.

At minimum, track:

- Document ID
- Document name
- Source type
- Page number when available
- Chunk ID
- Date added
- Relevant metadata

The user should be able to see which sources contributed to an answer.

Never invent citations.

If the system cannot determine a source location, say so rather than creating one.

## Technology Direction

Use Python for the backend and AI/ML pipeline.

Use FastAPI for the backend API.

Use a modern web frontend that can be deployed publicly.

Use a vector database suitable for semantic retrieval.

Use an embedding model for semantic search.

Use an LLM for answer generation and synthesis.

Use PostgreSQL or another appropriate relational database for structured application data when required.

Use Docker for reproducible deployment.

Use Git and GitHub for version control.

Prefer free or free-tier services during development and initial deployment.

Do not introduce paid infrastructure unless explicitly approved.

## Architecture Principles

Keep responsibilities separated.

The system should eventually have clear layers for:

- API
- document ingestion
- text extraction
- chunking
- embeddings
- retrieval
- synthesis
- database access
- LLM integration
- evaluation

Do not put the entire application into one file.

Do not create unnecessary microservices.

Start with a modular monolith and only introduce separate services when there is a real reason.

## RAG Design

RAG means Retrieval-Augmented Generation.

The system should retrieve relevant information from the user's knowledge base before asking the LLM to generate an answer.

The retrieval pipeline should eventually support:

- semantic search
- top-K retrieval
- metadata filtering
- source-aware retrieval
- configurable retrieval parameters

Future improvements may include:

- hybrid search
- reranking
- query expansion
- better chunking strategies

Do not implement all advanced retrieval techniques in the first milestone.

## Knowledge and Memory

The system should distinguish between:

1. User documents and knowledge
2. Conversation history
3. Application metadata

Do not mix these concepts into one database structure.

The system should eventually allow users to ask questions such as:

- What have I learned about RAG?
- What did I study recently?
- What sources discuss caching?
- How are these two concepts related?
- Summarize what I have learned about system design.

These features should be added incrementally.

## Evaluation

Do not assume the RAG system works simply because it produces answers.

Create an evaluation strategy.

Eventually evaluate:

- Retrieval relevance
- Retrieval accuracy
- Source attribution
- Answer relevance
- Groundedness
- Latency

Create a small evaluation dataset with known questions and expected relevant sources.

Do not invent performance numbers.

Only report metrics that were actually measured.

## Security

Do not expose API keys in source code.

Use environment variables for secrets.

Never commit .env files containing secrets.

Validate uploaded files.

Limit file sizes.

Do not execute uploaded files.

Treat uploaded content as untrusted data.

## Error Handling

Handle common failures explicitly:

- Invalid file
- Unsupported file type
- Empty document
- Text extraction failure
- Embedding failure
- Vector database failure
- LLM failure
- Timeout
- Invalid user input

Return useful errors rather than exposing internal stack traces to users.

## Testing

Write tests as functionality is added.

At minimum, test:

- document processing
- chunking
- metadata handling
- retrieval
- API endpoints
- important error cases

Do not wait until the entire project is finished before testing.

## Git

Use meaningful commits.

Examples:

feat: add PDF ingestion

feat: add vector retrieval

feat: add grounded question answering

test: add retrieval evaluation

fix: handle empty PDF uploads

Do not commit secrets.

## Development Process

Build the application incrementally.

Do not implement the entire project in one step.

For every milestone:

1. Explain what we are building.
2. Explain why it is needed.
3. Implement it.
4. Run tests.
5. Run the application when appropriate.
6. Verify the result.
7. Report what changed.
8. Wait for the next task unless the next step is clearly part of the same milestone.

Do not silently move to advanced features.

## Important Rule

Do not make architectural decisions just to make the project look impressive.

Every technology should have a reason.

The final project should be understandable enough that the developer can explain:

- Why RAG was used
- Why embeddings were used
- Why a vector database was used
- How retrieval works
- How multiple sources are handled
- How citations are generated
- How the system is evaluated
- How the system could scale
- What trade-offs were considered

The goal is a strong AI/ML engineering project, not a collection of buzzwords.